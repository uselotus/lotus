import datetime
from datetime import timezone
from decimal import Decimal

import posthog
from django.conf import settings
from metering_billing.payment_providers import PAYMENT_PROVIDER_MAP
from metering_billing.utils import (
    calculate_end_date,
    convert_to_decimal,
    date_as_min_dt,
    make_all_dates_times_strings,
    make_all_datetimes_dates,
    make_all_decimals_floats,
    now_utc,
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
    issue_date = now_utc()

    if amount:
        summary_dict = {
            "subtotal": amount,
            "line_items": [{
                "name": "Flat Subscription Fee Adjustment",
                "subtotal": amount,
                "quantity": 1,
                "type": "Adjustment",
            }],
        }
    else:
        summary_dict = {"line_items": []}
        for plan_component in billing_plan.components.all():
            pc_usg_and_rev = plan_component.calculate_revenue(
                customer,
                subscription.start_date,
                subscription.end_date,
            )
            usg_rev = pc_usg_and_rev.items()[0][1]
            line_item = {
                "name": plan_component.billable_metric.billable_metric_name,
                "start_date": subscription.start_date,
                "end_date": subscription.end_date,
                "quantity": usg_rev["usage_qty"],
                "subtotal": usg_rev["revenue"],
                "type": "In Arrears",
            }
            summary_dict["line_items"].append(line_item)
        # flat fee calculation
        flat_costs_dict_list = sorted(
            subscription.prorated_flat_costs_dict.items(), key=lambda x: x[0]
        )
        date_range_costs = [
            (
                0,
                flat_costs_dict_list[0][1]["plan_version_id"],
                flat_costs_dict_list[0][0],
                flat_costs_dict_list[0][0],
            )
        ]
        for k, v in flat_costs_dict_list:
            last_elem_amount, last_elem_plan, last_elem_start, _ = date_range_costs[-1]
            assert type(k) == type(issue_date.date())
            if (
                k > issue_date.date()
            ):  # only add flat fee if it is before the issue date
                break
            if v["plan_version_id"] != last_elem_plan:
                date_range_costs.append((v["amount"], v["plan_version_id"], k, k))
            else:
                last_elem_amount += v["amount"]
                date_range_costs[-1] = (
                    last_elem_amount,
                    last_elem_plan,
                    last_elem_start,
                    k,
                )
        for amount, _, start, end in date_range_costs:
            billing_plan_name = billing_plan.plan.name
            billing_plan_version = billing_plan.version
            summary_dict["line_items"].append(
                {
                    "name": f"{billing_plan_name} v{billing_plan_version} Flat Fee",
                    "start_date": start,
                    "end_date": end,
                    "quantity": 1,
                    "subtotal": amount,
                    "type": "In Arrears",
                }
            )
        if subscription.auto_renew:
            summary_dict["line_items"].append(
                {
                    "name": f"{billing_plan_name} v{billing_plan_version} Flat Fee",
                    "start_date": start,
                    "end_date": end,
                    "quantity": 1,
                    "subtotal": amount,
                    "type": "In Arrears",
                }
            )

        if billing_plan.flat_fee_billing_type == FLAT_FEE_BILLING_TYPE.IN_ADVANCE:
            if billing_plan.replace_with:
                new_bp = subscription.replace_with
            else:
                new_bp = billing_plan
            summary_dict["line_items"].append(
                {
                    "name": f"{new_bp.plan.name} v{new_bp.version} Flat Fee",
                    "start_date": subscription.end_date,
                    "end_date": calculate_end_date(
                        new_bp.plan.plan_duration, subscription.end_date
                    ),
                    "quantity": 1,
                    "subtotal": new_bp.flat_fee,
                    "type": "In Advance",
                }
            )
        if subscription.flat_fee_already_billed != 0:
            summary_dict["line_items"].append(
                {
                    "name": "Flat Fees Previously Paid",
                    "start_date": subscription.start_date,
                    "end_date": subscription.end_date,
                    "quantity": 1,
                    "subtotal": -subscription.flat_fee_already_billed,
                    "type": "In Arrears",
                }
            )
        summary_dict["subtotal"] = sum(
            [x["subtotal"] for x in summary_dict["line_items"]]
        )

        if billing_plan.price_adjustment:
            summary_dict["price_adjustment"] = str(billing_plan.price_adjustment)
            new_amount_due = billing_plan.price_adjustment.apply(
                summary_dict["subtotal"]
            )
            summary_dict["subtotal_after_adjustments"] = new_amount_due
        else:
            summary_dict["subtotal_after_adjustments"] = summary_dict["subtotal"]

        summary_dict["customer_balance_adjustment"] = max(
            customer.balance, -1 * summary_dict["subtotal_after_adjustments"]
        )
        summary_dict["total_amount_due"] = (
            summary_dict["subtotal_after_adjustments"]
            + summary_dict["customer_balance_adjustment"]
        )
        if summary_dict["customer_balance_adjustment"] != 0:
            customer.balance -= summary_dict["balance_adjustment"]
            customer.save()

        amount = summary_dict["total_amount_due"]
        summary_dict = make_all_decimals_floats(summary_dict)
        summary_dict = make_all_datetimes_dates(summary_dict)
        summary_dict = make_all_dates_times_strings(summary_dict)

    # create kwargs for invoice
    org_serializer = InvoiceOrganizationSerializer(organization)
    customer_serializer = InvoiceCustomerSerializer(customer)
    subscription_serializer = InvoiceSubscriptionSerializer(subscription)
    invoice_kwargs = {
        "cost_due": amount,
        "issue_date": issue_date,
        "organization": org_serializer.data,
        "customer": customer_serializer.data,
        "subscription": make_all_dates_times_strings(subscription_serializer.data),
        "payment_status": INVOICE_STATUS.UNPAID,
        "external_payment_obj_id": None,
        "external_payment_obj_type": None,
        "line_items": summary_dict,
    }

    # adjust kwargs depending on draft + external obj creation
    if draft:
        invoice_kwargs["payment_status"] = INVOICE_STATUS.DRAFT

    # Create the invoice
    invoice = Invoice.objects.create(**invoice_kwargs)
    for pp in customer.integrations.keys():
        if pp in PAYMENT_PROVIDER_MAP and PAYMENT_PROVIDER_MAP[pp].working():
            pp_connector = PAYMENT_PROVIDER_MAP[pp]
            customer_conn = pp_connector.customer_connected(customer)
            org_conn = pp_connector.organization_connected(organization)
            if customer_conn and org_conn:
                invoice.external_payment_obj_id = pp_connector.generate_payment_object(
                    invoice
                )
                invoice.external_payment_obj_type = pp
                invoice.save()
                break

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
