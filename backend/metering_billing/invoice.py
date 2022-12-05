from __future__ import absolute_import

import datetime
from decimal import Decimal

import lotus_python
from dateutil import relativedelta
from django.conf import settings
from django.db.models import Sum
from djmoney.money import Money
from metering_billing.payment_providers import PAYMENT_PROVIDER_MAP
from metering_billing.utils import (
    calculate_end_date,
    convert_to_date,
    convert_to_datetime,
    convert_to_decimal,
    date_as_max_dt,
    date_as_min_dt,
    now_utc,
)
from metering_billing.utils.enums import (
    CHARGEABLE_ITEM_TYPE,
    CUSTOMER_BALANCE_ADJUSTMENT_STATUS,
    FLAT_FEE_BEHAVIOR,
    FLAT_FEE_BILLING_TYPE,
    INVOICE_STATUS,
)
from metering_billing.webhooks import invoice_created_webhook

POSTHOG_PERSON = settings.POSTHOG_PERSON
META = settings.META
# LOTUS_HOST = settings.LOTUS_HOST
# LOTUS_API_KEY = settings.LOTUS_API_KEY
# if LOTUS_HOST and LOTUS_API_KEY:
#     lotus_python.api_key = LOTUS_API_KEY
#     lotus_python.host = LOTUS_HOST


def generate_invoice(
    subscription,
    draft=False,
    charge_next_plan=False,
    generate_next_subscription_record=False,
    issue_date=None,
):
    """
    Generate an invoice for a subscription.
    """
    from metering_billing.models import (
        CustomerBalanceAdjustment,
        Invoice,
        InvoiceLineItem,
        PlanVersion,
        SubscriptionRecord,
    )
    from metering_billing.serializers.model_serializers import InvoiceSerializer

    subscription_records = SubscriptionRecord.objects.filter(
        organization=subscription.organization,
        customer=subscription.customer,
        next_billing_date__range=(subscription.start_date, subscription.end_date),
    ).order_by("start_date")

    if not issue_date:
        issue_date = now_utc()
    issue_date_fmt = issue_date.strftime("%Y-%m-%d")

    customer = subscription.customer
    organization = subscription.organization

    # create kwargs for invoice
    invoice_kwargs = {
        "issue_date": issue_date,
        "organization": organization,
        "customer": customer,
        "subscription": subscription,
        "payment_status": INVOICE_STATUS.DRAFT if draft else INVOICE_STATUS.UNPAID,
    }
    # Create the invoice
    invoice = Invoice.objects.create(**invoice_kwargs)

    for subscription_record in subscription_records:
        billing_plan = subscription.billing_plan
        pricing_unit = billing_plan.pricing_unit
        subscription_record_check_discount = [subscription_record]
        # usage calculation
        if subscription_record.invoice_usage_fees:
            for plan_component in billing_plan.plan_components.all():
                usg_rev = plan_component.calculate_total_revenue(subscription)
                subperiods = usg_rev["subperiods"]
                for subperiod in subperiods:
                    ili = InvoiceLineItem.objects.create(
                        name=str(plan_component.billable_metric.billable_metric_name),
                        start_date=subperiod["start_date"],
                        end_date=subperiod["end_date"],
                        quantity=subperiod["usage_qty"],
                        subtotal=subperiod["revenue"],
                        billing_type=FLAT_FEE_BILLING_TYPE.IN_ARREARS,
                        chargeable_item_type=CHARGEABLE_ITEM_TYPE.USAGE_CHARGE,
                        invoice=invoice,
                        associated_subscription_record=subscription_record,
                    )
                    if "unique_identifier" in subperiod:
                        ili.metadata = subperiod["unique_identifier"]
                        ili.save()
        # flat fee calculation for current plan
        if subscription_record.flat_fee_behavior is not FLAT_FEE_BEHAVIOR.REFUND:
            if subscription_record.flat_fee_behavior is FLAT_FEE_BEHAVIOR.PRORATE:
                duration_aligned_end_date = convert_to_date(
                    calculate_end_date(
                        billing_plan.duration, subscription_record.start_date
                    )
                )
                start = convert_to_date(subscription_record.start_date)
                end = convert_to_date(subscription_record.end_date)
                # now calculate the proration as the ratio of the duration aligned end date to the total duration
                proration_factor = (end - start).days / (
                    duration_aligned_end_date - start
                ).days
                flat_fee_due = subscription_record.flat_fee * proration_factor
            else:
                flat_fee_due = subscription_record.flat_fee
            flat_fee_paid = subscription_record.amount_already_invoiced()
            if abs(float(flat_fee_paid) - float(flat_fee_due)) < 0.01:
                pass
            else:
                billing_plan_name = billing_plan.plan.plan_name
                billing_plan_version = billing_plan.plan_version
                InvoiceLineItem.objects.create(
                    name=f"{billing_plan_name} v{billing_plan_version} Prorated Flat Fee",
                    start_date=convert_to_datetime(start, date_behavior="min"),
                    end_date=convert_to_datetime(end, date_behavior="max"),
                    quantity=None,
                    subtotal=flat_fee_due,
                    billing_type=billing_plan.flat_fee_billing_type,
                    chargeable_item_type=CHARGEABLE_ITEM_TYPE.USAGE_CHARGE,
                    invoice=invoice,
                    associated_subscription_record=subscription_record,
                )
                if flat_fee_paid > 0:
                    InvoiceLineItem.objects.create(
                        name=f"{billing_plan_name} v{billing_plan_version} Flat Fee Already Invoiced",
                        start_date=issue_date,
                        end_date=issue_date,
                        quantity=None,
                        subtotal=-flat_fee_paid,
                        billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
                        chargeable_item_type=CHARGEABLE_ITEM_TYPE.USAGE_CHARGE,
                        invoice=invoice,
                        associated_subscription_record=subscription_record,
                    )
        # next plan flat fee calculation
        if billing_plan.transition_to:
            next_bp = billing_plan.transition_to.display_version
        elif billing_plan.replace_with:
            next_bp = billing_plan.replace_with
        else:
            next_bp = billing_plan
        if generate_next_subscription_record:
            if (
                subscription_record.end_date <= subscription_record.end_date
                and subscription_record.auto_renew
            ):
                subrec_dict = {
                    "organization": subscription_record.organization,
                    "customer": subscription_record.customer,
                    "billing_plan": next_bp,
                    "start_date": date_as_min_dt(
                        subscription_record.end_date + relativedelta(days=1)
                    ),
                    "is_new": False,
                    "filters": subscription_record.filters,
                }
                next_subscription_record = SubscriptionRecord.objects.create(
                    **subrec_dict
                )
                subscription_record_check_discount.append(next_subscription_record)
            else:
                next_subscription_record = None
        else:
            next_subscription_record = None
        if charge_next_plan:
            if (
                next_bp.flat_fee_billing_type == FLAT_FEE_BILLING_TYPE.IN_ADVANCE
                and next_bp.flat_fee > 0
                and subscription_record.auto_renew
            ):
                ili = InvoiceLineItem.objects.create(
                    name=f"{next_bp.plan.plan_name} v{next_bp.version} Flat Fee - Next Period",
                    start_date=subscription.end_date,
                    end_date=calculate_end_date(
                        next_bp.plan.plan_duration, subscription.end_date
                    ),
                    quantity=None,
                    subtotal=next_bp.flat_rate,
                    billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
                    invoice=invoice,
                )
                if next_subscription_record:
                    ili.associated_subscription_record = next_subscription_record
                    ili.save()

        for subscription_record in subscription_record_check_discount:
            plan_version = subscription_record.billing_plan
            if plan_version.price_adjustment:
                plan_amount = (
                    invoice.line_items.filter(
                        associated_subscription_record=subscription_record
                    ).aggregate(tot=Sum("subtotal"))["tot"]
                    or 0
                )
                price_adj_name = str(plan_version.price_adjustment)
                new_amount_due = billing_plan.price_adjustment.apply(plan_amount)
                new_amount_due = max(new_amount_due, Decimal(0))
                difference = new_amount_due - plan_amount
                InvoiceLineItem.objects.create(
                    name=f"{plan_version.plan.plan_name} v{plan_version.version} {price_adj_name}",
                    start_date=issue_date,
                    end_date=issue_date,
                    quantity=None,
                    subtotal=difference,
                    billing_type=FLAT_FEE_BILLING_TYPE.IN_ARREARS,
                    chargeable_item_type=CHARGEABLE_ITEM_TYPE.PLAN_ADJUSTMENT,
                    invoice=invoice,
                    associated_subscription_record=subscription_record,
                )

    subtotal = invoice.inv_line_items.aggregate(tot=Sum("subtotal"))["tot"] or 0
    if subtotal < 0:
        InvoiceLineItem.objects.create(
            name=f"{subscription.subscription_id} Customer Balance Adjustment",
            start_date=issue_date,
            end_date=issue_date,
            quantity=None,
            subtotal=-subtotal,
            billing_type=FLAT_FEE_BILLING_TYPE.IN_ARREARS,
            chargeable_item_type=CHARGEABLE_ITEM_TYPE.CUSTOMER_ADJUSTMENT,
            invoice=invoice,
        )
        if not draft:
            CustomerBalanceAdjustment.objects.create(
                organization=organization,
                customer=customer,
                amount=-subtotal,
                description=f"Balance increase from invoice {invoice.invoice_id} generated on {issue_date_fmt}",
                created=issue_date,
                effective_at=issue_date,
                status=CUSTOMER_BALANCE_ADJUSTMENT_STATUS.ACTIVE,
            )
            subscription.flat_fee_already_billed += subtotal
            subscription.save()
    elif subtotal > 0:
        customer_balance = CustomerBalanceAdjustment.get_pricing_unit_balance(customer)
        balance_adjustment = min(subtotal, customer_balance)
        if balance_adjustment > 0 and not draft:
            leftover = CustomerBalanceAdjustment.draw_down_amount(
                customer,
                balance_adjustment,
                description=f"Balance decrease from invoice {invoice.invoice_id} generated on {issue_date_fmt}",
            )
            subscription.flat_fee_already_billed += balance_adjustment - leftover
            subscription.save()
            InvoiceLineItem.objects.create(
                name=f"{subscription.subscription_id} Customer Balance Adjustment",
                start_date=issue_date,
                end_date=issue_date,
                quantity=None,
                subtotal=-balance_adjustment + leftover,
                billing_type=FLAT_FEE_BILLING_TYPE.IN_ARREARS,
                chargeable_item_type=CHARGEABLE_ITEM_TYPE.CUSTOMER_ADJUSTMENT,
                invoice=invoice,
            )

    invoice.cost_due = invoice.inv_line_items.aggregate(tot=Sum("subtotal"))["tot"] or 0
    if abs(invoice.cost_due) < 0.01 and not draft:
        invoice.payment_status = INVOICE_STATUS.PAID
    invoice.save()

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
        # if META:
        # lotus_python.track_event(
        #     customer_id=organization.company_name + str(organization.pk),
        #     event_name='create_invoice',
        #     properties={
        #         'amount': float(invoice.cost_due.amount),
        #         'currency': str(invoice.cost_due.currency),
        #         'customer': customer.customer_id,
        #         'subscription': subscription.subscription_id,
        #         'external_type': invoice.external_payment_obj_type,
        #         },
        # )
        invoice_created_webhook(invoice, organization)

    return invoice
