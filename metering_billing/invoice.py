from decimal import ROUND_DOWN, ROUND_UP, Decimal

import stripe
from lotus.settings import STRIPE_SECRET_KEY
from rest_framework import serializers

from metering_billing.exceptions import OrganizationMismatch, UserNoOrganization
from metering_billing.models import (
    BillingPlan,
    Customer,
    Invoice,
    Organization,
    Subscription,
)
from metering_billing.permissions import HasUserAPIKey
from metering_billing.serializers import (
    BillingPlanSerializer,
    PlanComponentSerializer,
    SubscriptionUsageSerializer,
)
from metering_billing.utils import calculate_plan_component_usage_and_revenue


#Invoice Serializers
class InvoiceOrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = (
            "company_name",
        )

class InvoiceCustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = (
            "name",
            "customer_id",
        )

class InvoiceBillingPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingPlan
        fields = (
            "name",
            "description",
            "currency",
            "interval",
            "flat_rate",
            "pay_in_advance",
        )

class InvoiceSubscriptionSerializer(serializers.ModelSerializer):
    billing_plan = InvoiceBillingPlanSerializer()
    usage = SubscriptionUsageSerializer()

    class Meta:
        model = Subscription
        fields = (
            "start_date",
            "end_date",
            "billing_plan"
        )


def generate_invoice(subscription):
    """
    Generate an invoice for a subscription.
    """
    customer = subscription.customer
    organization = subscription.organization
    billing_plan = subscription.billing_plan
    usage_dict = {"components": {}}
    for plan_component in billing_plan.components:
        usage_dict["components"][str(plan_component)] = calculate_plan_component_usage_and_revenue(
            customer, plan_component, subscription.start_date, subscription.end_date
        )
    usage_dict["usage_revenue_due"] = sum(x["usage_revenue_due"] for x in usage_dict)
    if billing_plan.pay_in_advance:
        if billing_plan.next_plan.exists():
            usage_dict["flat_revenue_due"] = billing_plan.next_plan.flat_rate
        else:
            usage_dict["flat_revenue_due"] = 0
    else:
        usage_dict["flat_revenue_due"] = billing_plan.flat_rate

    usage_dict["total_revenue_due"] = usage_dict["flat_revenue_due"] + usage_dict["usage_revenue_due"]
    

    amount = usage_dict["total_revenue_due"]
    amount_cents = int(amount.quantize(Decimal('.01'), rounding=ROUND_DOWN) * Decimal(100))
    payment_intent = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency=str.lower(amount.currency),
        payment_method_types=["card"],
        confirm=True,
        customer=customer.payment_provider_id,
        off_session=True,
        setup_future_usage="off_session",
        statement_descriptor=f"Invoice from {organization.name}",
        on_behalf_of=organization.stripe_id,
    )


    # Create the invoice
    org_serializer = InvoiceOrganizationSerializer(organization)
    org_serializer.is_valid(raise_exception=True)
    customer_serializer = InvoiceCustomerSerializer(customer)
    customer_serializer.is_valid(raise_exception=True)
    subscription_serializer = InvoiceSubscriptionSerializer(subscription)
    subscription_serializer.is_valid(raise_exception=True)
    invoice = Invoice.objects.create(
        cost_due=amount,
        issue_date=subscription.end_date,
        organization=org_serializer.validated_data,
        customer=customer_serializer.validated_data,
        subscription=subscription_serializer.validated_data,
        status=payment_intent.status,
        payment_intent_id=payment_intent.id,
        line_items=usage_dict,
    )

    return invoice
