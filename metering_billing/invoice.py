from decimal import ROUND_DOWN, ROUND_UP, Decimal

import stripe
from lotus.settings import STRIPE_SECRET_KEY
from rest_framework import serializers

from metering_billing.models import (
    BillingPlan,
    Customer,
    Invoice,
    Organization,
    Subscription,
)
from metering_billing.utils import (
    calculate_plan_component_usage_and_revenue,
    make_all_decimals_floats,
)

from .webhooks import invoice_created_webhook


# Invoice Serializers
class InvoiceOrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ("company_name",)


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

    flat_rate = serializers.SerializerMethodField()

    def get_flat_rate(self, obj):
        return float(obj.flat_rate.amount)


class InvoiceSubscriptionSerializer(serializers.ModelSerializer):
    billing_plan = InvoiceBillingPlanSerializer()

    class Meta:
        model = Subscription
        fields = ("start_date", "end_date", "billing_plan")


def generate_invoice(subscription):
    """
    Generate an invoice for a subscription.
    """
    customer = subscription.customer
    organization = subscription.organization
    billing_plan = subscription.billing_plan
    usage_dict = {"components": {}}
    for plan_component in billing_plan.components.all():
        pc_usg_and_rev = calculate_plan_component_usage_and_revenue(
            customer, plan_component, subscription.start_date, subscription.end_date
        )
        usage_dict["components"][str(plan_component)] = pc_usg_and_rev
    components = usage_dict["components"]
    usage_dict["usage_revenue_due"] = sum(
        v["usage_revenue"] for _, v in components.items()
    )
    if billing_plan.pay_in_advance:
        if subscription.auto_renew:
            usage_dict["flat_revenue_due"] = billing_plan.flat_rate.amount
        else:
            usage_dict["flat_revenue_due"] = 0
    else:
        usage_dict["flat_revenue_due"] = billing_plan.flat_rate.amount
    usage_dict["flat_revenue_due"] = Decimal(usage_dict["flat_revenue_due"])
    usage_dict["total_revenue_due"] = (
        usage_dict["flat_revenue_due"] + usage_dict["usage_revenue_due"]
    )
    amount = usage_dict["total_revenue_due"]
    amount_cents = int(
        amount.quantize(Decimal(".01"), rounding=ROUND_DOWN) * Decimal(100)
    )
    if organization.stripe_id is not None:
        if customer.payment_provider_id is not None:
            print(organization.stripe_id, customer.payment_provider_id, amount_cents)
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=str.lower(customer.currency),
                payment_method_types=["card"],
                customer=customer.payment_provider_id,
                description=f"Invoice from {organization.company_name}",
                stripe_account=organization.stripe_id,
            )
            status = payment_intent.status
            payment_intent_id = payment_intent.id
        else:
            status = "customer_not_connected_to_stripe"
            payment_intent_id = None
    else:
        status = "organization_not_connected_to_stripe"
        payment_intent_id = None

    # Create the invoice
    org_serializer = InvoiceOrganizationSerializer(organization)
    customer_serializer = InvoiceCustomerSerializer(customer)
    subscription_serializer = InvoiceSubscriptionSerializer(subscription)

    make_all_decimals_floats(usage_dict)
    invoice = Invoice.objects.create(
        cost_due=amount_cents / 100,
        issue_date=subscription.end_date,
        organization=org_serializer.data,
        customer=customer_serializer.data,
        subscription=subscription_serializer.data,
        status=status,
        payment_intent_id=payment_intent_id,
        line_items=usage_dict,
    )

    invoice_data = {
        invoice: {
            "cost_due": amount_cents / 100,
            "issue_date": subscription.end_date,
            "organization": org_serializer.data,
            "customer": customer_serializer.data,
            "subscription": subscription_serializer.data,
            "status": status,
            "payment_intent_id": payment_intent_id,
            "line_items": usage_dict,
        }
    }
    invoice_created_webhook(invoice_data, organization)

    return invoice
