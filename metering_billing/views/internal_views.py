import json
import math
import os
from datetime import datetime, timedelta

import dateutil.parser as parser
import stripe
from django.db import connection
from django.db.models import Q
from django.forms.models import model_to_dict
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
from django_q.tasks import async_task
from lotus.settings import STRIPE_SECRET_KEY
from metering_billing.models import (
    APIToken,
    BillableMetric,
    BillingPlan,
    Customer,
    Event,
    Invoice,
    Organization,
    PlanComponent,
    Subscription,
)
from metering_billing.permissions import HasUserAPIKey
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..utils import get_customer_usage, get_metric_usage, parse_organization


class OrganizationRevenueInPeriodView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        """
        Returns the revenue for an organization in a given time period.
        """

        parsed_org = parse_organization(request)
        if type(parsed_org) == Response:
            return parsed_org
        else:
            organization = parsed_org
        reference_date = request.query_params["reference_date"]
        period_length_days = request.query_params["period_length_days"]
        query_start_date = reference_date - 2 * timedelta(days=period_length_days)
        query_mid_date = reference_date - timedelta(days=period_length_days)
        invoices = Invoice.objects.filter(
            organization=organization,
            issue_date__range=[
                query_start_date,
                reference_date,
            ],
        )
        # calculate total theoretical revenue
        recent_period_invoices = list(
            filter(lambda invoice: invoice.issue_date >= query_mid_date, list(invoices))
        )
        older_period_invoices = list(
            filter(lambda invoice: invoice.issue_date < query_mid_date, list(invoices))
        )
        recent_period_total_rev = sum(
            map(lambda invoice: invoice.total, recent_period_invoices)
        )
        older_period_total_rev = sum(
            map(lambda invoice: invoice.total, older_period_invoices)
        )

        # calculate total realized revenue
        recent_period_realized_invoices = list(
            filter(
                lambda invoice: invoice.status == "fulfilled", recent_period_invoices
            )
        )
        older_period_realized_invoices = list(
            filter(lambda invoice: invoice.status == "fulfilled", older_period_invoices)
        )
        recent_period_realized_rev = sum(
            map(lambda invoice: invoice.total, recent_period_realized_invoices)
        )
        older_period_realized_rev = sum(
            map(lambda invoice: invoice.total, older_period_realized_invoices)
        )

        return JsonResponse(
            {
                "recent_period_total_rev": recent_period_total_rev,
                "older_period_total_rev": older_period_total_rev,
                "recent_period_realized_rev": recent_period_realized_rev,
                "older_period_realized_rev": older_period_realized_rev,
            }
        )


class OrganizationSubscriptionsInPeriodView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        """
        List subscriptions.
        """

        parsed_org = parse_organization(request)
        if type(parsed_org) == Response:
            return parsed_org
        else:
            organization = parsed_org
        reference_date = request.query_params["reference_date"]
        period_length_days = request.query_params["period_length_days"]
        query_start_date = reference_date - 2 * timedelta(days=period_length_days)
        query_mid_date = reference_date - timedelta(days=period_length_days)
        query_end_date = reference_date
        subscriptions = Subscription.objects.filter(
            Q(start_date__range=[query_start_date, query_end_date])
            | Q(end_date__range=[query_start_date, query_end_date]),
            organization=organization,
        )
        # calculate total theoretical revenue
        recent_period_only_subscriptions = list(
            filter(
                lambda subscription: subscription.start_date >= query_mid_date,
                list(subscriptions),
            )
        )
        older_period_only_subscriptions = list(
            filter(
                lambda subscription: subscription.end_date < query_mid_date,
                list(subscriptions),
            )
        )
        both_period_subscriptions = list(
            set(subscriptions)
            - set(recent_period_only_subscriptions)
            - set(older_period_only_subscriptions)
        )

        recent_period_first_time_subscriptions = list(
            filter(
                lambda subscription: subscription.is_new,
                recent_period_only_subscriptions,
            )
        )
        older_period_first_time_subscriptions = list(
            filter(
                lambda subscription: subscription.is_new,
                older_period_only_subscriptions,
            )
        )
        both_period_first_time_subscriptions = list(
            filter(lambda subscription: subscription.is_new, both_period_subscriptions)
        )

        return JsonResponse(
            {
                "recent_period_total_subscriptions": len(
                    recent_period_only_subscriptions
                )
                + len(both_period_subscriptions),
                "older_period_total_subscriptions": len(older_period_only_subscriptions)
                + len(both_period_subscriptions),
                "recent_period_new_subscriptions": len(
                    recent_period_first_time_subscriptions
                )
                + len(both_period_first_time_subscriptions),
                "older_period_realized_subscriptions": len(
                    older_period_first_time_subscriptions
                )
                + len(both_period_first_time_subscriptions),
            }
        )


class OrganizationMetricsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        """
        Returns the metrics for an organization in a given time period.
        """

        parsed_org = parse_organization(request)
        if type(parsed_org) == Response:
            return parsed_org
        else:
            organization = parsed_org
        metrics = BillableMetric.objects.filter(organization=organization)
        metrics_dict = {}
        for metric in metrics:
            if metric.event_name not in metrics_dict:
                metrics_dict[metric.event_name] = {}
            if metric.property_name not in metrics_dict[metric.event_name]:
                metrics_dict[metric.event_name][metric.property_name] = {}
            metrics_dict[metric.event_name][metric.property_name][
                metric.aggregation_type
            ] = str(metric)
        return JsonResponse(metrics_dict)


class OrganizationUsageForMetricView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        """
        Return current usage for a customer during a given billing period.
        """
        parsed_org = parse_organization(request)
        if type(parsed_org) == Response:
            return parsed_org
        else:
            organization = parsed_org
        reference_date = request.query_params["reference_date"]
        period_length_days = request.query_params["period_length_days"]
        query_start_date = reference_date - 2 * timedelta(days=period_length_days)
        query_mid_date = reference_date - timedelta(days=period_length_days)
        query_end_date = reference_date

        event_name = request.query_params["event_name"]
        property_name = request.query_params["property_name"]
        aggregation_type = request.query_params["aggregation_type"]
        metric_qs = BillableMetric.objects.filter(
            organization=organization,
            event_name=event_name,
            property_name=property_name,
            aggregation_type=aggregation_type,
        )

        if len(metric_qs) < 1:
            return Response(
                {
                    "error": f"Metric with event_name {event_name}, property_name {property_name}, aggregation_type {aggregation_type} not found"
                },
                status=400,
            )
        else:
            metric = metric_qs[0]

        usage_summary_current_period, usage_summary_previous_period = get_metric_usage(
            metric, query_start_date, query_mid_date, query_end_date
        )

        return JsonResponse(
            [usage_summary_current_period, usage_summary_previous_period]
        )
