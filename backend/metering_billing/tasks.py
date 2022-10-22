from __future__ import absolute_import, unicode_literals

import datetime
from datetime import timezone
from decimal import Decimal

import posthog
from celery import shared_task
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from metering_billing.invoice import generate_invoice
from metering_billing.models import (
    Backtest,
    Event,
    Invoice,
    Organization,
    PlanComponent,
    Subscription,
)
from metering_billing.serializers.backtest_serializers import (
    AllSubstitutionResultsSerializer,
)
from metering_billing.utils import (
    dates_bwn_twodates,
    make_all_dates_times_strings,
    make_all_datetimes_dates,
    make_all_decimals_floats,
)
from metering_billing.utils.enums import (
    BACKTEST_STATUS,
    INVOICE_STATUS,
    SUBSCRIPTION_STATUS,
)
from metering_billing.view_utils import (
    get_subscription_usage_and_revenue,
    sync_payment_provider_customers,
)

EVENT_CACHE_FLUSH_COUNT = settings.EVENT_CACHE_FLUSH_COUNT
EVENT_CACHE_FLUSH_SECONDS = settings.EVENT_CACHE_FLUSH_SECONDS
POSTHOG_PERSON = settings.POSTHOG_PERSON


@shared_task
def calculate_invoice():
    # get ending subs
    now = datetime.date.today()
    ending_subscriptions = list(
        Subscription.objects.filter(status=SUBSCRIPTION_STATUS.ACTIVE, end_date__lt=now)
    )
    invoice_sub_ids_seen = Invoice.objects.filter(
        ~Q(payment_status=INVOICE_STATUS.DRAFT)
    ).values_list("subscription__subscription_id", flat=True)

    if len(invoice_sub_ids_seen) > 0:
        ended_subs_no_invoice = Subscription.objects.filter(
            status=SUBSCRIPTION_STATUS.ENDED, end_date__lt=now
        ).exclude(subscription_id__in=list(invoice_sub_ids_seen))
        ending_subscriptions.extend(ended_subs_no_invoice)

    # prefetch organization customer stripe keys
    # orgs_seen = set()
    # for sub in ending_subscriptions:
    #     org_pk = sub.organization.pk
    #     if org_pk not in orgs_seen:
    #         orgs_seen.add(org_pk)
    #         import_stripe_customers(sub.organization)
    # now generate invoices and new subs
    for old_subscription in ending_subscriptions:
        # Generate the invoice
        try:
            generate_invoice(old_subscription)
        except Exception as e:
            print(e)
            print(
                "Error generating invoice for subscription {}".format(old_subscription)
            )
            continue
        # End the old subscription and delete draft invoices
        already_ended = old_subscription.status == SUBSCRIPTION_STATUS.ENDED
        old_subscription.status = SUBSCRIPTION_STATUS.ENDED
        old_subscription.save()
        now = datetime.datetime.now(timezone.utc).date()
        Invoice.objects.filter(
            issue_date__lt=now, payment_status=INVOICE_STATUS.DRAFT
        ).delete()
        # Renew the subscription
        if old_subscription.auto_renew and not already_ended:
            if old_subscription.auto_renew_billing_plan:
                new_bp = old_subscription.auto_renew_billing_plan
            else:
                new_bp = old_subscription.billing_plan
            # if we'e scheduled this plan for deletion, check if its still active in subs
            # otherwise just renew with the new plan
            if new_bp.scheduled_for_deletion:
                replacement_bp = new_bp.replacement_billing_plan
                num_with_bp = Subscription.objects.filter(
                    status=SUBSCRIPTION_STATUS.ACTIVE, billing_plan=new_bp
                ).count()
                if num_with_bp == 0:
                    new_bp.delete()
                new_bp = replacement_bp
            subscription_kwargs = {
                "organization": old_subscription.organization,
                "customer": old_subscription.customer,
                "billing_plan": new_bp,
                "start_date": old_subscription.end_date + relativedelta(days=+1),
                "auto_renew": True,
                "is_new": False,
            }
            sub = Subscription.objects.create(**subscription_kwargs)
            if new_bp.pay_in_advance:
                sub.flat_fee_already_billed = new_bp.flat_rate
            if sub.start_date <= now <= sub.end_date:
                sub.status = SUBSCRIPTION_STATUS.ACTIVE
            else:
                sub.status = SUBSCRIPTION_STATUS.ENDED
            sub.save()


@shared_task
def start_subscriptions():
    now = datetime.date.today()
    starting_subscriptions = Subscription.objects.filter(
        status=SUBSCRIPTION_STATUS.NOT_STARTED, start_date__lte=now
    )
    for new_subscription in starting_subscriptions:
        new_subscription.status = SUBSCRIPTION_STATUS.ACTIVE
        new_subscription.save()


@shared_task
def update_invoice_status():
    incomplete_invoices = Invoice.objects.filter(
        Q(payment_status=INVOICE_STATUS.UNPAID)
    )
    for incomplete_invoice in incomplete_invoices:
        pass
        # pi_id = incomplete_invoice.external_payment_obj_id
        # if pi_id is not None:
        #     try:
        #         pi = stripe.PaymentIntent.retrieve(pi_id)
        #     except Exception as e:
        #         print(e)
        #         print("Error retrieving payment intent {}".format(pi_id))
        #         continue
        #     if pi.status == "succeeded":
        #         incomplete_invoice.payment_status = INVOICE_STATUS.PAID
        #         incomplete_invoice.save()
        #         posthog.capture(
        #             POSTHOG_PERSON
        #             if POSTHOG_PERSON
        #             else incomplete_invoice.organization["company_name"],
        #             "invoice_status_succeeded",
        #         )


@shared_task
def write_batch_events_to_db(events_list):
    event_obj_list = [Event(**dict(event)) for event in events_list]
    Event.objects.bulk_create(event_obj_list)


@shared_task
def posthog_capture_track(organization_pk, len_sent_events, len_ingested_events):
    org = Organization.objects.get(pk=organization_pk)
    posthog.capture(
        POSTHOG_PERSON if POSTHOG_PERSON else org.company_name,
        "track_event",
        {"sent_events": len_sent_events, "ingested_events": len_ingested_events},
    )


@shared_task
def check_event_cache_flushed():
    cache_tup = cache.get("events_to_insert")
    now = datetime.datetime.now(timezone.utc).astimezone()
    cached_events, cached_idems, last_flush_dt = (
        cache_tup if cache_tup else ([], set(), now)
    )
    time_since_last_flush = (now - last_flush_dt).total_seconds()
    if (
        len(cached_events) >= EVENT_CACHE_FLUSH_COUNT
        or time_since_last_flush >= EVENT_CACHE_FLUSH_SECONDS
    ):
        write_batch_events_to_db.delay(cached_events)
        cached_events = []
        cached_idems = set()
        cache.set("events_to_insert", (cached_events, cached_idems, now), None)


@shared_task
def sync_payment_provider_customers_all_orgs():
    for org in Organization.objects.all():
        sync_payment_provider_customers(org)


@shared_task
def run_backtest(backtest_id):
    backtest = Backtest.objects.get(backtest_id=backtest_id)
    backtest_substitutions = backtest.backtest_substitutions.all()
    queries = [Q(billing_plan=x.original_plan) for x in backtest_substitutions]
    query = queries.pop()
    for item in queries:
        query |= item
    all_subs_time_period = (
        Subscription.objects.filter(
            query,
            start_date__lte=backtest.end_date,
            end_date__gte=backtest.start_date,
            end_date__lte=backtest.end_date,
            organization=backtest.organization,
        )
        .prefetch_related("billing_plan")
        .prefetch_related("billing_plan__components")
    )
    all_results = {
        "substitution_results": [],
    }
    for subst in backtest_substitutions:
        outer_results = {
            "substitution_name": f"{subst.original_plan.name} --> {subst.new_plan.name}",
            "original_plan": {
                "plan_name": subst.original_plan.name,
                "plan_id": subst.original_plan.version_id,
                "plan_revenue": Decimal(0),
            },
            "new_plan": {
                "plan_name": subst.new_plan.name,
                "plan_id": subst.new_plan.version_id,
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
            old_usage_revenue = get_subscription_usage_and_revenue(sub)
            # cumulative revenue
            inner_results["cumulative_revenue"][end_date][
                "original_plan_revenue"
            ] += old_usage_revenue["total_revenue_due"]
            # customer revenue
            inner_results["top_customers"][customer][
                "original_plan_revenue"
            ] += old_usage_revenue["total_revenue_due"]
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
                ] += sum(
                    [info_dict["revenue"] for _, info_dict in component_dict.items()]
                )
            if "flat_fees" not in inner_results["revenue_by_metric"]:
                inner_results["revenue_by_metric"]["flat_fees"] = {
                    "original_plan_revenue": Decimal(0),
                    "new_plan_revenue": Decimal(0),
                }
            inner_results["revenue_by_metric"]["flat_fees"][
                "original_plan_revenue"
            ] += old_usage_revenue["flat_revenue_due"]
            ## PROCESS NEW SUB
            sub.billing_plan = subst.new_plan
            sub.save()
            new_usage_revenue = get_subscription_usage_and_revenue(sub)
            # revert it so we don't accidentally change the past lol
            sub.billing_plan = subst.original_plan
            sub.save()
            # cumulative revenue
            inner_results["cumulative_revenue"][end_date][
                "new_plan_revenue"
            ] += new_usage_revenue["total_revenue_due"]
            # customer revenue
            inner_results["top_customers"][customer][
                "new_plan_revenue"
            ] += new_usage_revenue["total_revenue_due"]
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
                ] += sum(
                    [info_dict["revenue"] for _, info_dict in component_dict.items()]
                )
            inner_results["revenue_by_metric"]["flat_fees"][
                "new_plan_revenue"
            ] += new_usage_revenue["flat_revenue_due"]
        # change cumulative revenue to be cumulative and in fronted format
        cum_rev_dict_list = []
        cum_rev = inner_results.pop("cumulative_revenue")
        cum_rev_lst = sorted(cum_rev.items(), key=lambda x: x[0], reverse=True)
        print(cum_rev_lst)
        print("early_date", cum_rev_lst[-1][0], "late_date", cum_rev_lst[0][0])
        every_date = list(dates_bwn_twodates(cum_rev_lst[-1][0], cum_rev_lst[0][0]))
        print("len_all_dates", len(every_date))
        date, rev_dict = cum_rev_lst.pop(-1)
        last_dict = {**rev_dict, "date": date}
        for date in every_date:
            if (
                date < cum_rev_lst[-1][0]
            ):  # have not reached the next data point yet, dont add
                new_dict = last_dict.copy()
                new_dict["date"] = date
            elif date == cum_rev_lst[-1][0]:  # have reached the next data point, add it
                date, rev_dict = cum_rev_lst.pop()
                new_dict = {**rev_dict, "date": date}
                new_dict["original_plan_revenue"] += last_dict["original_plan_revenue"]
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
            top_cust.items(), key=lambda x: x[1]["original_plan_revenue"], reverse=True
        )[:5]
        top_cust_dict["original_plan_revenue"] = [
            {
                "customer_id": customer.customer_id,
                "customer_name": customer.name,
                "value": rev_dict["original_plan_revenue"],
            }
            for customer, rev_dict in top_original
        ]
        top_new = sorted(
            top_cust.items(), key=lambda x: x[1]["new_plan_revenue"], reverse=True
        )[:5]
        top_cust_dict["new_plan_revenue"] = [
            {
                "customer_id": customer.customer_id,
                "customer_name": customer.name,
                "value": rev_dict["new_plan_revenue"],
            }
            for customer, rev_dict in top_new
        ]
        all_pct_change = []
        for customer, rev_dict in top_cust.items():
            try:
                pct_change = (
                    rev_dict["new_plan_revenue"] / rev_dict["original_plan_revenue"] - 1
                )
            except ZeroDivisionError:
                pct_change = None
            all_pct_change.append((customer, pct_change))
        all_pct_change = sorted(
            [tup for tup in all_pct_change if tup[1] is not None], key=lambda x: x[1]
        )
        top_cust_dict["biggest_pct_increase"] = [
            {
                "customer_id": customer.customer_id,
                "customer_name": customer.name,
                "value": pct_change,
            }
            for customer, pct_change in all_pct_change[-5:]
        ][::-1]
        top_cust_dict["biggest_pct_decrease"] = [
            {
                "customer_id": customer.customer_id,
                "customer_name": customer.name,
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
        except ZeroDivisionError:
            outer_results["pct_revenue_change"] = None
        all_results["substitution_results"].append(outer_results)
    all_results["original_plans_revenue"] = sum(
        x["original_plan"]["plan_revenue"] for x in all_results["substitution_results"]
    )
    all_results["new_plans_revenue"] = sum(
        x["new_plan"]["plan_revenue"] for x in all_results["substitution_results"]
    )
    try:
        all_results["pct_revenue_change"] = (
            all_results["new_plans_revenue"] / all_results["original_plans_revenue"] - 1
        )
    except ZeroDivisionError:
        all_results["pct_revenue_change"] = None
    all_results = make_all_decimals_floats(all_results)
    all_results = make_all_datetimes_dates(all_results)
    all_results = make_all_dates_times_strings(all_results)
    serializer = AllSubstitutionResultsSerializer(data=all_results)
    try:
        serializer.is_valid(raise_exception=True)
    except:
        print("errors", serializer.errors)
        print("all results", all_results)
        raise Exception
    results = make_all_dates_times_strings(serializer.validated_data)
    backtest.backtest_results = results
    backtest.status = BACKTEST_STATUS.COMPLETED
    backtest.save()
