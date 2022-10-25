from decimal import Decimal

import posthog
from django.conf import settings
from metering_billing.payment_providers import PAYMENT_PROVIDER_MAP
from metering_billing.utils import (
    convert_to_decimal,
    make_all_dates_times_strings,
    make_all_datetimes_dates,
    make_all_decimals_floats,
)
from metering_billing.utils.enums import FLAT_FEE_BILLING_TYPE, INVOICE_STATUS
from rest_framework import serializers

from .webhooks import invoice_created_webhook

POSTHOG_PERSON = settings.POSTHOG_PERSON


def generate_invoice(subscription, draft=False, issue_date=None, amount=None):
    """
    Generate an invoice for a subscription.
    """
    from metering_billing.models import Invoice
    from metering_billing.serializers.internal_serializers import (
        InvoiceCustomerSerializer,
        InvoiceOrganizationSerializer,
        InvoiceSubscriptionSerializer,
    )
    from metering_billing.serializers.model_serializers import InvoiceSerializer

    customer = subscription.customer
    organization = subscription.organization
    billing_plan = subscription.billing_plan
    issue_date = issue_date if issue_date else subscription.end_date
    if amount:
        line_item = {"Flat Subscription Fee Adjustment": amount}
    else:
        usage_dict = {"components": {}}
        for plan_component in billing_plan.components.all():
            pc_usg_and_rev = plan_component.calculate_revenue(
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
        if billing_plan.flat_fee_billing_type == FLAT_FEE_BILLING_TYPE.IN_ADVANCE:
            if subscription.auto_renew:
                usage_dict["flat_revenue_due"] = billing_plan.flat_rate.amount
            else:
                usage_dict["flat_revenue_due"] = 0
        else:
            new_sub_daily_cost_dict = subscription.prorated_flat_costs_dict
            total_cost = convert_to_decimal(
                sum(v["amount"] for v in new_sub_daily_cost_dict.values())
            )
            print("total cost", total_cost)
            print("new_sub_daily_cost_dict", new_sub_daily_cost_dict)
            print("len", len(new_sub_daily_cost_dict))
            due = (
                total_cost
                - subscription.flat_fee_already_billed
                - customer.balance.amount
            )
            usage_dict["flat_revenue_due"] = max(due, 0)
            if due < 0:
                subscription.customer.balance += abs(due)

        usage_dict["flat_revenue_due"] = Decimal(usage_dict["flat_revenue_due"])
        usage_dict["total_revenue_due"] = (
            usage_dict["flat_revenue_due"] + usage_dict["usage_revenue_due"]
        )
        amount = usage_dict["total_revenue_due"]
        usage_dict = make_all_decimals_floats(usage_dict)
        usage_dict = make_all_datetimes_dates(usage_dict)
        usage_dict = make_all_dates_times_strings(usage_dict)
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
        "payment_status": INVOICE_STATUS.UNPAID,
        "external_payment_obj_id": None,
        "external_payment_obj_type": None,
        "line_items": line_item,
    }

    # adjust kwargs depending on draft + external obj creation
    if draft:
        invoice_kwargs["payment_status"] = INVOICE_STATUS.DRAFT
    else:
        for pp in customer.payment_providers.keys():
            if pp in PAYMENT_PROVIDER_MAP and PAYMENT_PROVIDER_MAP[pp].working():
                pp_connector = PAYMENT_PROVIDER_MAP[pp]
                customer_conn = pp_connector.customer_connected(customer)
                org_conn = pp_connector.organization_connected(organization)
                if customer_conn and org_conn:
                    invoice_kwargs[
                        "external_payment_obj_id"
                    ] = pp_connector.generate_payment_object(
                        customer, amount, organization
                    )
                    invoice_kwargs["external_payment_obj_type"] = pp
                    break

    # Create the invoice
    invoice = Invoice.objects.create(**invoice_kwargs)

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
