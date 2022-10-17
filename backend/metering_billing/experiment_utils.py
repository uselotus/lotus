from __future__ import absolute_import, unicode_literals

from decimal import Decimal

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from metering_billing.invoice import generate_invoice
from metering_billing.models import Backtest, PlanComponent, Subscription
from metering_billing.payment_providers import PAYMENT_PROVIDER_MAP
from metering_billing.serializers.model_serializers import (
    AllSubstitutionResultsSerializer,
)
from metering_billing.utils import (
    BACKTEST_STATUS_TYPES,
    dates_bwn_twodates,
    make_all_dates_times_strings,
    make_all_datetimes_dates,
    make_all_decimals_floats,
)
from metering_billing.view_utils import get_subscription_usage_and_revenue


def calculate_backtest(backtest_id):
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
                "plan_id": subst.original_plan.billing_plan_id,
                "plan_revenue": Decimal(0),
            },
            "new_plan": {
                "plan_name": subst.new_plan.name,
                "plan_id": subst.new_plan.billing_plan_id,
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
    backtest.status = BACKTEST_STATUS_TYPES.COMPLETED
    backtest.save()
