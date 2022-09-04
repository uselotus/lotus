import math
from decimal import Decimal

from django.contrib.postgres.fields import DateTimeRangeField
from django.db import connection
from django.db.models import Count, F, FloatField, Func, Max, Q, Sum
from django.db.models.functions import Cast
from django.shortcuts import get_list_or_404
from lotus.settings import STRIPE_SECRET_KEY
from rest_framework.response import Response

from metering_billing.exceptions import OrganizationMismatch, UserNoOrganization
from metering_billing.models import (
    APIToken,
    BillingPlan,
    Customer,
    Event,
    Invoice,
    PlanComponent,
    Subscription,
)
from metering_billing.permissions import HasUserAPIKey
from metering_billing.serializers import (
    BillingPlanSerializer,
    CustomerRevenueSerializer,
    CustomerSerializer,
    EventSerializer,
    PlanComponentSerializer,
    SubscriptionSerializer,
    SubscriptionUsageSerializer,
)


# AUTH METHODS
def get_organization_from_key(request):
    validator = HasUserAPIKey()
    key = validator.get_key(request)
    api_key = APIToken.objects.get_from_key(key)
    organization = api_key.organization
    return organization


def get_user_org_or_raise_no_org(request):
    organization_user = request.user.organization
    if organization_user is None:
        raise UserNoOrganization()
    return organization_user


def parse_organization(request):
    is_authenticated = request.user.is_authenticated
    has_api_key = HasUserAPIKey().get_key(request) is not None
    if has_api_key and is_authenticated:
        organization_api_token = get_organization_from_key(request)
        organization_user = get_user_org_or_raise_no_org(request)
        if organization_user.pk != organization_api_token.pk:
            raise OrganizationMismatch()
        return organization_api_token
    elif has_api_key:
        return get_organization_from_key(request)
    elif is_authenticated:
        return get_user_org_or_raise_no_org(request)


# DAILY USAGE + REVENUE METHODS
def get_metric_usage(
    metric, query_start_date, query_end_date, customer=None, daily=False
):
    filtering_kwargs = {
        "organization": metric.organization,
        "event_name": metric.event_name,
        "time_created__date__gte": query_start_date,
        "time_created__date__lte": query_end_date,
    }
    values_kwargs = {"customer_name": F("customer__name")}
    if metric.aggregation_type == "count":
        aggregation_field = "event_name"
        aggregation_type = Count
    else:
        aggregation_field = f"properties__{metric.property_name}"
        aggregation_type = Sum if metric.aggregation_type == "sum" else Max
        filtering_kwargs["properties__has_key"] = metric.property_name
    if customer:
        filtering_kwargs["customer"] = customer
    if daily:
        filtering_kwargs["time_created__date"] = F("time_created__date")
        values_kwargs["date_created"] = F("time_created__date")
    usage_summary = (
        Event.objects.filter(**filtering_kwargs)
        .values(**values_kwargs)
        .annotate(
            usage_qty=aggregation_type(
                Cast(aggregation_field, FloatField())
                if metric.aggregation_type != "count"
                else aggregation_field
            )
        )
    )

    return usage_summary


def calculate_plan_component_daily_revenue_for_additive_metric(
    plan_component, units_usage_per_day, query_start, query_end
):
    units_usage_btwn_plan_and_query_starts = sum(
        (
            x["usage_qty"]
            for x in units_usage_per_day
            if x["date_created"] < query_start
        ),
        default=0,
    )
    units_usage_query = [
        x["usage_qty"]
        for x in units_usage_per_day
        if x["date_created"] >= query_start and x["date_created"] <= query_end
    ]
    free_units_usage = plan_component.free_metric_quantity
    free_units_usage_left = max(
        free_units_usage - units_usage_btwn_plan_and_query_starts, 0
    )
    day_revenue_dict = {}
    remainder_billable_units = 0
    for single_day_units_usage in units_usage_query:
        qty = single_day_units_usage["usage_qty"]
        date = single_day_units_usage["date_created"]
        billable_units = max(qty - free_units_usage_left + remainder_billable_units, 0)
        billable_batches = billable_units // plan_component.metric_amount_per_cost
        remainder_billable_units = (
            billable_units - billable_batches * plan_component.metric_amount_per_cost
        )
        free_units_usage_left = max(0, free_units_usage_left - qty)
        usage_revenue = (billable_batches * plan_component.cost_per_metric).amount
        day_revenue_dict[date] = usage_revenue
    return day_revenue_dict


def calculate_plan_component_daily_revenue_for_cliff_metric(
    plan_component, units_usage_per_day, query_start, query_end
):
    # determine what the maximum usage was IN the plan, but OUTSIDE the query
    units_usage_btwn_plan_and_query_start = max(
        (
            x["usage_qty"]
            for x in units_usage_per_day
            if x["date_created"] < query_start
        ),
        default=0,
    )
    units_usage_btwn_query_end_and_plan_end = max(
        (x["usage_qty"] for x in units_usage_per_day if x["date_created"] > query_end),
        default=0,
    )
    max_units_usage_outside_query = max(
        units_usage_btwn_plan_and_query_start, units_usage_btwn_query_end_and_plan_end
    )
    # go through each day in the query and determine the usage revenue... x if max, 0 otherwise
    units_usage_query = [
        x["usage_qty"]
        for x in units_usage_per_day
        if x["date_created"] >= query_start and x["date_created"] <= query_end
    ]
    max_units_usage_query = max(units_usage_query)
    day_revenue_dict = {x["date_created"]: 0 for x in units_usage_query}
    if max_units_usage_query < max_units_usage_outside_query:
        return day_revenue_dict
    for single_day_units_usage in units_usage_query:
        qty = single_day_units_usage["usage_qty"]
        date = single_day_units_usage["date_created"]
        if qty > max_units_usage_outside_query and qty == max_units_usage_query:
            free_units_usage = plan_component.free_metric_quantity
            metric_batches = math.ceil(
                (qty - free_units_usage) / plan_component.metric_amount_per_cost
            )
            usage_revenue = (metric_batches * plan_component.cost_per_metric).amount
            day_revenue_dict[date] = usage_revenue
            break
    return day_revenue_dict


def calculate_plan_component_daily_revenue(
    customer, plan_component, plan_start_date, plan_end_date, query_start, query_end
):
    billable_metric = plan_component.billable_metric
    units_usage_per_day = get_metric_usage(
        billable_metric,
        query_start_date=plan_start_date,
        query_end_date=plan_end_date,
        customer=customer,
        daily=True,
    )
    if billable_metric.aggregation_type == "max":
        usage_revenue_dict = calculate_plan_component_daily_revenue_for_cliff_metric(
            plan_component, units_usage_per_day, query_start, query_end
        )
    else:
        usage_revenue_dict = calculate_plan_component_daily_revenue_for_additive_metric(
            plan_component, units_usage_per_day, query_start, query_end
        )
    return usage_revenue_dict


# AGGREGATE USAGE + REVENUE METHODS
def calculate_plan_component_revenue(plan_component, units_usage):
    subtotal_usage = units_usage - plan_component.free_metric_quantity
    metric_batches = math.ceil(subtotal_usage / plan_component.metric_amount_per_cost)
    subtotal_cost = (metric_batches * plan_component.cost_per_metric).amount
    return subtotal_cost


def calculate_plan_component_usage_and_revenue(
    customer, plan_component, plan_start_date, plan_end_date
):
    usage_revenue_dict = {"usage": 0, "revenue": 0}
    billable_metric = plan_component.billable_metric
    units_usage = Decimal(
        get_metric_usage(
            billable_metric,
            query_start_date=plan_start_date,
            query_end_date=plan_end_date,
            customer=customer,
        ).first()["usage_qty"]
    )
    usage_revenue_dict["units_usage"] = units_usage
    usage_revenue_dict["usage_revenue"] = calculate_plan_component_revenue(
        plan_component, units_usage
    )
    return usage_revenue_dict


def get_subscription_usage_and_revenue(subscription):
    sub_dict = {}
    sub_dict["components"] = []
    # set up the billing plan for this subscription
    plan = subscription.billing_plan
    # shallow_serializer = BillingPlanSerializer(plan)
    # shallow_serializer.is_valid(raise_exception=True)
    sub_dict["billing_plan"] = BillingPlanSerializer(plan).data
    # set up other details of the subscription
    plan_start_date = subscription.start_date
    plan_end_date = subscription.end_date
    # extract other objects that we need when calculating usage
    customer = subscription.customer
    plan_components_qs = plan.components.all()
    # For each component of the plan, calculate usage/revenue
    for plan_component in plan_components_qs:
        plan_component_summary = calculate_plan_component_usage_and_revenue(
            customer,
            plan_component,
            plan_start_date,
            plan_end_date,
        )
        plan_component_summary["plan_component"] = PlanComponentSerializer(
            plan_component
        ).data
        sub_dict["components"].append(plan_component_summary)
    sub_dict["usage_revenue_due"] = sum(
        component["usage_revenue"] for component in sub_dict["components"]
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


def generate_invoice(subscription):
    """
    Generate an invoice for a subscription.
    """
    usage_dict = get_subscription_usage_and_revenue(subscription)
    # Get the customer
    customer = subscription.customer
    billing_plan = subscription.billing_plan
    # Create the invoice
    invoice = Invoice.objects.create(
        cost_due=usage_dict["total_revenue_due"],
        issue_date=subscription.end_date,
        organization=subscription.organization,
        customer=customer,
        subscription=subscription,
    )

    return invoice
