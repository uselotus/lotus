import math
from datetime import datetime

import dateutil.parser as parser
import stripe
from django.db import connection
from django.db.models import Count, Max, Sum
from django.http import HttpResponseBadRequest, JsonResponse
from lotus.settings import STRIPE_SECRET_KEY
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

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
    CustomerSerializer,
    EventSerializer,
    PlanComponentSerializer,
    SubscriptionSerializer,
)


def get_organization_from_key(request):
    validator = HasUserAPIKey()
    key = validator.get_key(request)
    api_key = APIToken.objects.get_from_key(key)
    organization = api_key.organization
    return organization


def parse_organization(request):
    is_authenticated = request.user.is_authenticated
    has_api_key = HasUserAPIKey().get_key(request) is not None
    if has_api_key and is_authenticated:
        organization_api_token = get_organization_from_key(request)
        organization_user = request.user.organization
        if organization_user.pk != organization_api_token.pk:
            return Response(
                {
                    "error": "Provided both API key and session authentication but organization didn't match"
                },
                status=406,
            )
        else:
            return organization_api_token
    elif has_api_key:
        return get_organization_from_key(request)
    elif is_authenticated:
        organization_user = request.user.organization
        if organization_user is None:
            return Response({"error": "User does not have an organization"}, status=403)
        return organization_user


def get_subscription_usage(subscription):
    plan = subscription.billing_plan
    flat_rate = int(plan.flat_rate.amount)
    plan_start_timestamp = subscription.start_date
    plan_end_timestamp = subscription.end_date

    plan_components_qs = PlanComponent.objects.filter(billing_plan=plan.id)
    if len(plan_components_qs) < 1:
        return Response(
            {"error": "There are no components for this plan"},
            status=409,
        )
    subscription_cost = 0
    plan_components_summary = {}
    # For each component of the plan, calculate usage/cost
    for plan_component in plan_components_qs:
        billable_metric = plan_component.billable_metric
        event_name = billable_metric.event_name
        aggregation_type = billable_metric.aggregation_type
        subtotal_usage = 0.0
        subtotal_cost = 0.0

        events = Event.objects.filter(
            organization=subscription.customer.organization,
            customer=subscription.customer,
            event_name=event_name,
            time_created__gte=plan_start_timestamp,
            time_created__lte=plan_end_timestamp,
        )

        if aggregation_type == "count":
            subtotal_usage = len(events) - plan_component.free_metric_quantity
            metric_batches = math.ceil(
                subtotal_usage / plan_component.metric_amount_per_cost
            )
        elif aggregation_type == "sum":
            property_name = billable_metric.property_name
            for event in events:
                properties_dict = event.properties
                if property_name in properties_dict:
                    subtotal_usage += float(properties_dict[property_name])
            subtotal_usage -= plan_component.free_metric_quantity
            metric_batches = math.ceil(
                subtotal_usage / plan_component.metric_amount_per_cost
            )

        elif aggregation_type == "max":
            property_name = billable_metric.property_name
            for event in events:
                properties_dict = event.properties
                if property_name in properties_dict:
                    subtotal_usage = max(
                        subtotal_usage, float(properties_dict[property_name])
                    )
                metric_batches = subtotal_usage
        subtotal_cost = int((metric_batches * plan_component.cost_per_metric).amount)
        subscription_cost += subtotal_cost

        subtotal_cost_string = "$" + str(subtotal_cost)
        plan_components_summary[str(plan_component)] = {
            "cost": subtotal_cost_string,
            "usage": str(subtotal_usage),
            "free_usage_left": str(
                max(plan_component.free_metric_quantity - subtotal_usage, 0)
            ),
        }
        usage_dict = {
            "subscription_cost": subscription_cost,
            "flat_rate": flat_rate,
            "plan_components_summary": plan_components_summary,
            "current_amount_due": subscription_cost + flat_rate,
            "plan_start_timestamp": plan_start_timestamp,
            "plan_end_timestamp": plan_end_timestamp,
        }

    return usage_dict


def get_customer_usage(customer):
    customer_subscriptions = Subscription.objects.filter(
        customer=customer, status="active", organization=customer.organization
    )

    usage_summary = {}
    for subscription in customer_subscriptions:

        usage_dict = get_subscription_usage(subscription)
        subscription_usage_dict = {
            "total_usage_cost": "$" + str(usage_dict["subscription_cost"]),
            "flat_rate_cost": "$" + str(usage_dict["flat_rate"]),
            "components": usage_dict["plan_components_summary"],
            "current_amount_due": "$" + str(usage_dict["current_amount_due"]),
            "billing_start_date": usage_dict["plan_start_timestamp"],
            "billing_end_date": usage_dict["plan_end_timestamp"],
        }

        usage_summary[subscription.billing_plan.name] = subscription_usage_dict

    return usage_summary


def get_metric_usage(metric, query_start_date, query_mid_date, query_end_date):
    aggregation_field = f"properties__{metric.property_name}"
    aggregation_type = Count if metric.aggregation_type == "count" else (Sum if metric.aggregation_type == "sum" else Max) 
    usage_summary_current_period = Event.objects.filter(
        organization=metric.organization,
        event_name=metric.event_name,
        time_created__gte=query_mid_date,
        time_created__lte=query_end_date,
        properties__has_key=metric.property_name,
    ).values('customer').annotate(value=aggregation_type(aggregation_field))

    usage_summary_previous_period = Event.objects.filter(
        organization=metric.organization,
        event_name=metric.event_name,
        time_created__gte=query_start_date,
        time_created__lte=query_mid_date,
        properties__has_key=metric.property_name,
    ).values('customer').annotate(value=aggregation_type(aggregation_field))

    return usage_summary_current_period, usage_summary_previous_period


def generate_invoice(subscription):
    """
    Generate an invoice for a subscription.
    """

    usage_dict = get_subscription_usage(subscription)

    # Get the customer
    customer = subscription.customer
    billing_plan = subscription.billing_plan
    # Create the invoice
    invoice = Invoice.objects.create(
        cost_due=usage_dict["current_amount_due"],
        issue_date=subscription.end_date,
        organization=subscription.organization,
        customer=customer,
        subscription=subscription,
    )

    return invoice
