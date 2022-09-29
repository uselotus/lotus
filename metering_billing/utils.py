import collections
import datetime
import math
from datetime import timezone
from decimal import ROUND_DOWN, ROUND_UP, Decimal

from dateutil import parser
from dateutil.relativedelta import relativedelta
from django.db.models import Count, F, FloatField, Max, Sum
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast

from metering_billing.models import Event, Subscription
from metering_billing.serializers.model_serializers import (
    BillingPlanReadSerializer,
    PlanComponentReadSerializer,
)

rev_calc_to_agg_keyword = {
    "daily": "date",
    "monthly": "month",
    "yearly": "year",
}

stateful_agg_period_to_agg_keyword = {
    "day": "date",
    "hour": "hour",
}

# DAILY USAGE + REVENUE METHODS
def get_metric_usage(
    metric,
    query_start_date=None,
    query_end_date=None,
    customer=None,
    time_period_agg=None,
):
    filter_kwargs = {
        "organization": metric.organization,
        "event_name": metric.event_name,
    }
    values_kwargs = {"org": F("organization")}
    annotate_kwargs = {}
    # handle date range
    if query_start_date is not None:
        filter_kwargs["time_created__date__gte"] = query_start_date
    if query_end_date is not None:
        filter_kwargs["time_created__date__lte"] = query_end_date
    # do it in aggregate, or by customer
    if customer is not None:
        filter_kwargs["customer"] = customer
    else:
        values_kwargs["customer_name"] = F("customer__name")
    # do it day-by-day, or aggregated over the query period
    if time_period_agg:
        values_kwargs["time_created_quantized"] = F(f"time_created__{time_period_agg}")
    # try filtering by the metric's desired property_name
    if metric.property_name is not None and metric.property_name != "":
        filter_kwargs["properties__has_key"] = metric.property_name
    # input the correct aggregation type
    if metric.aggregation_type == "count":
        annotate_kwargs["usage_qty"] = Count("pk")
    elif metric.aggregation_type == "unique":
        annotate_kwargs["usage_qty"] = Count(
            f"properties__{metric.property_name}", distinct=True
        )
    else:
        aggregation_type = Sum if metric.aggregation_type == "sum" else Max
        annotate_kwargs["usage_qty"] = aggregation_type(
            Cast(KeyTextTransform(metric.property_name, "properties"), FloatField())
        )
    query = (
        Event.objects.filter(**filter_kwargs)
        .values(**values_kwargs)
        .annotate(**annotate_kwargs)
    )

    usage_summary = query
    for x in usage_summary:
        x["usage_qty"] = Decimal(x["usage_qty"]).quantize(
            Decimal(".0000000001"), rounding=ROUND_UP
        )

    return usage_summary


def calculate_total_pc_revenue(plan_component, units_usage):
    if plan_component.cost_per_batch == 0 or plan_component.cost_per_batch is None:
        return 0
    subtotal_usage = max(units_usage - plan_component.free_metric_units, 0)
    metric_batches = math.ceil(subtotal_usage / plan_component.metric_units_per_batch)
    subtotal_cost = (metric_batches * plan_component.cost_per_batch).amount
    return subtotal_cost


def calculate_per_period_pc_revenue_for_additive_metric(
    plan_component, units_usage_per_day, query_start, query_end, time_period_agg
):
    usage_before_query_start = list(
        x["usage_qty"]
        for x in units_usage_per_day
        if x["time_created_quantized"] < query_start
    )
    units_usage_before_query_start = (
        sum(usage_before_query_start) if len(usage_before_query_start) > 0 else 0
    )
    units_usage_query = [
        (x["usage_qty"], x["time_created_quantized"])
        for x in units_usage_per_day
        if x["time_created_quantized"] >= query_start
        and x["time_created_quantized"] <= query_end
    ]
    free_units_usage = plan_component.free_metric_units
    free_units_usage_left = max(free_units_usage - units_usage_before_query_start, 0)
    if time_period_agg == "date":
        plan_periods = list(dates_bwn_twodates(query_start, query_end))
    else:
        raise NotImplementedError(
            f"Time period aggregation {time_period_agg} not supported"
        )
    period_revenue_dict = {
        tc_q: {"revenue": Decimal(0), "usage_qty": 0} for tc_q in plan_periods
    }
    for usg_qty, tc_q in units_usage_query:
        period_revenue_dict[tc_q]["usage_qty"] += usg_qty
    if plan_component.cost_per_batch == 0 or plan_component.cost_per_batch is None:
        return period_revenue_dict
    remainder_billable_units = 0
    for qty, tc_q in units_usage_query:
        qty = Decimal(qty)
        billable_units = max(qty - free_units_usage_left + remainder_billable_units, 0)
        billable_batches = billable_units // plan_component.metric_units_per_batch
        remainder_billable_units = (
            billable_units - billable_batches * plan_component.metric_units_per_batch
        )
        free_units_usage_left = max(0, free_units_usage_left - qty)
        usage_revenue = (billable_batches * plan_component.cost_per_batch).amount
        period_revenue_dict[tc_q]["revenue"] = usage_revenue
    return period_revenue_dict


def calculate_per_period_pc_revenue_for_cliff_metric(
    plan_component, units_usage_per_day, query_start, query_end, time_period_agg
):
    # determine what the maximum usage was IN the plan, but OUTSIDE the query
    periods_before_query_start = list(
        x["usage_qty"]
        for x in units_usage_per_day
        if x["time_created_quantized"] < query_start
    )
    units_usage_before_query_start = (
        max(periods_before_query_start) if len(periods_before_query_start) > 0 else 0
    )
    units_usage_before_query_start = Decimal(units_usage_before_query_start)
    periods_after_query_end = list(
        x["usage_qty"]
        for x in units_usage_per_day
        if x["time_created_quantized"] > query_end
    )
    units_usage_after_query_end = (
        max(periods_after_query_end) if len(periods_after_query_end) > 0 else 0
    )
    units_usage_after_query_end = Decimal(units_usage_after_query_end)
    max_units_usage_outside_query = max(
        units_usage_before_query_start, units_usage_after_query_end
    )
    # go through each day in the query and determine the usage revenue... x if max, 0 otherwise
    units_usage_query = [
        (x["usage_qty"], x["time_created_quantized"])
        for x in units_usage_per_day
        if x["time_created_quantized"] >= query_start
        and x["time_created_quantized"] <= query_end
    ]
    max_units_usage_query = (
        max(x[0] for x in units_usage_query) if len(units_usage_query) > 0 else 0
    )
    if time_period_agg == "date":
        plan_periods = list(dates_bwn_twodates(query_start, query_end))
    else:
        raise NotImplementedError(
            f"Time period aggregation {time_period_agg} not supported"
        )
    period_revenue_dict = {
        tc_q: {"revenue": Decimal(0), "usage_qty": 0} for tc_q in plan_periods
    }
    for usg_qty, tc_q in units_usage_query:
        period_revenue_dict[tc_q]["usage_qty"] += usg_qty
    if (
        max_units_usage_query < max_units_usage_outside_query
        or max_units_usage_query == 0
        or plan_component.cost_per_batch == 0
        or plan_component.cost_per_batch is None
    ):
        return period_revenue_dict
    for qty, tc_q in units_usage_query:
        qty = Decimal(qty)
        if qty > max_units_usage_outside_query and qty == max_units_usage_query:
            free_units_usage = plan_component.free_metric_units
            metric_batches = math.ceil(
                (qty - free_units_usage) / plan_component.metric_units_per_batch
            )
            usage_revenue = (metric_batches * plan_component.cost_per_batch).amount
            period_revenue_dict[tc_q]["revenue"] = usage_revenue
            break
    return period_revenue_dict


def calculate_stateful_pc_revenue(
    plan_component,
    units_usage,
    plan_start_date,
    plan_end_date,
    customer,
    stateful_agg_period,
    revenue_agg_period,
):
    metric = plan_component.billable_metric
    if stateful_agg_period == "date":
        plan_periods = list(dates_bwn_twodates(plan_start_date, plan_end_date))
    elif stateful_agg_period == "hour":
        plan_periods = list(hours_bwn_twodates(plan_start_date, plan_end_date))
    usage_revenue_dict = {x: {"usage": 0, "revenue": 0} for x in plan_periods}
    # sort all the events by date
    qs_periods = {}
    for x in units_usage:
        tc = x["time_created_quantized"]
        if tc not in qs_periods:
            qs_periods[tc] = []
        qs_periods[tc].append(x)
    # sicne stateful metrics carry over, we need to add the last usage from the previous period
    try:
        filter_kwargs = {
            "organization": metric.organization,
            "event_name": metric.event_name,
            "time_created__date__lt": plan_start_date,
            "customer": customer,
        }
        if metric.property_name is not None:
            filter_kwargs["properties__has_key"] = metric.property_name
        last_event = (
            Event.objects.filter(**filter_kwargs).order_by("-time_created").first()
        )
    except Event.DoesNotExist:
        last_event = None
    # for each day, calculate the usage and revenue
    for period in sorted(usage_revenue_dict.keys()):
        # optionally add the "last" event, and calculate effective usage
        period_events = qs_periods.get(period, [])
        if last_event is not None and len(period_events) == 0:
            period_events.append(last_event)
        period_events_ordered_asc = sorted(
            period_events, key=lambda x: x["time_created_quantized"]
        )
        if metric.aggregation_type == "max":
            usage = max([x["usage_qty"] for x in period_events], default=0)
        elif metric.aggregation_type == "last":
            usage = (
                period_events_ordered_asc[-1]["usage_qty"]
                if len(period_events_ordered_asc) > 0
                else 0
            )
        # calculate revenue
        if plan_component.cost_per_batch == 0 or plan_component.cost_per_batch is None:
            revenue = 0
        else:
            free_units_usage = plan_component.free_metric_units
            metric_batches = math.ceil(
                (max(usage - free_units_usage, 0))
                / plan_component.metric_units_per_batch
            )
            revenue = (metric_batches * plan_component.cost_per_batch).amount
        # add revenue and usage to the dict
        usage_revenue_dict[period] = {
            "revenue": revenue,
            "usage_qty": usage,
        }
        # update the last event
        if len(period_events_ordered_asc) > 0:
            last_event = period_events_ordered_asc[-1]
    if stateful_agg_period != revenue_agg_period:
        all_periods = list(usage_revenue_dict.keys())
        if revenue_agg_period == "date":
            agged_periods = set(x.date for x in all_periods)
            agged_periods = {p: {"revenue": 0, "usage_qty": {}} for p in agged_periods}
        else:
            raise NotImplementedError(
                f"Time period aggregation {revenue_agg_period} not supported"
            )
        for period in all_periods:
            if revenue_agg_period == "date":
                agged_period = period.date
            else:
                raise NotImplementedError(
                    f"Time period aggregation {revenue_agg_period} not supported"
                )
            agged_periods[agged_period]["revenue"] += usage_revenue_dict[period][
                "revenue"
            ]
            agged_periods[agged_period]["usage_qty"][period] = usage_revenue_dict[
                period
            ]["usage_qty"]
        usage_revenue_dict = agged_periods
    usage_revenue_dict = {str(k): v for k, v in usage_revenue_dict.items()}
    return usage_revenue_dict


def calculate_pc_usage_rev_for_stateful_metric(
    plan_component,
    billable_metric,
    customer,
    plan_start_date,
    plan_end_date,
    query_start,
    query_end,
    revenue_calc_period,
):
    stateful_agg_p = billable_metric.stateful_aggregation_period
    stateful_agg_p = stateful_agg_period_to_agg_keyword[stateful_agg_p]
    units_usage = get_metric_usage(
        billable_metric,
        query_start_date=query_start,
        query_end_date=query_end,
        customer=customer,
        time_period_agg=stateful_agg_p,
    )
    revenue_period_agg = rev_calc_to_agg_keyword.get(revenue_calc_period)
    usage_revenue_dict = calculate_stateful_pc_revenue(
        plan_component,
        units_usage,
        plan_start_date,
        plan_end_date,
        customer,
        stateful_agg_period=stateful_agg_p,
        revenue_agg_period=revenue_period_agg,
    )
    return usage_revenue_dict


def calculate_pc_usage_rev_for_aggregation_metric(
    plan_component,
    billable_metric,
    customer,
    plan_start_date,
    plan_end_date,
    query_start,
    query_end,
    revenue_calc_period,
):
    time_period_agg = rev_calc_to_agg_keyword.get(revenue_calc_period)
    units_usage = get_metric_usage(
        billable_metric,
        query_start_date=plan_start_date,
        query_end_date=plan_end_date,
        customer=customer,
        time_period_agg=time_period_agg,
    )
    if revenue_calc_period is not None:
        if billable_metric.aggregation_type == "max":
            usage_revenue_dict = calculate_per_period_pc_revenue_for_cliff_metric(
                plan_component, units_usage, query_start, query_end, time_period_agg
            )
        else:
            usage_revenue_dict = calculate_per_period_pc_revenue_for_additive_metric(
                plan_component, units_usage, query_start, query_end, time_period_agg
            )
    else:
        # this mean we only care about total revenue, don't need to break it out by x
        assert len(units_usage) <= 1, "Shouldn't have more than one row of usage"
        usg = units_usage[0]["usage_qty"] if len(units_usage) > 0 else 0
        usage_revenue_dict = {"usage_qty": usg, "revenue": 0}
        revenue = calculate_total_pc_revenue(
            plan_component, usage_revenue_dict["usage_qty"]
        )
        usage_revenue_dict["revenue"] = revenue
    return usage_revenue_dict


def calculate_sub_pc_usage_revenue(
    plan_component,
    billable_metric,
    customer,
    plan_start_date,
    plan_end_date,
    query_start=None,
    query_end=None,
    revenue_calc_period=None,
):
    # revenue calculation needs to be daily, monthly, yearly, or over the entire query
    assert revenue_calc_period in list(rev_calc_to_agg_keyword.keys()) + [
        None
    ], f"Can't calculate revenue over {revenue_calc_period} period"
    if query_start is None and query_end is None:
        # if we don't specify a query start or a query end, then we
        # assume we want something for the duration of plan only
        query_start = plan_start_date
        query_end = plan_end_date
    if type(plan_start_date) == str:
        plan_start_date = parser.parse(plan_start_date).date()
    if type(plan_end_date) == str:
        plan_end_date = parser.parse(plan_end_date).date()
    if type(query_start) == str:
        query_start = parser.parse(query_start).date()
    if type(query_end) == str:
        query_end = parser.parse(query_end).date()
    args_dict = {
        "plan_component": plan_component,
        "billable_metric": billable_metric,
        "customer": customer,
        "plan_start_date": plan_start_date,
        "plan_end_date": plan_end_date,
        "query_start": query_start,
        "query_end": query_end,
        "revenue_calc_period": revenue_calc_period,
    }
    if billable_metric.event_type == "stateful":
        usage_revenue_dict = calculate_pc_usage_rev_for_stateful_metric(**args_dict)
    else:
        usage_revenue_dict = calculate_pc_usage_rev_for_aggregation_metric(**args_dict)
    return usage_revenue_dict


# AGGREGATE USAGE + REVENUE METHODS
def get_subscription_usage_and_revenue(subscription):
    sub_dict = {}
    sub_dict["components"] = []
    # set up the billing plan for this subscription
    plan = subscription.billing_plan
    # set up other details of the subscription
    plan_start_date = subscription.start_date
    plan_end_date = subscription.end_date
    # extract other objects that we need when calculating usage
    customer = subscription.customer
    plan_components_qs = plan.components.all()
    # For each component of the plan, calculate usage/revenue
    for plan_component in plan_components_qs:
        plan_component_summary = calculate_sub_pc_usage_revenue(
            plan_component,
            plan_component.billable_metric,
            customer,
            plan_start_date,
            plan_end_date,
        )
        sub_dict["components"].append(plan_component_summary)
    sub_dict["usage_revenue_due"] = sum(
        component["revenue"] for component in sub_dict["components"]
    )
    sub_dict["flat_revenue_due"] = subscription.billing_plan.flat_rate.amount
    sub_dict["total_revenue_due"] = (
        sub_dict["flat_revenue_due"] + sub_dict["usage_revenue_due"]
    )
    del sub_dict["components"]
    return sub_dict


def get_customer_usage_and_revenue(customer):
    customer_subscriptions = (
        Subscription.objects.filter(
            customer=customer, status="active", organization=customer.organization
        )
        .select_related("customer")
        .prefetch_related("billing_plan__components")
        .prefetch_related("billing_plan__components__billable_metric")
        .select_related("billing_plan")
    )
    subscription_usages = {"subscriptions": []}
    for subscription in customer_subscriptions:
        sub_dict = get_subscription_usage_and_revenue(subscription)
        sub_dict["billing_plan_name"] = subscription.billing_plan.name
        subscription_usages["subscriptions"].append(sub_dict)

    return subscription_usages


def make_all_decimals_floats(json):
    if type(json) in [dict, list, Decimal, collections.OrderedDict]:
        for key, value in json.items():
            if isinstance(value, dict) or isinstance(value, collections.OrderedDict):
                make_all_decimals_floats(value)
            elif isinstance(value, list):
                for item in value:
                    make_all_decimals_floats(item)
            elif isinstance(value, Decimal):
                json[key] = float(value)


def years_bwn_twodates(start_date, end_date):
    years_btwn = relativedelta(end_date, start_date).years
    for n in range(years_btwn + 1):
        yield (start_date + relativedelta(years=n)).year


def months_bwn_twodates(start_date, end_date):
    months_btwn = (
        12 * relativedelta(end_date, start_date).years
        + relativedelta(end_date, start_date).months
    )
    for n in range(months_btwn + 1):
        next_date = start_date + relativedelta(months=n)
        yield (next_date.year, next_date.month)


def dates_bwn_twodates(start_date, end_date):
    days_btwn = (end_date - start_date).days
    for n in range(days_btwn + 1):
        yield start_date + relativedelta(days=n)


def hours_bwn_twodates(start_date, end_date):
    start_time = datetime.datetime.combine(
        start_date, datetime.time.min, tzinfo=timezone.utc
    )
    end_time = datetime.datetime.combine(
        end_date, datetime.time.max, tzinfo=timezone.utc
    )
    hours_btwn = abs(relativedelta(start_time, end_time).hours)
    for n in range(hours_btwn + 1):
        yield start_date + relativedelta(hours=n)
