import collections
from datetime import timedelta
from decimal import Decimal

import dateutil.parser as parser
import stripe
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_list_or_404, get_object_or_404
from drf_spectacular.utils import extend_schema
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
from metering_billing.serializers.internal_serializers import *
from metering_billing.serializers.model_serializers import *
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..auth_utils import parse_organization
from ..utils import (
    calculate_plan_component_daily_revenue,
    get_customer_usage_and_revenue,
    get_metric_usage,
    make_all_decimals_floats,
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

        organization = parse_organization(request)
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
    permission_classes = [IsAuthenticated | HasUserAPIKey]

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
            "total_revenue_period_1": Decimal(0),
            "daily_usage_revenue_period_2": {},
            "total_revenue_period_2": Decimal(0),
        }
        if all_org_billable_metrics.count() > 0:
            for billable_metric in all_org_billable_metrics:
                for p_start, p_end, p_num in [(p1_start, p1_end, 1), (p2_start, p2_end, 2)]:
                    return_dict[f"daily_usage_revenue_period_{p_num}"][
                        billable_metric.id
                    ] = {
                        "metric": str(billable_metric),
                        "data": {
                            str(x): Decimal(0) for x in dates_bwn_twodates(p_start, p_end)
                        },
                        "total_revenue": Decimal(0),
                    }
            for p_start, p_end, p_num in [(p1_start, p1_end, 1), (p2_start, p2_end, 2)]:
                subs = Subscription.objects.filter(
                    Q(start_date__range=[p_start, p_end])
                    | Q(end_date__range=[p_start, p_end]),
                    organization=organization,
                )
                for sub in subs:
                    billing_plan = sub.billing_plan
                    flat_fee_billable_date = (
                        sub.start_date if billing_plan.pay_in_advance else sub.end_date
                    )
                    if (
                        flat_fee_billable_date >= p_start
                        and flat_fee_billable_date <= p_end
                    ):
                        return_dict[
                            f"total_revenue_period_{p_num}"
                        ] += billing_plan.flat_rate.amount
                    for plan_component in billing_plan.components.all():
                        usage_cost_per_day = calculate_plan_component_daily_revenue(
                            sub.customer,
                            plan_component,
                            sub.start_date,
                            sub.end_date,
                            p_start,
                            p_end,
                        )
                        metric_dict = return_dict[f"daily_usage_revenue_period_{p_num}"][
                            plan_component.billable_metric.id
                        ]
                        for date, usage_cost in usage_cost_per_day.items():
                            usage_cost = Decimal(usage_cost)
                            metric_dict["data"][str(date)] += usage_cost
                            metric_dict["total_revenue"] += usage_cost
                            return_dict[f"total_revenue_period_{p_num}"] += usage_cost

        for p_num in [1, 2]:
            dailies = return_dict[f"daily_usage_revenue_period_{p_num}"]
            dailies = [v for _, v in dailies.items()]
            return_dict[f"daily_usage_revenue_period_{p_num}"] = dailies
            for dic in dailies:
                dic["data"] = [
                    {"date": k, "metric_revenue": v} for k, v in dic["data"].items()
                ]
        serializer = PeriodMetricRevenueResponseSerializer(data=return_dict)
        serializer.is_valid(raise_exception=True)
        ret = serializer.validated_data
        make_all_decimals_floats(ret)
        return JsonResponse(ret, status=status.HTTP_200_OK)


class PeriodSubscriptionsView(APIView):
    permission_classes = [IsAuthenticated | HasUserAPIKey]

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
        ret = serializer.validated_data
        make_all_decimals_floats(ret)
        return JsonResponse(ret, status=status.HTTP_200_OK)


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
        organization = parse_organization(request)
        serializer = PeriodMetricUsageRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        q_start, q_end, top_n = [
            serializer.validated_data.get(key, None)
            for key in ["start_date", "end_date", "top_n_customers"]
        ]

        metrics = BillableMetric.objects.filter(organization=organization)
        return_dict = {}
        for metric in metrics:
            usage_summary = get_metric_usage(metric, q_start, q_end, daily=True)
            return_dict[str(metric)] = {
                "data": {},
                "total_usage": 0,
                "top_n_customers": {},
            }
            metric_dict = return_dict[str(metric)]
            for obj in usage_summary:
                customer, date, qty = [
                    obj[key] for key in ["customer_name", "date_created", "usage_qty"]
                ]
                if str(date) not in metric_dict["data"]:
                    metric_dict["data"][str(date)] = {
                        "total_usage": Decimal(0),
                        "customer_usages": {},
                    }
                date_dict = metric_dict["data"][str(date)]
                date_dict["total_usage"] += qty
                date_dict["customer_usages"][customer] = qty
                metric_dict["total_usage"] += qty
                if customer not in metric_dict["top_n_customers"]:
                    metric_dict["top_n_customers"][customer] = 0
                metric_dict["top_n_customers"][customer] += qty
            if top_n:
                top_n_customers = sorted(
                    metric_dict["top_n_customers"].items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:top_n]
                metric_dict["top_n_customers"] = list(x[0] for x in top_n_customers)
                metric_dict["top_n_customers_usage"] = list(
                    x[1] for x in top_n_customers
                )
            else:
                del metric_dict["top_n_customers"]
        for metric, metric_d in return_dict.items():
            metric_d["data"] = [
                {
                    "date": k,
                    "total_usage": v["total_usage"],
                    "customer_usages": v["customer_usages"],
                }
                for k, v in metric_d["data"].items()
            ]
        return_dict = {"metrics": return_dict}
        serializer = PeriodMetricUsageResponseSerializer(data=return_dict)
        serializer.is_valid(raise_exception=True)
        ret = serializer.validated_data
        make_all_decimals_floats(ret)
        return JsonResponse(ret, status=status.HTTP_200_OK)


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
        customers = Customer.objects.filter(organization=organization)
        customers_dict = {"customers": []}
        for customer in customers:
            customer_dict = {}
            sub_usg_summaries = get_customer_usage_and_revenue(customer)
            customer_dict["total_revenue_due"] = sum(
                x["total_revenue_due"] for x in sub_usg_summaries["subscriptions"]
            )
            customer_dict["customer_name"] = customer.name
            customer_dict["customer_id"] = customer.customer_id
            customer_dict["subscriptions"] = [
                x["billing_plan"]["name"] for x in sub_usg_summaries["subscriptions"]
            ]

            serializer = CustomerRevenueSerializer(data=customer_dict)
            serializer.is_valid(raise_exception=True)
            customers_dict["customers"].append(serializer.validated_data)
        serializer = CustomerRevenueSummarySerializer(data=customers_dict)
        serializer.is_valid(raise_exception=True)
        ret = serializer.validated_data
        make_all_decimals_floats(ret)
        return JsonResponse(ret, status=status.HTTP_200_OK)
