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
from django.shortcuts import get_list_or_404, get_object_or_404
from django_q.tasks import async_task
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
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
from metering_billing.serializers import (
    BillingPlanSerializer,
    CustomerRevenueSerializer,
    CustomerRevenueSummarySerializer,
    CustomerSerializer,
    DayMetricUsageCustomerSerializer,
    EventSerializer,
    PeriodComparisonRequestSerializer,
    PeriodMetricRevenueResponseSerializer,
    PeriodMetricUsageRequestSerializer,
    PeriodMetricUsageResponseSerializer,
    PeriodSubscriptionsResponseSerializer,
    PlanComponentSerializer,
    SubscriptionSerializer,
    SubscriptionUsageSerializer,
)
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..utils import (
    calculate_plan_component_daily_revenue,
    get_customer_usage_and_revenue,
    get_metric_usage,
    parse_organization,
)

stripe.api_key = STRIPE_SECRET_KEY


def import_stripe_customers(organization):
    """
    If customer exists in Stripe and also exists in Lotus (compared by matching names), then update the customer's payment provider ID from Stripe.
    """

    stripe_customers_response = stripe.Customer.list(
        stripe_account=organization.stripe_id
    )

    for stripe_customer in stripe_customers_response.auto_paging_iter():
        try:
            customer = Customer.objects.get(name=stripe_customer["name"])
            customer.payment_provider_id = stripe_customer["id"]
            customer.save()
        except Customer.DoesNotExist:
            pass


def issue_stripe_payment_intent(invoice):

    cost_due = int(invoice.cost_due * 100)
    currency = (invoice.currency).lower()

    stripe.PaymentIntent.create(
        amount=cost_due,
        currency=currency,
        payment_method_types=["card"],
        stripe_account=invoice.organization.stripe_id,
    )


def retrive_stripe_payment_intent(invoice):
    payment_intent = stripe.PaymentIntent.retrieve(
        invoice.payment_intent_id,
        stripe_account=invoice.organization.stripe_id,
    )
    return payment_intent


class InitializeStripeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        """
        Check to see if user has connected their Stripe account.
        """

        organization = parse_organization(request)

        stripe_id = organization.stripe_id

        if stripe_id and len(stripe_id) > 0:
            return JsonResponse({"connected": True})
        else:
            return JsonResponse({"connected": False})

    def post(self, request, format=None):
        """
        Initialize Stripe after user inputs an API key.
        """

        data = request.data

        if data is None:
            return JsonResponse({"details": "No data provided"}, status=400)

        organization = request.user.organization
        if organization is None:
            return Response({"error": "User does not have an organization"}, status=403)
        stripe_code = data["authorization_code"]

        try:
            response = stripe.OAuth.token(
                grant_type="authorization_code",
                code=stripe_code,
            )
        except:
            return JsonResponse(
                {"success": False, "details": "Invalid authorization code"}, status=400
            )

        if "error" in response:
            return JsonResponse(
                {"success": False, "details": response["error"]}, status=400
            )

        connected_account_id = response["stripe_user_id"]

        organization.stripe_id = connected_account_id

        import_stripe_customers(organization)

        organization.save()

        return JsonResponse({"Success": True})


def dates_bwn_twodates(start_date, end_date):
    for n in range((end_date - start_date).days + 1):
        yield start_date + timedelta(n)


class PeriodMetricRevenueView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[PeriodComparisonRequestSerializer],
        responses={200: PeriodMetricRevenueResponseSerializer},
    )
    def get(self, request, format=None):
        """
        Returns the revenue for an organization in a given time period.
        """

        organization = parse_organization(request)
        serializer = PeriodComparisonRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        p1_start, p1_end, p2_start, p2_end = [
            serializer.validated_data.get(key, None)
            for key in [
                "period_1_start_date",
                "period_1_end_date",
                "period_2_start_date",
                "period_2_end_date",
            ]
        ]
        all_org_billable_metrics = BillableMetric.objects.filter(
            organization=organization
        )

        return_dict = {
            "daily_usage_revenue_period_1": {},
            "total_revenue_period_1": 0,
            "daily_usage_revenue_period_2": {},
            "total_revenue_period_2": 0,
        }
        for billable_metric in all_org_billable_metrics:
            for period_start, period_end, period_num in [
                (p1_start, p1_end, 1),
                (p2_start, p2_end, 2),
            ]:
                return_dict[f"daily_usage_revenue_period_{period_num}"][
                    billable_metric.id
                ] = {
                    "metric": billable_metric,
                    "data": {
                        x: 0 for x in dates_bwn_twodates(period_start, period_end)
                    },
                    "total_revenue": 0,
                }
        for period_start, period_end, period_num in [
            (p1_start, p1_end, 1),
            (p2_start, p2_end, 2),
        ]:
            subs = Subscription.objects.filter(
                Q(start_date__range=[period_start, period_end])
                | Q(end_date__range=[period_start, period_end]),
                organization=organization,
            )
            for sub in subs:
                billing_plan = sub.billing_plan
                if billing_plan.pay_in_advance:
                    if sub.start_date >= period_start and sub.start_date <= period_end:
                        return_dict[
                            f"total_revenue_period_{period_num}"
                        ] += billing_plan.flat_rate
                else:
                    if sub.end_date >= period_start and sub.end_date <= period_end:
                        return_dict[
                            f"total_revenue_period_{period_num}"
                        ] += billing_plan.flat_rate
                for plan_component in billing_plan:
                    usage_cost_per_day = calculate_plan_component_daily_revenue(
                        sub.customer,
                        plan_component,
                        sub.start_date,
                        sub.end_date,
                        period_start,
                        period_end,
                    )
                    metric_dict = return_dict[
                        f"daily_usage_revenue_period_{period_num}"
                    ][plan_component.billable_metric.id]
                    for date, usage_cost in usage_cost_per_day.items():
                        metric_dict["data"][date] += usage_cost
                        metric_dict["total_revenue"] += usage_cost
                        return_dict[f"total_revenue_period_{period_num}"] += usage_cost

        for period_num in [1, 2]:
            return_dict[f"daily_usage_revenue_period_{period_num}"] = [
                v
                for _, v in return_dict[
                    f"daily_usage_revenue_period_{period_num}"
                ].items()
            ]
            for dic in return_dict[f"daily_usage_revenue_period_{period_num}"]:
                dic["data"] = [
                    {"date": k, "metric_revenue": v} for k, v in dic["data"].items()
                ]
        serializer = PeriodMetricRevenueResponseSerializer(data=return_dict)
        serializer.is_valid(raise_exception=True)

        return JsonResponse(serializer.validated_data, status=status.HTTP_200_OK)


class PeriodSubscriptionsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[PeriodComparisonRequestSerializer],
        responses={200: PeriodSubscriptionsResponseSerializer},
    )
    def get(self, request, format=None):
        organization = parse_organization(request)
        serializer = PeriodComparisonRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        p1_start, p1_end, p2_start, p2_end = [
            serializer.validated_data.get(key, None)
            for key in [
                "period_1_start_date",
                "period_1_end_date",
                "period_2_start_date",
                "period_2_end_date",
            ]
        ]

        return_dict = {}

        p1_subs = Subscription.objects.filter(
            Q(start_date__range=[p1_start, p1_end])
            | Q(end_date__range=[p1_start, p1_end]),
            organization=organization,
        )
        p1_new_subs = list(filter(lambda sub: sub.is_new, p1_subs))
        return_dict["period_1_total_subscriptions"] = len(p1_subs)
        return_dict["period_1_new_subscriptions"] = len(p1_new_subs)

        p2_subs = Subscription.objects.filter(
            Q(start_date__range=[p2_start, p2_end])
            | Q(end_date__range=[p2_start, p2_end]),
            organization=organization,
        )
        p2_new_subs = list(filter(lambda sub: sub.is_new, p2_subs))
        return_dict["period_2_total_subscriptions"] = len(p2_subs)
        return_dict["period_2_new_subscriptions"] = len(p2_new_subs)

        serializer = PeriodSubscriptionsResponseSerializer(data=return_dict)
        serializer.is_valid(raise_exception=True)
        return JsonResponse(serializer.validated_data, status=status.HTTP_200_OK)


class PeriodMetricUsageView(APIView):

    permission_classes = [IsAuthenticated | HasUserAPIKey]

    @extend_schema(
        parameters=[PeriodMetricUsageRequestSerializer],
        responses={200: PeriodMetricUsageResponseSerializer},
    )
    def get(self, request, format=None):
        """
        Return current usage for a customer during a given billing period.
        """
        pass
        # organization = parse_organization(request)
        # serializer = PeriodMetricUsageRequestSerializer(data=request.query_params)
        # serializer.is_valid(raise_exception=True)
        # q_start, q_end, top_n = [
        #     serializer.validated_data.get(key, None)
        #     for key in ["start_date", "end_date", "top_n_customers"]
        # ]

        # metrics = get_list_or_404(BillableMetric, organization=organization)
        # return_dict = {str(metric):{"data":{}, "total_usage":0} for metric in metrics}
        # customer_usage = {}
        # for metric in metrics:
        #     metric_dict = return_dict[str(metric)]
        #     usage_summary = get_metric_usage(metric, q_start, q_end, daily=True)
        #     for customer_day_object in usage_summary:
        #         customer = customer_day_object["customer_name"]
        #         date_created = customer_day_object["date_created"]
        #         usage_qty = customer_day_object["usage_qty"]

        #         metric_dict["total_usage"] += usage_qty
        #         if date_created not in metric_dict["data"]:
        #             metric_dict["data"]["date"] = {"date": date_created, "customer_usages": []}
        #         metric_dict["data"]["date"]["customer_usages"].append({"customer": customer, "metric_amount": usage_qty})
        #         customer_usage[customer] += usage_qty

        #     return_dict[str(metric)]["data"] =
        #     total_usage = sum(customer_usage.values())
        #     return_dict[str(metric)]["total_usage"] = total_usage
        #     if top_n:
        #         top_n_dict = dict(
        #             sorted(customer_usage.items(), key=lambda x: x[1], reverse=True)[
        #                 :top_n
        #             ]
        #         )
        #         top_n_customers = list(top_n_dict.keys())
        #         top_n_usage = sum(top_n_dict.values())
        #         return_dict[str(metric)]["top_n_customers"] = top_n_customers
        #         return_dict[str(metric)]["top_n_customers_usage"] = top_n_usage
        # response = PeriodMetricUsageResponseSerializer(data={"usage":return_dict})
        # response.is_valid(raise_exception=True)
        # return JsonResponse(response.validated_data, status=status.HTTP_200_OK)


class CustomerWithRevenueView(APIView):

    permission_classes = [IsAuthenticated | HasUserAPIKey]

    @extend_schema(
        responses={200: CustomerRevenueSummarySerializer},
    )
    def get(self, request, format=None):
        """
        Return current usage for a customer during a given billing period.
        """
        organization = parse_organization(request)
        customers = get_list_or_404(Customer, organization=organization)

        customers_dict = {"customers": []}
        for customer in customers:
            sub_usg_summaries = get_customer_usage_and_revenue(customer)
            sub_usg_summaries["total_revenue_due"] = sum(
                x["total_revenue_due"] for x in sub_usg_summaries["subscriptions"]
            )
            serializer = CustomerRevenueSerializer(data=sub_usg_summaries)
            serializer.is_valid(raise_exception=True)
            customers_dict["customers"].append(serializer.validated_data)
        serializer = CustomerRevenueSummarySerializer(data=customers_dict)
        serializer.is_valid(raise_exception=True)

        return Response(serializer.validated_data, status=status.HTTP_200_OK)
