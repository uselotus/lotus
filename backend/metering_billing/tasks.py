import logging
from decimal import Decimal, InvalidOperation

import pytz
from celery import shared_task
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db.models import Q
from metering_billing.payment_processors import PAYMENT_PROCESSOR_MAP
from metering_billing.serializers.backtest_serializers import (
    AllSubstitutionResultsSerializer,
)
from metering_billing.serializers.serializer_utils import PlanVersionUUIDField
from metering_billing.utils import (
    date_as_max_dt,
    date_as_min_dt,
    dates_bwn_two_dts,
    make_all_dates_times_strings,
    make_all_datetimes_dates,
    make_all_decimals_floats,
    now_utc,
)
from metering_billing.utils.enums import (
    BACKTEST_STATUS,
    CUSTOMER_BALANCE_ADJUSTMENT_STATUS,
)
from metering_billing.webhooks import invoice_past_due_webhook

logger = logging.getLogger("django.server")
EVENT_CACHE_FLUSH_COUNT = settings.EVENT_CACHE_FLUSH_COUNT
EVENT_CACHE_FLUSH_SECONDS = settings.EVENT_CACHE_FLUSH_SECONDS
POSTHOG_PERSON = settings.POSTHOG_PERSON


@shared_task
def sync_all_crm_integrations():
    from metering_billing.models import UnifiedCRMOrganizationIntegration

    for integration in UnifiedCRMOrganizationIntegration.objects.all():
        integration.perform_sync()


@shared_task
def sync_single_organization_integrations(
    organization_integration_pk, crm_provider_values=None
):
    from metering_billing.models import UnifiedCRMOrganizationIntegration

    if crm_provider_values is None:
        crm_provider_values = UnifiedCRMOrganizationIntegration.CRMProvider.values
    for integration in UnifiedCRMOrganizationIntegration.objects.filter(
        pk=organization_integration_pk, crm_provider__in=crm_provider_values
    ):
        integration.perform_sync()


@shared_task
def update_subscription_filter_settings_task(org_pk, subscription_filter_keys):
    from metering_billing.models import Organization

    org = Organization.objects.get(pk=org_pk)
    org.update_subscription_filter_settings(subscription_filter_keys)


@shared_task
def generate_invoice_pdf_async(invoice_pk):
    from metering_billing.invoice_pdf import get_invoice_presigned_url
    from metering_billing.models import Invoice

    invoice = Invoice.objects.get(pk=invoice_pk)
    try:
        pdf_url_dict = get_invoice_presigned_url(invoice)
        pdf_url = pdf_url_dict.get("url")
    except Exception as e:
        logger.error("RAN INTO ERROR GENERATING PDF: {}".format(e))
        pdf_url = None

    invoice.invoice_pdf = pdf_url
    invoice.save()


@shared_task
def calculate_invoice():
    # GENERAL PHILOSOPHY: this task is for periodic maintenance of ending susbcriptions. We only end and re-start subscriptions when they're scheduled to end, if for some other reason they end early then it is up to the other process to handle the invoice creationg and .
    # get ending subs

    from metering_billing.invoice import generate_invoice
    from metering_billing.models import BillingRecord, Invoice, SubscriptionRecord

    now_minus_30 = now_utc() + relativedelta(
        minutes=-30
    )  # grace period of 30 minutes for sending events
    sub_records_to_bill = SubscriptionRecord.objects.filter(
        Q(end_date__lt=now_minus_30)
    )
    billing_records_to_bill = BillingRecord.objects.filter(
        Q(next_invoicing_date__lt=now_minus_30) & Q(fully_billed=False),
    )
    # Get a list of distinct subscription IDs from the billing records
    subscription_id_from_br = billing_records_to_bill.values_list(
        "subscription", flat=True
    ).distinct()
    subscription_id_from_sr = sub_records_to_bill.values_list(
        "id", flat=True
    ).distinct()
    # Get the subscription records for the subscriptions
    all_sub_records = SubscriptionRecord.objects.filter(
        Q(id__in=subscription_id_from_br) | Q(id__in=subscription_id_from_sr)
    ).prefetch_related(
        "customer",
        "organization",
        "billing_plan",
        "billing_plan__recurring_charges",
        "billing_plan__plan_components",
        "billing_plan__plan_components__billable_metric",
        "billing_plan__plan_components__tiers",
        "filters",
        "billing_records",
    )

    # now generate invoices and new subs
    cust_info = all_sub_records.values_list("customer", "organization").distinct()
    for customer_id, organization_id in cust_info:
        customer_subscription_records = all_sub_records.filter(customer_id=customer_id)
        # Generate the invoice
        try:
            generate_invoice(
                customer_subscription_records,
                charge_next_plan=True,
                generate_next_subscription_record=True,
            )
            now = now_utc()
        except Exception as e:
            logger.error(
                "Error generating invoice for subscription records {}. Error was {}".format(
                    [str(x) for x in customer_subscription_records], e
                )
            )
            continue
        # delete draft invoices
        Invoice.objects.filter(
            issue_date__lt=now,
            payment_status=Invoice.PaymentStatus.DRAFT,
            customer_id=customer_id,
            organization_id=organization_id,
        ).delete()


def refresh_alerts_inner():
    from metering_billing.models import UsageAlertResult

    # get all UsageAlertResults
    now = now_utc()
    UsageAlertResult.objects.filter(subscription_record__end_date__lt=now).delete()
    alert_results = UsageAlertResult.objects.filter(
        subscription_record__end_date__gte=now
    ).prefetch_related("alert", "subscription_record", "alert__metric")
    for alert_result in alert_results:
        alert_result.refresh()


@shared_task
def refresh_alerts():
    refresh_alerts_inner()


def prune_guard_table_inner():
    from metering_billing.models import IdempotenceCheck

    # get all UsageAlertResults
    thirty_three_days = now_utc() - relativedelta(days=33)
    IdempotenceCheck.objects.filter(time_created__lt=thirty_three_days).delete()


@shared_task
def prune_guard_table():
    prune_guard_table_inner()


@shared_task
def zero_out_expired_balance_adjustments():
    from metering_billing.models import CustomerBalanceAdjustment

    now = now_utc()
    expired_balance_adjustments = CustomerBalanceAdjustment.objects.filter(
        expires_at__lt=now,
        amount__gt=0,
        status=CUSTOMER_BALANCE_ADJUSTMENT_STATUS.ACTIVE,
    )
    for ba in expired_balance_adjustments:
        ba.zero_out(reason="expired")


@shared_task
def update_invoice_status():
    from metering_billing.models import Invoice

    incomplete_invoices = Invoice.objects.filter(
        Q(payment_status=Invoice.PaymentStatus.UNPAID),
        external_payment_obj_id__isnull=False,
    )
    for incomplete_invoice in incomplete_invoices:
        pp = incomplete_invoice.external_payment_obj_type
        if pp in PAYMENT_PROCESSOR_MAP and PAYMENT_PROCESSOR_MAP[pp].working():
            organization = incomplete_invoice.organization
            status = PAYMENT_PROCESSOR_MAP[pp].update_payment_object_status(
                organization, incomplete_invoice.external_payment_obj_id
            )
            if status == Invoice.PaymentStatus.PAID:
                incomplete_invoice.payment_status = Invoice.PaymentStatus.PAID
                incomplete_invoice.save()


@shared_task
def run_backtest(backtest_id):
    from metering_billing.models import Backtest, PlanComponent, SubscriptionRecord

    try:
        backtest = Backtest.objects.get(backtest_id=backtest_id)
        backtest_substitutions = backtest.backtest_substitutions.all()
        queries = [Q(billing_plan=x.original_plan) for x in backtest_substitutions]
        query = queries.pop()
        start_date = date_as_min_dt(backtest.start_date, timezone=pytz.UTC)
        end_date = date_as_max_dt(backtest.end_date, timezone=pytz.UTC)
        for item in queries:
            query |= item
        all_subs_time_period = (
            SubscriptionRecord.objects.filter(
                query,
                start_date__lte=end_date,
                end_date__gte=start_date,
                end_date__lte=end_date,
                organization=backtest.organization,
            )
            .prefetch_related("billing_plan")
            .prefetch_related("billing_plan__plan_components")
        )
        all_results = {
            "substitution_results": [],
        }
        logger.info(f"Running backtest for {len(backtest_substitutions)} substitutions")
        for subst in backtest_substitutions:
            outer_results = {
                "substitution_name": f"{str(subst.original_plan)} --> {str(subst.new_plan)}",
                "original_plan": {
                    "plan_name": str(subst.original_plan),
                    "plan_id": PlanVersionUUIDField().to_representation(
                        subst.original_plan.version_id
                    ),
                    "plan_revenue": Decimal(0),
                },
                "new_plan": {
                    "plan_name": str(subst.new_plan),
                    "plan_id": PlanVersionUUIDField().to_representation(
                        subst.new_plan.version_id
                    ),
                    "plan_revenue": Decimal(0),
                },
            }
            # since we can have at most one new plan per old plan, the old plan uniquely
            # identifies the substitutiont
            subst_subscriptions = all_subs_time_period.filter(
                billing_plan=subst.original_plan
            )
            inner_results = {
                "cumulative_revenue": {},
                "revenue_by_metric": {},
                "top_customers": {},
            }
            for sub in subst_subscriptions:
                # create if not seen
                customer = sub.customer
                if customer not in inner_results["top_customers"]:
                    inner_results["top_customers"][customer] = {
                        "original_plan_revenue": Decimal(0),
                        "new_plan_revenue": Decimal(0),
                    }
                end_date = sub.end_date
                if end_date not in inner_results["cumulative_revenue"]:
                    inner_results["cumulative_revenue"][end_date] = {
                        "original_plan_revenue": Decimal(0),
                        "new_plan_revenue": Decimal(0),
                    }
                ## PROCESS OLD SUB
                old_usage_revenue = sub.get_usage_and_revenue()
                # cumulative revenue
                inner_results["cumulative_revenue"][end_date][
                    "original_plan_revenue"
                ] += old_usage_revenue["total_amount_due"]
                # customer revenue
                inner_results["top_customers"][customer][
                    "original_plan_revenue"
                ] += old_usage_revenue["total_amount_due"]
                # per metric
                for component_pk, component_dict in old_usage_revenue["components"]:
                    metric = PlanComponent.objects.get(pk=component_pk).billable_metric
                    metric_name = metric.billable_metric_name
                    if metric_name not in inner_results["revenue_by_metric"]:
                        inner_results["revenue_by_metric"][metric_name] = {
                            "original_plan_revenue": Decimal(0),
                            "new_plan_revenue": Decimal(0),
                        }
                    inner_results["revenue_by_metric"][metric_name][
                        "original_plan_revenue"
                    ] += component_dict["revenue"]
                if "flat_fees" not in inner_results["revenue_by_metric"]:
                    inner_results["revenue_by_metric"]["flat_fees"] = {
                        "original_plan_revenue": Decimal(0),
                        "new_plan_revenue": Decimal(0),
                    }
                inner_results["revenue_by_metric"]["flat_fees"][
                    "original_plan_revenue"
                ] += old_usage_revenue["flat_amount_due"]
                ## PROCESS NEW SUB
                sub.billing_plan = subst.new_plan
                sub.save()
                new_usage_revenue = sub.get_usage_and_revenue()
                # revert it so we don't accidentally change the past lol
                sub.billing_plan = subst.original_plan
                sub.save()
                # cumulative revenue
                inner_results["cumulative_revenue"][end_date][
                    "new_plan_revenue"
                ] += new_usage_revenue["total_amount_due"]
                # customer revenue
                inner_results["top_customers"][customer][
                    "new_plan_revenue"
                ] += new_usage_revenue["total_amount_due"]
                # per metric
                for component_pk, component_dict in new_usage_revenue["components"]:
                    metric = PlanComponent.objects.get(pk=component_pk).billable_metric
                    metric_name = metric.billable_metric_name
                    if metric_name not in inner_results["revenue_by_metric"]:
                        inner_results["revenue_by_metric"][metric_name] = {
                            "new_plan_revenue": Decimal(0),
                            "original_plan_revenue": Decimal(0),
                        }
                    inner_results["revenue_by_metric"][metric_name][
                        "new_plan_revenue"
                    ] += component_dict["revenue"]
                inner_results["revenue_by_metric"]["flat_fees"][
                    "new_plan_revenue"
                ] += new_usage_revenue["flat_amount_due"]
            # change cumulative revenue to be cumulative and in fronted format
            cum_rev_dict_list = []
            cum_rev = inner_results.pop("cumulative_revenue")
            cum_rev_lst = sorted(cum_rev.items(), key=lambda x: x[0], reverse=True)
            date_cumrev_list = []
            for date, cum_rev_dict in cum_rev_lst:
                date_cumrev_list.append((date.date(), cum_rev_dict))
            cum_rev_lst = date_cumrev_list
            try:
                every_date = list(
                    dates_bwn_two_dts(cum_rev_lst[-1][0], cum_rev_lst[0][0])
                )
            except IndexError:
                every_date = []
            if cum_rev_lst:
                date, rev_dict = cum_rev_lst.pop(-1)
                last_dict = {**rev_dict, "date": date}
            else:
                rev_dict = {}
            for date in every_date:
                if (
                    date < cum_rev_lst[-1][0]
                ):  # have not reached the next data point yet, dont add
                    new_dict = last_dict.copy()
                    new_dict["date"] = date
                elif (
                    date == cum_rev_lst[-1][0]
                ):  # have reached the next data point, add it
                    date, rev_dict = cum_rev_lst.pop()
                    new_dict = {**rev_dict, "date": date}
                    new_dict["original_plan_revenue"] += last_dict[
                        "original_plan_revenue"
                    ]
                    new_dict["new_plan_revenue"] += last_dict["new_plan_revenue"]
                    last_dict = new_dict
                else:
                    raise Exception("should not be greater than the most recent date")
                cum_rev_dict_list.append(new_dict)
            inner_results["cumulative_revenue"] = cum_rev_dict_list
            # change metric revenue to be in frontend format
            metric_rev = inner_results.pop("revenue_by_metric")
            metric_rev = [
                {**rev_dict, "metric_name": metric_name}
                for metric_name, rev_dict in metric_rev.items()
            ]
            inner_results["revenue_by_metric"] = metric_rev
            # change top customers to be in frontend format
            top_cust_dict = {}
            top_cust = inner_results.pop("top_customers")
            top_original = sorted(
                top_cust.items(),
                key=lambda x: x[1]["original_plan_revenue"],
                reverse=True,
            )[:5]
            top_cust_dict["original_plan_revenue"] = [
                {
                    "customer_id": customer.customer_id,
                    "customer_name": customer.customer_name,
                    "value": rev_dict.get("original_plan_revenue", 0),
                }
                for customer, rev_dict in top_original
            ]
            top_new = sorted(
                top_cust.items(), key=lambda x: x[1]["new_plan_revenue"], reverse=True
            )[:5]
            top_cust_dict["new_plan_revenue"] = [
                {
                    "customer_id": customer.customer_id,
                    "customer_name": customer.customer_name,
                    "value": rev_dict.get("new_plan_revenue", 0),
                }
                for customer, rev_dict in top_new
            ]
            all_pct_change = []
            for customer, rev_dict in top_cust.items():
                try:
                    pct_change = (
                        rev_dict.get("new_plan_revenue", 0)
                        / rev_dict.get("original_plan_revenue", 0)
                        - 1
                    )
                except ZeroDivisionError:
                    pct_change = None
                all_pct_change.append((customer, pct_change))
            all_pct_change = sorted(
                [tup for tup in all_pct_change if tup[1] is not None],
                key=lambda x: x[1],
            )
            top_cust_dict["biggest_pct_increase"] = [
                {
                    "customer_id": customer.customer_id,
                    "customer_name": customer.customer_name,
                    "value": pct_change,
                }
                for customer, pct_change in all_pct_change[-5:]
            ][::-1]
            top_cust_dict["biggest_pct_decrease"] = [
                {
                    "customer_id": customer.customer_id,
                    "customer_name": customer.customer_name,
                    "value": pct_change,
                }
                for customer, pct_change in all_pct_change[:5]
            ]
            inner_results["top_customers"] = top_cust_dict
            # now add the inner results to the outer results
            outer_results["results"] = inner_results
            try:
                outer_results["original_plan"]["plan_revenue"] = inner_results[
                    "cumulative_revenue"
                ][-1]["original_plan_revenue"]
            except IndexError:
                outer_results["original_plan"]["plan_revenue"] = Decimal(0)
            try:
                outer_results["new_plan"]["plan_revenue"] = inner_results[
                    "cumulative_revenue"
                ][-1]["new_plan_revenue"]
            except IndexError:
                outer_results["new_plan"]["plan_revenue"] = Decimal(0)
            try:
                outer_results["pct_revenue_change"] = (
                    outer_results["new_plan"]["plan_revenue"]
                    / outer_results["original_plan"]["plan_revenue"]
                    - 1
                )
            except (ZeroDivisionError, InvalidOperation):
                outer_results["pct_revenue_change"] = None
            all_results["substitution_results"].append(outer_results)
        all_results["original_plans_revenue"] = sum(
            x["original_plan"]["plan_revenue"]
            for x in all_results["substitution_results"]
        )
        all_results["new_plans_revenue"] = sum(
            x["new_plan"]["plan_revenue"] for x in all_results["substitution_results"]
        )
        try:
            all_results["pct_revenue_change"] = (
                all_results["new_plans_revenue"] / all_results["original_plans_revenue"]
                - 1
            )
        except (ZeroDivisionError, InvalidOperation):
            all_results["pct_revenue_change"] = None
        all_results = make_all_decimals_floats(all_results)
        all_results = make_all_datetimes_dates(all_results)
        all_results = make_all_dates_times_strings(all_results)
        serializer = AllSubstitutionResultsSerializer(data=all_results)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            logger.error("errors", serializer.errors, "all results", all_results)
            raise Exception
        results = make_all_dates_times_strings(serializer.validated_data)
        backtest.backtest_results = results
        backtest.status = BACKTEST_STATUS.COMPLETED
        backtest.save()
    except Exception as e:
        backtest.status = BACKTEST_STATUS.FAILED
        backtest.save()
        raise e


@shared_task
def run_generate_invoice(subscription_record_pk_set, **kwargs):
    from metering_billing.invoice import generate_invoice
    from metering_billing.models import SubscriptionRecord

    subscription_record_set = SubscriptionRecord.objects.filter(
        pk__in=subscription_record_pk_set
    )
    generate_invoice(subscription_record_set, **kwargs)


def import_customers_from_payment_processor_inner(payment_processor, organization_pk):
    from metering_billing.models import Organization

    organization = Organization.objects.get(pk=organization_pk)
    connector = PAYMENT_PROCESSOR_MAP[payment_processor]
    n = connector.import_customers(organization)

    return n


@shared_task
def import_customers_from_payment_processor(payment_processor, organization_pk):
    import_customers_from_payment_processor_inner(payment_processor, organization_pk)


def check_past_due_invoices_inner():
    from metering_billing.models import Invoice

    now = now_utc()
    incomplete_invoices = Invoice.objects.filter(
        Q(payment_status=Invoice.PaymentStatus.UNPAID),
        due_date__lt=now,
        invoice_past_due_webhook_sent=False,
    )
    for invoice in incomplete_invoices:
        invoice_past_due_webhook(invoice, invoice.organization)
        invoice.invoice_past_due_webhook_sent = True
        invoice.save()


@shared_task
def check_past_due_invoices():
    check_past_due_invoices_inner()
