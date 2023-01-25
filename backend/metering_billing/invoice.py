from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db.models import Sum
from metering_billing.payment_providers import PAYMENT_PROVIDER_MAP
from metering_billing.utils import (
    calculate_end_date,
    convert_to_datetime,
    convert_to_decimal,
    date_as_min_dt,
    now_utc,
)
from metering_billing.utils.enums import (
    CHARGEABLE_ITEM_TYPE,
    CUSTOMER_BALANCE_ADJUSTMENT_STATUS,
    FLAT_FEE_BEHAVIOR,
    FLAT_FEE_BILLING_TYPE,
    ORGANIZATION_SETTING_GROUPS,
    ORGANIZATION_SETTING_NAMES,
)
from metering_billing.webhooks import invoice_created_webhook

POSTHOG_PERSON = settings.POSTHOG_PERSON
META = settings.META
DEBUG = settings.DEBUG
# LOTUS_HOST = settings.LOTUS_HOST
# LOTUS_API_KEY = settings.LOTUS_API_KEY
# if LOTUS_HOST and LOTUS_API_KEY:
#     lotus_python.api_key = LOTUS_API_KEY
#     lotus_python.host = LOTUS_HOST


def generate_invoice(
    subscription,
    subscription_records,
    draft=False,
    charge_next_plan=False,
    generate_next_subscription_record=False,
    issue_date=None,
):  # NOTE: CHARGE_NEXT_PLAN needs to be true to generate next subscription record
    """
    Generate an invoice for a subscription.
    """
    from metering_billing.models import Invoice, OrganizationSetting
    from metering_billing.tasks import generate_invoice_pdf_async

    if not issue_date:
        issue_date = now_utc()

    customer = subscription.customer
    organization = subscription.organization
    try:
        _ = (e for e in subscription_records)
    except TypeError:
        subscription_records = [subscription_records]
    distinct_currencies = set(
        [sr.billing_plan.pricing_unit for sr in subscription_records]
    )
    invoices = {}
    for currency in distinct_currencies:
        # create kwargs for invoice
        invoice_kwargs = {
            "issue_date": issue_date,
            "organization": organization,
            "customer": customer,
            "subscription": subscription,
            "payment_status": Invoice.PaymentStatus.DRAFT
            if draft
            else Invoice.PaymentStatus.UNPAID,
            "currency": currency,
        }
        due_date = issue_date
        grace_period_setting = OrganizationSetting.objects.filter(
            organization=organization,
            setting_name=ORGANIZATION_SETTING_NAMES.PAYMENT_GRACE_PERIOD,
            setting_group=ORGANIZATION_SETTING_GROUPS.BILLING,
        ).first()
        if grace_period_setting:
            due_date += relativedelta(
                days=int(grace_period_setting.setting_values["value"])
            )
        invoice_kwargs["due_date"] = due_date
        # Create the invoice
        invoice = Invoice.objects.create(**invoice_kwargs)
        invoices[currency] = invoice

    for subscription_record in subscription_records:
        invoice = invoices[subscription_record.billing_plan.pricing_unit]
        # usage calculation
        calculate_subscription_record_usage_fees(subscription_record, invoice)
        # flat fee calculation for current plan
        calculate_subscription_record_flat_fees(subscription_record, invoice)
        # next plan flat fee calculation
        next_bp = find_next_billing_plan(subscription_record)
        sr_renews = check_subscription_record_renews(subscription, subscription_record)
        if sr_renews:
            if generate_next_subscription_record:
                # actually make one, when we're actually invoicing
                next_subscription_record = create_next_subscription_record(
                    subscription, next_bp
                )
            else:
                # this is just a placeholder e.g. for previewing draft invoices
                next_subscription_record = subscription_record
            if charge_next_plan:
                # this can be both for actual invoicing or just for drafts to see whats next
                charge_next_plan_flat_fee(
                    subscription_record, next_subscription_record, next_bp, invoice
                )
    for invoice in invoices.values():
        apply_plan_discounts(invoice)
        apply_taxes(invoice, customer, organization)
        apply_customer_balance_adjustments(invoice, customer, organization, draft)

        invoice.cost_due = invoice.line_items.aggregate(tot=Sum("subtotal"))["tot"] or 0
        if abs(invoice.cost_due) < 0.01 and not draft:
            invoice.payment_status = Invoice.PaymentStatus.PAID
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
            for subscription_record in subscription_records:
                subscription_record.fully_billed = True
                subscription_record.save()
            generate_invoice_pdf_async.delay(invoice.pk)
            invoice_created_webhook(invoice, organization)

    return invoices


def calculate_subscription_record_usage_fees(subscription_record, invoice):
    billing_plan = subscription_record.billing_plan
    # only calculate this for parent plans! addons should never calculate
    if (
        subscription_record.invoice_usage_charges
        and billing_plan.plan.addon_spec is None
    ):
        for plan_component in billing_plan.plan_components.all():
            usg_rev = plan_component.calculate_total_revenue(subscription_record)
            InvoiceLineItem.objects.create(
                name=str(plan_component.billable_metric.billable_metric_name),
                start_date=subscription_record.usage_start_date,
                end_date=subscription_record.end_date,
                quantity=usg_rev["usage_qty"] or 0,
                subtotal=usg_rev["revenue"],
                billing_type=FLAT_FEE_BILLING_TYPE.IN_ARREARS,
                chargeable_item_type=CHARGEABLE_ITEM_TYPE.USAGE_CHARGE,
                invoice=invoice,
                associated_subscription_record=subscription_record,
                associated_plan_version=billing_plan,
                organization=organization,
            )


def apply_plan_discounts(invoice):
    from metering_billing.models import InvoiceLineItem, PlanVersion, SubscriptionRecord

    distinct_sr_pv_combos = (
        invoice.line_items.filter(
            associated_subscription_record__isnull=False,
            associated_plan_version__isnull=False,
        )
        .values("associated_subscription_record", "associated_plan_version")
        .distinct()
    )
    srs = SubscriptionRecord.objects.filter(
        pk__in=[x["associated_subscription_record"] for x in distinct_sr_pv_combos]
    )
    pvs = PlanVersion.objects.filter(
        pk__in=[x["associated_plan_version"] for x in distinct_sr_pv_combos]
    )
    for combo in distinct_sr_pv_combos:
        sr = srs.get(pk=combo["associated_subscription_record"])
        pv = pvs.get(pk=combo["associated_plan_version"])
        if pv.price_adjustment:
            plan_amount = (
                invoice.line_items.filter(
                    associated_subscription_record=sr,
                    associated_plan_version=pv,
                ).aggregate(tot=Sum("subtotal"))["tot"]
                or 0
            )
            price_adj_name = str(pv.price_adjustment)
            new_amount_due = pv.price_adjustment.apply(plan_amount)
            new_amount_due = max(new_amount_due, Decimal(0))
            difference = new_amount_due - plan_amount
            if difference != 0:
                InvoiceLineItem.objects.create(
                    name=f"{pv.plan.plan_name} v{pv.version} {price_adj_name}",
                    start_date=invoice.issue_date,
                    end_date=invoice.issue_date,
                    quantity=None,
                    subtotal=difference,
                    billing_type=FLAT_FEE_BILLING_TYPE.IN_ARREARS,
                    chargeable_item_type=CHARGEABLE_ITEM_TYPE.PLAN_ADJUSTMENT,
                    invoice=invoice,
                    associated_subscription_record=sr,
                    organization=sr.organization,
                )


def charge_next_plan_flat_fee(
    subscription_record, next_subscription_record, next_bp, invoice
):
    from metering_billing.models import AddOnSpecification, InvoiceLineItem

    if next_bp.plan.addon_spec:
        charge_in_advance = (
            next_bp.plan.addon_spec.recurring_flat_fee_timing
            == AddOnSpecification.RecurringFlatFeeTiming.IN_ADVANCE
        )
        next_bp_duration = find_next_billing_plan(
            subscription_record.parent
        ).plan.plan_duration
        name = f"{next_bp.plan.plan_name} Flat Fee - Next Period [Add-on]"
    else:
        charge_in_advance = (
            next_bp.flat_fee_billing_type == FLAT_FEE_BILLING_TYPE.IN_ADVANCE
        )
        next_bp_duration = next_bp.plan.plan_duration
        name = f"{next_bp.plan.plan_name} v{next_bp.version} Flat Fee - Next Period"
    if charge_in_advance and next_bp.flat_rate > 0:
        new_start = date_as_min_dt(subscription_record.end_date + relativedelta(days=1))
        InvoiceLineItem.objects.create(
            name=name,
            start_date=new_start,
            end_date=calculate_end_date(next_bp_duration, new_start),
            quantity=1,
            subtotal=next_bp.flat_rate,
            billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
            chargeable_item_type=CHARGEABLE_ITEM_TYPE.RECURRING_CHARGE,
            invoice=invoice,
            associated_subscription_record=next_subscription_record,
            associated_plan_version=next_bp,
            organization=subscription_record.organization,
        )


def create_next_subscription_record(subscription_record, next_bp):
    from metering_billing.models import SubscriptionRecord

    subrec_dict = {
        "organization": subscription_record.organization,
        "customer": subscription_record.customer,
        "billing_plan": next_bp,
        "start_date": date_as_min_dt(
            subscription_record.end_date + relativedelta(days=1)
        ),
        "is_new": False,
    }
    next_subscription_record = SubscriptionRecord.objects.create(**subrec_dict)
    for f in subscription_record.filters.all():
        next_subscription_record.filters.add(f)
    return next_subscription_record


def check_subscription_record_renews(subscription, subscription_record):
    if subscription_record.end_date < subscription.end_date:
        return False
    if subscription_record.parent is None:
        return subscription_record.auto_renew
    else:
        return subscription_record.auto_renew and subscription_record.parent.auto_renew


def calculate_subscription_record_flat_fees(subscription_record, billing_plan, invoice):
    from metering_billing.models import InvoiceLineItem

    amt_already_billed = subscription_record.amount_already_invoiced()

    start = subscription_record.start_date
    end = subscription_record.end_date
    if subscription_record.flat_fee_behavior == FLAT_FEE_BEHAVIOR.PRORATE:
        proration_factor = (
            end - start
        ).total_seconds() / subscription_record.unadjusted_duration_seconds
        flat_fee_due = billing_plan.flat_rate * convert_to_decimal(proration_factor)
    elif subscription_record.flat_fee_behavior is not FLAT_FEE_BEHAVIOR.REFUND:
        flat_fee_due = Decimal(0)
    else:
        flat_fee_due = billing_plan.flat_rate
    if abs(float(amt_already_billed) - float(flat_fee_due)) < 0.01:
        pass
    else:
        billing_plan_name = billing_plan.plan.plan_name
        billing_plan_version = billing_plan.version
        if flat_fee_due > 0:
            InvoiceLineItem.objects.create(
                name=f"{billing_plan_name} v{billing_plan_version} Prorated Flat Fee",
                start_date=convert_to_datetime(start, date_behavior="min"),
                end_date=convert_to_datetime(end, date_behavior="max"),
                quantity=1,
                subtotal=flat_fee_due,
                billing_type=billing_plan.flat_fee_billing_type,
                chargeable_item_type=CHARGEABLE_ITEM_TYPE.RECURRING_CHARGE,
                invoice=invoice,
                associated_subscription_record=subscription_record,
                associated_plan_version=billing_plan,
                organization=subscription_record.organization,
            )
        if amt_already_billed > 0:
            InvoiceLineItem.objects.create(
                name=f"{billing_plan_name} v{billing_plan_version} Flat Fee Already Invoiced",
                start_date=invoice.issue_date,
                end_date=invoice.issue_date,
                quantity=1,
                subtotal=-amt_already_billed,
                billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
                chargeable_item_type=CHARGEABLE_ITEM_TYPE.RECURRING_CHARGE,
                invoice=invoice,
                associated_subscription_record=subscription_record,
                associated_plan_version=billing_plan,
                organization=subscription_record.organization,
            )


def find_next_billing_plan(subscription_record):
    if subscription_record.billing_plan.transition_to:
        next_bp = subscription_record.billing_plan.transition_to.display_version
    elif subscription_record.billing_plan.replace_with:
        next_bp = subscription_record.billing_plan.replace_with
    else:
        next_bp = subscription_record.billing_plan
    return next_bp


def apply_taxes(invoice, customer, organization):
    """
    Apply taxes to an invoice
    """
    from metering_billing.models import Invoice, InvoiceLineItem

    if invoice.payment_status == Invoice.PaymentStatus.PAID:
        return
    if customer.tax_rate is None and organization.tax_rate is None:
        return
    associated_subscription_records = invoice.line_items.values_list(
        "associated_subscription_record", flat=True
    ).distinct()
    for sr in associated_subscription_records:
        current_subtotal = (
            invoice.line_items.filter(associated_subscription_record=sr).aggregate(
                tot=Sum("subtotal")
            )["tot"]
            or 0
        )
        if customer.tax_rate is not None:
            tax_rate = customer.tax_rate
        elif organization.tax_rate is not None:
            tax_rate = organization.tax_rate
        name = f"Tax - {round(tax_rate, 2)}%"
        tax_amount = current_subtotal * (tax_rate / Decimal(100))
        InvoiceLineItem.objects.create(
            name=name,
            start_date=invoice.issue_date,
            end_date=invoice.issue_date,
            quantity=None,
            subtotal=tax_amount,
            billing_type=FLAT_FEE_BILLING_TYPE.IN_ARREARS,
            chargeable_item_type=CHARGEABLE_ITEM_TYPE.TAX,
            invoice=invoice,
            organization=invoice.organization,
            associated_subscription_record_id=sr,
        )


def apply_customer_balance_adjustments(invoice, customer, organization, draft):
    """
    Apply customer balance adjustments to an invoice
    """
    from metering_billing.models import (
        CustomerBalanceAdjustment,
        Invoice,
        InvoiceLineItem,
    )

    issue_date = invoice.issue_date
    issue_date_fmt = issue_date.strftime("%Y-%m-%d")
    if invoice.payment_status == Invoice.PaymentStatus.PAID or draft:
        return
    subtotal = invoice.line_items.aggregate(tot=Sum("subtotal"))["tot"] or 0
    if subtotal < 0:
        InvoiceLineItem.objects.create(
            name="Balance Adjustment [CREDIT]",
            start_date=invoice.issue_date,
            end_date=invoice.issue_date,
            quantity=None,
            subtotal=-subtotal,
            billing_type=FLAT_FEE_BILLING_TYPE.IN_ARREARS,
            chargeable_item_type=CHARGEABLE_ITEM_TYPE.CUSTOMER_ADJUSTMENT,
            invoice=invoice,
            organization=organization,
        )
        if not draft:
            CustomerBalanceAdjustment.objects.create(
                organization=organization,
                customer=customer,
                amount=-subtotal,
                description=f"Balance increase from invoice {invoice.invoice_number} generated on {issue_date_fmt}",
                created=issue_date,
                effective_at=issue_date,
                status=CUSTOMER_BALANCE_ADJUSTMENT_STATUS.ACTIVE,
            )
    elif subtotal > 0:
        customer_balance = CustomerBalanceAdjustment.get_pricing_unit_balance(customer)
        balance_adjustment = min(subtotal, customer_balance)
        if balance_adjustment > 0:
            if draft:
                leftover = 0
            else:
                leftover = CustomerBalanceAdjustment.draw_down_amount(
                    customer,
                    balance_adjustment,
                    description=f"Balance decrease from invoice {invoice.invoice_number} generated on {issue_date_fmt}",
                )
            if -balance_adjustment + leftover != 0:
                InvoiceLineItem.objects.create(
                    name="Balance Adjustment [DEBIT]",
                    start_date=issue_date,
                    end_date=issue_date,
                    quantity=None,
                    subtotal=-balance_adjustment + leftover,
                    billing_type=FLAT_FEE_BILLING_TYPE.IN_ARREARS,
                    chargeable_item_type=CHARGEABLE_ITEM_TYPE.CUSTOMER_ADJUSTMENT,
                    invoice=invoice,
                    organization=organization,
                )


def generate_balance_adjustment_invoice(balance_adjustment, draft=False):
    """
    Generate an invoice for a subscription.
    """
    from metering_billing.models import Invoice, InvoiceLineItem, OrganizationSetting
    from metering_billing.tasks import generate_invoice_pdf_async

    issue_date = balance_adjustment.created
    customer = balance_adjustment.customer
    organization = balance_adjustment.organization
    # create kwargs for invoice
    invoice_kwargs = {
        "issue_date": issue_date,
        "organization": organization,
        "customer": customer,
        "payment_status": Invoice.PaymentStatus.DRAFT
        if draft
        else Invoice.PaymentStatus.UNPAID,
        "currency": balance_adjustment.amount_paid_currency,
    }
    due_date = issue_date
    grace_period_setting = OrganizationSetting.objects.filter(
        organization=organization,
        setting_name=ORGANIZATION_SETTING_NAMES.PAYMENT_GRACE_PERIOD,
        setting_group=ORGANIZATION_SETTING_GROUPS.BILLING,
    ).first()
    if grace_period_setting:
        due_date += relativedelta(
            days=int(grace_period_setting.setting_values["value"])
        )
    invoice_kwargs["due_date"] = due_date
    # Create the invoice
    invoice = Invoice.objects.create(**invoice_kwargs)

    # Create the invoice line item
    InvoiceLineItem.objects.create(
        name="Balance Adjustment Grant",
        start_date=issue_date,
        end_date=issue_date,
        quantity=balance_adjustment.amount,
        subtotal=balance_adjustment.amount_paid,
        billing_type=FLAT_FEE_BILLING_TYPE.IN_ARREARS,
        chargeable_item_type=CHARGEABLE_ITEM_TYPE.ONE_TIME_CHARGE,
        invoice=invoice,
        organization=organization,
    )

    apply_taxes(invoice, customer, organization)

    invoice.cost_due = invoice.line_items.aggregate(tot=Sum("subtotal"))["tot"] or 0
    if abs(invoice.cost_due) < 0.01 and not draft:
        invoice.payment_status = Invoice.PaymentStatus.PAID
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
        generate_invoice_pdf_async.delay(invoice.pk)
        invoice_created_webhook(invoice, organization)

    return invoice
    return invoice
