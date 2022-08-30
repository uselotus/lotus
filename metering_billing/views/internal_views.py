import json
import math
import os
from datetime import datetime, timedelta

import dateutil.parser as parser
import stripe
from django.db import connection
from django.forms.models import model_to_dict
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
from django_q.tasks import async_task
from lotus.settings import STRIPE_SECRET_KEY
from metering_billing.models import (
    APIToken,
    BillingPlan,
    Customer,
    Event,
    Invoice,
    Organization,
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
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..utils import get_customer_usage, parse_organization


class OrganizationRevenueView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        """
        List active subscriptions. If customer_id is provided, only return subscriptions for that customer.
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
            filter(lambda invoice: invoice.issue_date >= query_mid_date), list(invoices)
        )
        older_period_invoices = list(
            filter(lambda invoice: invoice.issue_date < query_mid_date), list(invoices)
        )
        recent_period_total_rev = sum(
            map(lambda invoice: invoice.total, recent_period_invoices)
        )
        older_period_total_rev = sum(
            map(lambda invoice: invoice.total, older_period_invoices)
        )

        # calculate total realized revenue
        recent_period_realized_invoices = list(
            filter(lambda invoice: invoice.status == "fulfilled"),
            recent_period_invoices,
        )
        older_period_realized_invoices = list(
            filter(lambda invoice: invoice.status == "fulfilled"), older_period_invoices
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
