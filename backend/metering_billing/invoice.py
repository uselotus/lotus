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


def generate_invoice(subscription, draft=False, charge_next_plan=False):
    """
    Generate an invoice for a subscription.
    """
    from metering_billing.models import CustomerBalanceAdjustment, Invoice, PlanVersion
    from metering_billing.serializers.internal_serializers import (
        InvoiceCustomerSerializer,
        InvoiceOrganizationSerializer,
        InvoiceSubscriptionSerializer,
    )
    from metering_billing.serializers.model_serializers import InvoiceSerializer

    issue_date = now_utc()

    customer = subscription.customer
    organization = subscription.organization
    billing_plan = subscription.billing_plan
    plan_currency = billing_plan.flat_rate.currency
    customer_balance = customer.get_currency_balance(plan_currency)

    summary_dict = {"line_items": []}
    # usage calculation
    if subscription.end_date < issue_date:
        for plan_component in billing_plan.components.all():
            pc_usg_and_rev = plan_component.calculate_revenue(
                customer,
                subscription.start_date,
                subscription.end_date,
            )
            usg_rev = list(pc_usg_and_rev.items())[0][1]
            line_item = {
                "name": plan_component.billable_metric.billable_metric_name,
                "start_date": subscription.start_date,
                "end_date": subscription.end_date,
                "quantity": usg_rev["usage_qty"],
                "subtotal": usg_rev["revenue"],
                "type": "In Arrears",
                "associated_version": billing_plan,
            }
            summary_dict["line_items"].append(line_item)
    # flat fee calculation for current plan
    flat_costs_dict_list = sorted(
        list(subscription.prorated_flat_costs_dict.items()), key=lambda x: x[0]
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
        assert type(k) == type(str(issue_date.date())), "k is not a string"
        if (
            str(issue_date.date()) < k
        ):  # only add flat fee if it is before or equal the issue date
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
    for amount, plan_version_id, start, end in date_range_costs:
        cur_bp = PlanVersion.objects.get(version_id=plan_version_id)
        billing_plan_name = cur_bp.plan.plan_name
        billing_plan_version = cur_bp.version
        summary_dict["line_items"].append(
            {
                "name": f"{billing_plan_name} v{billing_plan_version} Flat Fee",
                "start_date": start,
                "end_date": end,
                "quantity": 1,
                "subtotal": amount,
                "type": "In Arrears",
                "associated_version": cur_bp,
            }
        )
    # next plan flat fee calculation
    if charge_next_plan:
        if billing_plan.replace_with:
            next_bp = subscription.replace_with
        else:
            next_bp = billing_plan
        if next_bp.flat_fee_billing_type == FLAT_FEE_BILLING_TYPE.IN_ADVANCE:
            summary_dict["line_items"].append(
                {
                    "name": f"{next_bp.plan.plan_name} v{next_bp.version} Flat Fee",
                    "start_date": subscription.end_date,
                    "end_date": calculate_end_date(
                        next_bp.plan.plan_duration, subscription.end_date
                    ),
                    "quantity": 1,
                    "subtotal": next_bp.flat_rate.amount,
                    "type": "In Advance",
                    "associated_version": next_bp,
                }
            )
    summary_dict["subtotal_by_plan"] = {}

    for line_item in summary_dict["line_items"]:
        associated_version = line_item.get("associated_version")
        billing_plan_name = associated_version.plan.plan_name
        billing_plan_version = associated_version.version
        plan_name = f"{billing_plan_name} v{billing_plan_version}"
        if associated_version not in summary_dict["subtotal_by_plan"]:
            summary_dict["subtotal_by_plan"][plan_name] = {
                "amount": 0,
                "plan": associated_version,
            }
        summary_dict["subtotal_by_plan"][plan_name]["amount"] += line_item["subtotal"]
        del line_item["associated_version"]
        line_item["source"] = plan_name

    summary_dict["subtotal_by_plan_after_adjustments"] = {}
    for plan_name, plan_dict in summary_dict["subtotal_by_plan"].items():
        subtotal_adjustment_dict = {}
        plan_version = plan_dict["plan"]
        plan_amount = convert_to_decimal(plan_dict["amount"])
        if plan_version.price_adjustment:
            subtotal_adjustment_dict["price_adjustment"] = str(
                billing_plan.price_adjustment
            )
            new_amount_due = billing_plan.price_adjustment.apply(plan_amount)
            subtotal_adjustment_dict["amount"] = max(new_amount_due, Decimal(0))
        else:
            subtotal_adjustment_dict["price_adjustment"] = "None"
            subtotal_adjustment_dict["amount"] = plan_amount
        summary_dict["subtotal_by_plan_after_adjustments"][
            plan_name
        ] = subtotal_adjustment_dict

    summary_dict["subtotal_by_plan"] = {
        k: v["amount"] for k, v in summary_dict["subtotal_by_plan"].items()
    }

    summary_dict["total"] = convert_to_decimal(
        sum(
            x["amount"]
            for x in summary_dict["subtotal_by_plan_after_adjustments"].values()
        )
    )

    summary_dict["already_paid"] = subscription.flat_fee_already_billed
    summary_dict["customer_balance_adjustment"] = max(
        customer_balance, -(summary_dict["total"] - summary_dict["already_paid"])
    )

    summary_dict["total_amount_due"] = (
        summary_dict["total"]
        - summary_dict["already_paid"]
        + summary_dict["customer_balance_adjustment"]
    )

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
        "payment_status": INVOICE_STATUS.DRAFT if draft else INVOICE_STATUS.UNPAID,
        "external_payment_obj_id": None,
        "external_payment_obj_type": None,
        "line_items": summary_dict,
    }

    # Create the invoice
    invoice = Invoice.objects.create(**invoice_kwargs)

    if not draft:
        for pp in customer.integrations.keys():
            if pp in PAYMENT_PROVIDER_MAP and PAYMENT_PROVIDER_MAP[pp].working():
                pp_connector = PAYMENT_PROVIDER_MAP[pp]
                customer_conn = pp_connector.customer_connected(customer)
                org_conn = pp_connector.organization_connected(organization)
                if customer_conn and org_conn:
                    invoice.external_payment_obj_id = (
                        pp_connector.create_payment_object(invoice)
                    )
                    invoice.external_payment_obj_type = pp
                    invoice.save()
                    break

        if summary_dict["customer_balance_adjustment"] != 0:
            CustomerBalanceAdjustment.objects.create(
                customer=customer,
                amount=-summary_dict["customer_balance_adjustment"],
                description=f"Balance alteration from invoice {invoice.invoice_id} generated on {issue_date}",
                created=issue_date,
                effective_at=issue_date,
            )

        invoice_data = InvoiceSerializer(invoice).data
        invoice_created_webhook(invoice_data, organization)
        posthog.capture(
            POSTHOG_PERSON
            if POSTHOG_PERSON
            else subscription.organization.company_name,
            "generate_invoice",
            properties={"organization": organization.company_name,"amount": amount,},
        )

    return invoice
