import collections
import datetime
import math
from datetime import timezone
from decimal import ROUND_DOWN, ROUND_UP, Decimal
from enum import Enum

from dateutil import parser
from dateutil.relativedelta import relativedelta
from django.db.models import Count, F, FloatField, Max, Min, Sum
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast, Trunc

from metering_billing.models import Event, Subscription
from metering_billing.serializers.model_serializers import (
    BillingPlanReadSerializer,
    PlanComponentReadSerializer,
)


class RevenueCalcGranularity(Enum):
    DAILY = "day"
    TOTAL = None


rev_calc_to_agg_keyword = {
    "daily": "date",
    "monthly": "month",
    "yearly": "year",
}

stateful_agg_period_to_agg_keyword = {
    "day": "date",
    "hour": "hour",
}


def convert_to_decimal(value):
    return Decimal(value).quantize(Decimal(".0000000001"), rounding=ROUND_UP)


# DAILY USAGE + REVENUE METHODS
def get_metric_usage(
    metric,
    query_start_date=None,
    query_end_date=None,
    customer=None,
    time_period_agg=None,
    only_billable_usage=False,
):
    now = datetime.datetime.now(timezone.utc)
    filter_kwargs = {
        "organization": metric.organization,
        "event_name": metric.event_name,
        "time_created__lt": now,
    }
    pre_groupby_ann_kwargs = {}
    groupby_kwargs = {"customer_name": F("customer__name")}
    groupby_aggregation_kwargs = {}

    # handle date range
    if query_start_date is not None:
        filter_kwargs["time_created__date__gte"] = query_start_date
    if query_end_date is not None:
        filter_kwargs["time_created__date__lte"] = query_end_date
    # filter by customer if its a single one
    if customer is not None:
        filter_kwargs["customer"] = customer
    # do it day-by-day, or aggregated over the query period
    if time_period_agg:
        groupby_kwargs["time_created_quantized"] = Trunc(
            F("time_created"), time_period_agg
        )
    # try filtering by the metric's desired property_name
    if metric.property_name is not None and metric.property_name != "":
        filter_kwargs["properties__has_key"] = metric.property_name
        pre_groupby_ann_kwargs["property_value"] = F(
            f"properties__{metric.property_name}"
        )
    # input the correct aggregation type
    if metric.aggregation_type == "count":
        groupby_aggregation_kwargs["usage_qty"] = Count("pk")
    elif metric.aggregation_type == "unique":
        if only_billable_usage:
            # for unique, the billable usage only comes from the first time a person is seen
            # in the query period. First, we remove the group by day
            groupby_kwargs.pop("time_created_quantized", None)
            # then we group by the property value
            groupby_kwargs["property_value"] = F("property_value")
            # then we get the min time created for each property value
            groupby_aggregation_kwargs["time_created_quantized"] = Min(
                Trunc(F("time_created"), time_period_agg)
            )
        groupby_aggregation_kwargs["usage_qty"] = Count(
            F("property_value"), distinct=True
        )
    elif metric.aggregation_type == "max":
        if only_billable_usage:
            # for max, the billable usage only comes from the single max event in the query period
            # However, we also need the date of this event, and if we aggregate, we lose that info.
            # so what we do is we still aggregate per day, but after the query is executed just
            # order by the max value and take the first one
            # groupby_kwargs.pop("time_created_quantized", None)
            pass
        groupby_aggregation_kwargs["usage_qty"] = Max(
            Cast(F("property_value"), FloatField())
        )
    elif metric.aggregation_type == "last":
        # in the case of a last aggregation, we want to get the last event in the query period
        # our strategy will be to get rid of any groupbys and just use order by and distinct
        groupby_kwargs = {}
        groupby_aggregation_kwargs = {}
    else:
        # sum
        groupby_aggregation_kwargs["usage_qty"] = Sum(
            Cast(F("property_value"), FloatField())
        )

    query = Event.objects.filter(**filter_kwargs)
    query = query.annotate(**pre_groupby_ann_kwargs)
    query = query.values(**groupby_kwargs)
    query = query.annotate(**groupby_aggregation_kwargs)

    if metric.aggregation_type == "max" and only_billable_usage:
        try:
            query = query.order_by("-usage_qty", "time_created_quantized")[:1]
        except:  # this queryset is empty
            pass

    if metric.aggregation_type == "last":
        if len(query) > 0:
            query = query.order_by(
                Trunc(F("time_created"), time_period_agg), "-time_created"
            ).distinct(Trunc(F("time_created"), time_period_agg))

    usage_summary = query
    for x in usage_summary:
        x["usage_qty"] = convert_to_decimal(x["usage_qty"])

    return usage_summary


def calculate_total_pc_revenue(plan_component, units_usage):
    if plan_component.cost_per_batch == 0 or plan_component.cost_per_batch is None:
        return 0
    subtotal_usage = max(units_usage - plan_component.free_metric_units, 0)
    metric_batches = math.ceil(subtotal_usage / plan_component.metric_units_per_batch)
    subtotal_cost = (metric_batches * plan_component.cost_per_batch).amount
    return subtotal_cost


def calculate_per_period_pc_revenue_for_aggregation_metric(
    plan_component, units_usage_per_day
):
    coalesced_usage = {}
    for x in units_usage_per_day:
        tc_q = x["time_created_quantized"]
        if tc_q not in coalesced_usage:
            coalesced_usage[tc_q] = 0
        coalesced_usage[tc_q] += x["usage_qty"]
    usages = [
        {"time_created_quantized": k, "usage_qty": v}
        for k, v in coalesced_usage.items()
    ]
    sorted_usage = sorted(usages, key=lambda x: x["time_created_quantized"])
    period_revenue_dict = {}
    free_units_usage_left = plan_component.free_metric_units
    remainder_billable_units = 0
    for x in sorted_usage:
        qty = Decimal(x["usage_qty"])
        tc_q = x["time_created_quantized"]
        period_revenue_dict[tc_q] = {"usage_qty": qty, "revenue": 0}
        if plan_component.cost_per_batch == 0 or plan_component.cost_per_batch is None:
            pass
        else:
            billable_units = max(
                qty - free_units_usage_left + remainder_billable_units, 0
            )
            billable_batches = billable_units // plan_component.metric_units_per_batch
            remainder_billable_units = (
                billable_units
                - billable_batches * plan_component.metric_units_per_batch
            )
            free_units_usage_left = max(0, free_units_usage_left - qty)
            usage_revenue = (billable_batches * plan_component.cost_per_batch).amount
            period_revenue_dict[tc_q]["revenue"] = usage_revenue
    return period_revenue_dict


def calculate_pc_usage_rev_for_stateful_metric(
    plan_component,
    billable_metric,
    customer,
    plan_start_date,
    plan_end_date,
    revenue_granularity,
):

    stateful_agg_p = billable_metric.stateful_aggregation_period
    # get all the relevant events
    now = datetime.datetime.now(timezone.utc)
    event_set = Event.objects.filter(
        organization=billable_metric.organization,
        event_name=billable_metric.event_name,
        time_created__date__gte=plan_start_date,
        time_created__date__lte=plan_end_date,
        time_created__lt=now,
        customer=customer,
        properties__has_key=billable_metric.property_name,
    ).annotate(property_value=F("properties__" + billable_metric.property_name))
    last_event = (
        Event.objects.filter(
            organization=billable_metric.organization,
            event_name=billable_metric.event_name,
            time_created__date__lt=plan_start_date,
            customer=customer,
            properties__has_key=billable_metric.property_name,
        )
        .order_by("-time_created")
        .annotate(property_value=F("properties__" + billable_metric.property_name))
        .first()
    )

    # quantize first according to the stateful period
    if stateful_agg_p == "day":
        plan_periods = list(dates_bwn_twodates(plan_start_date, plan_end_date))
        prorated_cost_per_batch = convert_to_decimal(
            (plan_component.cost_per_batch / len(plan_periods)).amount
        )
        quantize_event_time = lambda x: x.date()
    elif stateful_agg_p == "hour":
        plan_periods = list(hours_bwn_twodates(plan_start_date, plan_end_date))
        prorated_cost_per_batch = convert_to_decimal(
            (plan_component.cost_per_batch / len(plan_periods)).amount
        )
        quantize_event_time = lambda x: x.replace(minute=0, second=0, microsecond=0)
    event_period_dict = {}
    for event in event_set:
        tc_q = quantize_event_time(event.time_created)
        if tc_q not in event_period_dict:
            event_period_dict[tc_q] = []
        event_period_dict[tc_q].append(event)
    # for each period, get the events and calculate the usage and revenue
    usage_revenue_dict = {}
    for period in plan_periods:
        # optionally add the "last" event, and calculate effective usage
        period_events = event_period_dict.get(period, [])
        if last_event is not None and len(period_events) == 0:
            period_events.append(last_event)
        period_events_ordered_asc = sorted(period_events, key=lambda x: x.time_created)
        if billable_metric.aggregation_type == "max":
            usage = max([x.property_value for x in period_events], default=0)
        elif billable_metric.aggregation_type == "last":
            usage = (
                period_events_ordered_asc[-1].property_value
                if len(period_events_ordered_asc) > 0
                else 0
            )
        usage = convert_to_decimal(usage)
        # calculate revenue
        if plan_component.cost_per_batch == 0 or plan_component.cost_per_batch is None:
            revenue = 0
        else:
            free_units_usage = plan_component.free_metric_units
            metric_batches = math.ceil(
                (max(usage - free_units_usage, 0))
                / plan_component.metric_units_per_batch
            )
            revenue = metric_batches * prorated_cost_per_batch
        # add revenue and usage to the dict
        usage_revenue_dict[period] = {
            "revenue": revenue,
            "usage_qty": usage,
        }
        # update the last event
        if len(period_events_ordered_asc) > 0:
            last_event = period_events_ordered_asc[-1]

    # now we need to re-quantize the usage_revenue_dict according to the revenue granularity
    if revenue_granularity == RevenueCalcGranularity.DAILY:
        re_quantized_usage_revenue_dict = {}
        for period, d in usage_revenue_dict.items():
            if not isinstance(period, datetime.date):
                dt = period.date
            else:
                dt = period
            if dt not in re_quantized_usage_revenue_dict:
                re_quantized_usage_revenue_dict[dt] = {
                    "revenue": 0,
                    "usages": [],
                }
            re_quantized_usage_revenue_dict[dt]["revenue"] += d["revenue"]
            re_quantized_usage_revenue_dict[dt]["usages"].append(d["usage_qty"])
    elif revenue_granularity == RevenueCalcGranularity.TOTAL:
        re_quantized_usage_revenue_dict = {
            "revenue": sum([d["revenue"] for d in usage_revenue_dict.values()]),
        }
    else:
        raise NotImplementedError(
            f"Time period aggregation {revenue_granularity} not supported"
        )
    return re_quantized_usage_revenue_dict


def calculate_pc_usage_rev_for_aggregation_metric(
    plan_component,
    billable_metric,
    customer,
    plan_start_date,
    plan_end_date,
    revenue_granularity,
):
    units_usage = get_metric_usage(
        billable_metric,
        query_start_date=plan_start_date,
        query_end_date=plan_end_date,
        customer=customer,
        time_period_agg=revenue_granularity.value,
        only_billable_usage=revenue_granularity != RevenueCalcGranularity.TOTAL,
    )
    if revenue_granularity == RevenueCalcGranularity.TOTAL:
        # this mean we only care about total revenue, don't need to break it out by x
        assert len(units_usage) <= 1, "Shouldn't have more than one row of usage"
        if len(units_usage) > 0:
            usg = units_usage[0]["usage_qty"]
            revenue = calculate_total_pc_revenue(plan_component, usg)
            usage_revenue_dict = {"usage_qty": usg, "revenue": revenue}
        else:
            usage_revenue_dict = {"usage_qty": 0, "revenue": 0}
    else:
        usage_revenue_dict = calculate_per_period_pc_revenue_for_aggregation_metric(
            plan_component, units_usage
        )
    ret_dict = {}
    for k, v in usage_revenue_dict.items():
        if isinstance(k, datetime.datetime):
            ret_dict[k.date()] = v
        else:
            ret_dict[k] = v
    return ret_dict


def calculate_sub_pc_usage_revenue(
    plan_component,
    billable_metric,
    customer,
    plan_start_date,
    plan_end_date,
    revenue_granularity=RevenueCalcGranularity.TOTAL,
):
    # revenue calculation needs to be daily, monthly, yearly, or over the entire query
    assert isinstance(
        revenue_granularity, RevenueCalcGranularity
    ), "revenue_granularity must be part of RevenueCalcGranularity enum"
    if type(plan_start_date) == str:
        plan_start_date = parser.parse(plan_start_date).date()
    if type(plan_end_date) == str:
        plan_end_date = parser.parse(plan_end_date).date()
    args_dict = {
        "plan_component": plan_component,
        "billable_metric": billable_metric,
        "customer": customer,
        "plan_start_date": plan_start_date,
        "plan_end_date": plan_end_date,
        "revenue_granularity": revenue_granularity,
    }
    if billable_metric.event_type == "stateful":
        usage_revenue_dict = calculate_pc_usage_rev_for_stateful_metric(**args_dict)
    else:
        usage_revenue_dict = calculate_pc_usage_rev_for_aggregation_metric(**args_dict)
    for k, _ in usage_revenue_dict.items():
        if revenue_granularity == RevenueCalcGranularity.TOTAL:
            assert isinstance(k, str), "Total revenue should be a string"
        elif revenue_granularity == RevenueCalcGranularity.DAILY:
            assert isinstance(
                k, datetime.date
            ), f"Daily revenue should be a date (Key {k} is not)"
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
    if type(json) in [dict, collections.OrderedDict]:
        for key, value in json.items():
            if isinstance(value, dict) or isinstance(value, collections.OrderedDict):
                make_all_decimals_floats(value)
            elif isinstance(value, list):
                for item in value:
                    make_all_decimals_floats(item)
            elif isinstance(value, Decimal):
                json[key] = float(value)
    if isinstance(json, list):
        for item in json:
            make_all_decimals_floats(item)


def make_all_dates_times_strings(json):
    if type(json) in [
        dict,
        list,
        datetime.datetime,
        datetime.date,
        collections.OrderedDict,
    ]:
        for key, value in json.items():
            if isinstance(value, dict) or isinstance(value, collections.OrderedDict):
                make_all_dates_times_strings(value)
            elif isinstance(value, list):
                for item in value:
                    make_all_dates_times_strings(item)
            elif isinstance(value, datetime.datetime) or isinstance(
                value, datetime.date
            ):
                json[key] = str(value)


def make_all_datetimes_dates(json):
    if type(json) in [
        dict,
        list,
        datetime.datetime,
        collections.OrderedDict,
    ]:
        for key, value in json.items():
            if isinstance(value, dict) or isinstance(value, collections.OrderedDict):
                make_all_dates_times_strings(value)
            elif isinstance(value, list):
                for item in value:
                    make_all_dates_times_strings(item)
            elif isinstance(value, datetime.datetime):
                json[key] = value.date()


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
