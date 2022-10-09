from decimal import ROUND_DOWN, ROUND_UP, Decimal

import posthog
import stripe
from lotus.settings import POSTHOG_PERSON
from rest_framework import serializers

from metering_billing.models import (
    BillingPlan,
    Customer,
    Invoice,
    Organization,
    Subscription,
)
from metering_billing.payment_providers import StripeConnector
from metering_billing.serializers.model_serializers import InvoiceSerializer
from metering_billing.utils import (
    PAYMENT_PROVIDERS,
    make_all_dates_times_strings,
    make_all_datetimes_dates,
    make_all_decimals_floats,
)
from metering_billing.view_utils import calculate_sub_pc_usage_revenue

from .webhooks import invoice_created_webhook

# initialize payment processors
payment_providers = {}
payment_providers[PAYMENT_PROVIDERS.STRIPE] = StripeConnector()


# Invoice Serializers
class InvoiceOrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ("company_name",)


class InvoiceCustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = (
            "customer_name",
            "customer_id",
        )

    customer_name = serializers.CharField(source="name")


class InvoiceBillingPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingPlan
        fields = (
            "name",
            "description",
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
        fields = ("start_date", "end_date", "billing_plan", "subscription_id")


def generate_invoice(subscription, draft=False, issue_date=None, amount=None):
    """
    Generate an invoice for a subscription.
    """
    customer = subscription.customer
    organization = subscription.organization
    billing_plan = subscription.billing_plan
    issue_date = issue_date if issue_date else subscription.end_date
    if amount:
        line_item = {"Flat Subscription Fee Adjustment": amount}
    else:
        usage_dict = {"components": {}}
        for plan_component in billing_plan.components.all():
            pc_usg_and_rev = calculate_sub_pc_usage_revenue(
                plan_component,
                plan_component.billable_metric,
                customer,
                subscription.start_date,
                subscription.end_date,
            )
            usage_dict["components"][str(plan_component)] = pc_usg_and_rev
        components = usage_dict["components"]
        usage_dict["usage_revenue_due"] = 0
        for pc_name, pc_dict in components.items():
            for period, period_dict in pc_dict.items():
                usage_dict["usage_revenue_due"] += period_dict["revenue"]
        if billing_plan.pay_in_advance:
            if subscription.auto_renew:
                usage_dict["flat_revenue_due"] = billing_plan.flat_rate.amount
            else:
                usage_dict["flat_revenue_due"] = 0
        else:
            new_sub_daily_cost_dict = subscription.prorated_flat_costs_dict
            total_cost = sum(new_sub_daily_cost_dict.values())
            due = total_cost - float(subscription.flat_fee_already_billed)
            usage_dict["flat_revenue_due"] = max(due, 0)
            if due < 0:
                subscription.customer.balance += abs(due)

        usage_dict["flat_revenue_due"] = Decimal(usage_dict["flat_revenue_due"])
        usage_dict["total_revenue_due"] = (
            usage_dict["flat_revenue_due"] + usage_dict["usage_revenue_due"]
        )
        amount = usage_dict["total_revenue_due"]
        make_all_decimals_floats(usage_dict)
        print("pre")
        make_all_datetimes_dates(usage_dict)
        print("post")
        make_all_dates_times_strings(usage_dict)
        line_item = usage_dict

    # create kwargs for invoice
    org_serializer = InvoiceOrganizationSerializer(organization)
    customer_serializer = InvoiceCustomerSerializer(customer)
    subscription_serializer = InvoiceSubscriptionSerializer(subscription)
    invoice_kwargs = {
        "cost_due": amount,
        "issue_date": issue_date,
        "organization": org_serializer.data,
        "customer": customer_serializer.data,
        "subscription": subscription_serializer.data,
        "payment_status": "unpaid",
        "external_payment_obj_id": None,
        "external_payment_obj_type": None,
        "line_items": line_item,
    }

    # adjust kwargs depending on draft + external obj creation
    if draft:
        invoice_kwargs["payment_status"] = "draft"
    elif (
        customer.payment_provider != ""
        and payment_providers[customer.payment_provider].working()
    ):
        pp_connector = payment_providers[customer.payment_provider]
        customer_conn = pp_connector.customer_connected(customer)
        org_conn = pp_connector.organization_connected(organization)
        if customer_conn and org_conn:
            invoice_kwargs[
                "external_payment_obj_id"
            ] = pp_connector.generate_payment_object(customer, amount, organization)
            invoice_kwargs["external_payment_obj_type"] = customer.payment_provider

    # Create the invoice
    print("chill")
    print(line_item)
    invoice = Invoice.objects.create(**invoice_kwargs)
    print("donezo")

    if not draft:
        invoice_data = InvoiceSerializer(invoice).data
        invoice_created_webhook(invoice_data, organization)
        posthog.capture(
            POSTHOG_PERSON
            if POSTHOG_PERSON
            else subscription.organization.company_name,
            "generate_invoice",
            {
                "amount": amount,
            },
        )

    return invoice
