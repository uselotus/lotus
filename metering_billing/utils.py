import collections
import math
from decimal import ROUND_DOWN, ROUND_UP, Decimal

from dateutil import parser
from dateutil.relativedelta import relativedelta
from django.db.models import Count, F, FloatField, Max, Sum
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast

from metering_billing.models import Event, Subscription
from metering_billing.serializers.internal_serializers import (
    SubscriptionUsageSerializer,
)
from metering_billing.serializers.model_serializers import (
    BillingPlanSerializer,
    PlanComponentReadSerializer,
)


# DAILY USAGE + REVENUE METHODS
def get_metric_usage(
    metric,
    query_start_date=None,
    query_end_date=None,
    customer=None,
    time_period_agg=None,
    time_period_annotation=None,
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
    if time_period_annotation:
        annotate_kwargs["time_created_quantized"] = F(
            f"time_created__{time_period_annotation}"
        )
    # try filtering by the metric's desired property_name
    if metric.property_name is not None:
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


def calculate_plan_component_revenue(plan_component, units_usage):
    subtotal_usage = max(units_usage - plan_component.free_metric_quantity, 0)
    metric_batches = math.ceil(subtotal_usage / plan_component.metric_amount_per_cost)
    subtotal_cost = (metric_batches * plan_component.cost_per_metric).amount
    return subtotal_cost


def calculate_daily_pc_revenue_for_additive_metric(
    plan_component, units_usage_per_day, query_start, query_end
):
    days_before_query_start = list(
        x["usage_qty"]
        for x in units_usage_per_day
        if x["time_created_quantized"] < query_start
    )
    units_usage_before_query_start = (
        sum(days_before_query_start) if len(days_before_query_start) > 0 else 0
    )
    units_usage_query = [
        (x["usage_qty"], x["time_created_quantized"])
        for x in units_usage_per_day
        if x["time_created_quantized"] >= query_start
        and x["time_created_quantized"] <= query_end
    ]
    free_units_usage = plan_component.free_metric_quantity
    free_units_usage_left = max(free_units_usage - units_usage_before_query_start, 0)
    day_revenue_dict = {
        x[1]: {"revenue": Decimal(0), "usage_qty": x[0]} for x in units_usage_query
    }
    remainder_billable_units = 0
    for qty, date in units_usage_query:
        qty = Decimal(qty)
        billable_units = max(qty - free_units_usage_left + remainder_billable_units, 0)
        billable_batches = billable_units // plan_component.metric_amount_per_cost
        remainder_billable_units = (
            billable_units - billable_batches * plan_component.metric_amount_per_cost
        )
        free_units_usage_left = max(0, free_units_usage_left - qty)
        usage_revenue = (billable_batches * plan_component.cost_per_metric).amount
        day_revenue_dict[date]["revenue"] = usage_revenue
    return day_revenue_dict


def calculate_daily_pc_revenue_for_cliff_metric(
    plan_component, units_usage_per_day, query_start, query_end
):
    # determine what the maximum usage was IN the plan, but OUTSIDE the query
    days_before_query_start = list(
        x["usage_qty"]
        for x in units_usage_per_day
        if x["time_created_quantized"] < query_start
    )
    units_usage_before_query_start = (
        max(days_before_query_start) if len(days_before_query_start) > 0 else 0
    )
    units_usage_before_query_start = Decimal(units_usage_before_query_start)
    days_after_query_end = list(
        x["usage_qty"]
        for x in units_usage_per_day
        if x["time_created_quantized"] > query_end
    )
    units_usage_after_query_end = (
        max(days_after_query_end) if len(days_after_query_end) > 0 else 0
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
    day_revenue_dict = {
        x[1]: {"revenue": Decimal(0), "usage_qty": x[0]} for x in units_usage_query
    }
    if (
        max_units_usage_query < max_units_usage_outside_query
        or max_units_usage_query == 0
    ):
        return day_revenue_dict
    for qty, date in units_usage_query:
        qty = Decimal(qty)
        if qty > max_units_usage_outside_query and qty == max_units_usage_query:
            free_units_usage = plan_component.free_metric_quantity
            metric_batches = math.ceil(
                (qty - free_units_usage) / plan_component.metric_amount_per_cost
            )
            usage_revenue = (metric_batches * plan_component.cost_per_metric).amount
            day_revenue_dict[date]["revenue"] = usage_revenue
            break
    return day_revenue_dict


def calculate_stateful_pc_revenue(
    plan_component, units_usage, plan_start_date, plan_end_date, customer
):
    metric = plan_component.billable_metric
    plan_dates = list(dates_bwn_twodates(plan_start_date, plan_end_date))
    usage_revenue_dict = {str(x): {"usage": 0, "revenue": 0} for x in plan_dates}
    # sort all the events by date
    qs_dates = {}
    for x in units_usage:
        tc = str(x["time_created_quantized"])
        if tc not in qs_dates:
            qs_dates[tc] = []
        qs_dates[tc].append(x)
    # if the plan carries over, we need to add the last usage from the previous period
    last_event = None
    if plan_component.billable_metric.carries_over:
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
    # for each day, calculate the usage and revenue
    for date in sorted(usage_revenue_dict.keys()):
        # optionally add the "last" event, and calculate effective usage
        date_events = qs_dates.get(date, [])
        if last_event is not None and len(date_events) == 0:
            date_events.append(last_event)
        usage = max([x["usage_qty"] for x in date_events], default=0)
        # calculate revenue
        free_units_usage = plan_component.free_metric_quantity
        metric_batches = math.ceil(
            (max(usage - free_units_usage, 0)) / plan_component.metric_amount_per_cost
        )
        revenue = (metric_batches * plan_component.cost_per_metric).amount
        # add revenue and usage to the dict
        usage_revenue_dict[date] = {
            "revenue": revenue,
            "usage_qty": usage,
        }
        # update the last event
        if len(date_events) > 0:
            last_event = sorted(date_events, key=lambda x: x["time_created_quantized"])[
                -1
            ]
    return usage_revenue_dict


def calculate_pc_usage_rev_for_stateful_metric(
    plan_component,
    customer,
    plan_start_date,
    plan_end_date,
    query_start,
    query_end,
    time_period_agg,
    time_period_annotation,
):
    billable_metric = plan_component.billable_metric
    units_usage = get_metric_usage(
        billable_metric,
        query_start_date=query_start,
        query_end_date=query_end,
        customer=customer,
        time_period_agg=time_period_agg,
        time_period_annotation=time_period_annotation,
    )
    usage_revenue_dict = calculate_stateful_pc_revenue(
        plan_component, units_usage, plan_start_date, plan_end_date, customer
    )
    return usage_revenue_dict


def calculate_pc_usage_rev_for_aggregation_metric(
    plan_component,
    customer,
    plan_start_date,
    plan_end_date,
    query_start,
    query_end,
    time_period_agg,
    time_period_annotation,
):
    billable_metric = plan_component.billable_metric
    units_usage = get_metric_usage(
        billable_metric,
        query_start_date=plan_start_date,
        query_end_date=plan_end_date,
        customer=customer,
        time_period_agg=time_period_agg,
        time_period_annotation=time_period_annotation,
    )
    if time_period_agg == "date":
        if billable_metric.aggregation_type == "max":
            usage_revenue_dict = calculate_daily_pc_revenue_for_cliff_metric(
                plan_component, units_usage, query_start, query_end
            )
        else:
            usage_revenue_dict = calculate_daily_pc_revenue_for_additive_metric(
                plan_component, units_usage, query_start, query_end
            )
    else:
        # this means this plan component is not recurring, and we want usage + revenue
        # only during the plan
        assert len(units_usage) <= 1, "Shouldn't have more than one row of usage"
        usg = units_usage[0]["usage_qty"] if len(units_usage) > 0 else 0
        usage_revenue_dict = {"usage_qty": usg, "revenue": 0}
        revenue = calculate_plan_component_revenue(
            plan_component, usage_revenue_dict["usage_qty"]
        )
        usage_revenue_dict["revenue"] = revenue
    return usage_revenue_dict


def calculate_sub_pc_usage_revenue(
    plan_component,
    customer,
    plan_start_date,
    plan_end_date,
    query_start=None,
    query_end=None,
    time_period_agg=None,
    time_period_annotation=None,
):
    billable_metric = plan_component.billable_metric
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
        "customer": customer,
        "plan_start_date": plan_start_date,
        "plan_end_date": plan_end_date,
        "query_start": query_start,
        "query_end": query_end,
        "time_period_agg": time_period_agg,
        "time_period_annotation": time_period_annotation,
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
    sub_dict["billing_plan"] = BillingPlanSerializer(plan).data
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
            customer,
            plan_start_date,
            plan_end_date,
        )
        plan_component_summary["plan_component"] = PlanComponentReadSerializer(
            plan_component
        ).data
        sub_dict["components"].append(plan_component_summary)
    sub_dict["usage_revenue_due"] = sum(
        component["revenue"] for component in sub_dict["components"]
    )
    sub_dict["flat_revenue_due"] = subscription.billing_plan.flat_rate.amount
    sub_dict["total_revenue_due"] = (
        sub_dict["flat_revenue_due"] + sub_dict["usage_revenue_due"]
    )
    serializer = SubscriptionUsageSerializer(data=sub_dict)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def get_customer_usage_and_revenue(customer):
    customer_subscriptions = Subscription.objects.filter(
        customer=customer, status="active", organization=customer.organization
    )
    subscription_usages = {"subscriptions": []}
    for subscription in customer_subscriptions:
        sub_dict = get_subscription_usage_and_revenue(subscription)
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


def dates_bwn_twodates(start_date, end_date):
    for n in range((end_date - start_date).days + 1):
        yield start_date + relativedelta(days=n)
