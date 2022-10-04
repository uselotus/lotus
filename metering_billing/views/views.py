import datetime
from decimal import Decimal

import posthog
import stripe
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from drf_spectacular.utils import extend_schema, inline_serializer
from lotus.settings import SELF_HOSTED, STRIPE_SECRET_KEY
from metering_billing.invoice import generate_invoice
from metering_billing.models import APIToken, BillableMetric, Customer, Subscription
from metering_billing.permissions import HasUserAPIKey
from metering_billing.serializers.internal_serializers import *
from metering_billing.serializers.model_serializers import *
from metering_billing.view_utils import RevenueCalcGranularity, dates_bwn_twodates
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..auth_utils import parse_organization
from ..invoice import generate_adjustment_invoice
from ..utils import make_all_dates_times_strings, make_all_decimals_floats
from ..view_utils import (
    calculate_sub_pc_usage_revenue,
    get_customer_usage_and_revenue,
    get_metric_usage,
)

stripe.api_key = STRIPE_SECRET_KEY


def import_stripe_customers(organization):
    """
    If customer exists in Stripe and also exists in Lotus (compared by matching names), then update the customer's payment provider ID from Stripe.
    """
    num_cust_added = 0
    org_ppis = organization.payment_provider_ids
    if "stripe" in org_ppis or (SELF_HOSTED and STRIPE_SECRET_KEY != ""):
        stripe_cust_kwargs = {}
        if org_ppis.get("stripe") != "":
            stripe_cust_kwargs["stripe_account"] = org_ppis.get("stripe")
        stripe_customers_response = stripe.Customer.list(**stripe_cust_kwargs)
        for stripe_customer in stripe_customers_response.auto_paging_iter():
            try:
                customer = Customer.objects.get(
                    organization=organization, name=stripe_customer.name
                )
                customer.payment_provider = "stripe"
                customer.payment_provider_id = stripe_customer.id
                customer.save()
                num_cust_added += 1
            except Customer.DoesNotExist:
                pass
    return num_cust_added


class InitializeStripeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: inline_serializer(
                "StripeConnectedResponse",
                fields={"connected": serializers.BooleanField()},
            )
        },
    )
    def get(self, request, format=None):
        """
        Check to see if user has connected their Stripe account.
        """

        organization = parse_organization(request)
        org_ppis = organization.payment_provider_ids
        stripe_id = org_ppis.get("stripe")

        if (stripe_id and len(stripe_id) > 0) or (
            SELF_HOSTED and STRIPE_SECRET_KEY != ""
        ):
            return Response({"connected": True}, status=status.HTTP_200_OK)
        else:
            return Response({"connected": False}, status=status.HTTP_200_OK)

    @extend_schema(
        request=inline_serializer(
            "StripeConnectRequest",
            fields={"authorization_code": serializers.CharField()},
        ),
        responses={
            200: inline_serializer(
                "StripeImportResponse",
                fields={"success": serializers.BooleanField()},
            ),
            400: inline_serializer(
                "StripeImportError",
                fields={
                    "success": serializers.BooleanField(),
                    "details": serializers.CharField(),
                },
            ),
        },
    )
    def post(self, request, format=None):
        """
        Initialize Stripe after user inputs an API key.
        """

        data = request.data

        if data is None:
            return Response(
                {"success": False, "details": "No data provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        organization = parse_organization(request)
        stripe_code = data["authorization_code"]

        try:
            response = stripe.OAuth.token(
                grant_type="authorization_code",
                code=stripe_code,
            )
        except:
            return Response(
                {"success": False, "details": "Invalid authorization code"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if "error" in response:
            return Response(
                {"success": False, "details": response["error"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        connected_account_id = response["stripe_user_id"]

        organization.payment_provider_ids.stripe = connected_account_id
        organization.save()

        n_cust_added = import_stripe_customers(organization)

        organization.save()

        posthog.capture(
            organization.company_name,
            event="connect_stripe_customers",
            properties={
                "num_cust_added": n_cust_added,
            },
        )

        return Response({"success": True}, status=status.HTTP_201_CREATED)


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
            "total_revenue_period_1": Decimal(0),
            "daily_usage_revenue_period_2": {},
            "total_revenue_period_2": Decimal(0),
        }
        if all_org_billable_metrics.count() > 0:
            for billable_metric in all_org_billable_metrics:
                for p_start, p_end, p_num in [
                    (p1_start, p1_end, 1),
                    (p2_start, p2_end, 2),
                ]:
                    return_dict[f"daily_usage_revenue_period_{p_num}"][
                        billable_metric.id
                    ] = {
                        "metric": str(billable_metric),
                        "data": {
                            x: Decimal(0) for x in dates_bwn_twodates(p_start, p_end)
                        },
                        "total_revenue": Decimal(0),
                    }
            for p_start, p_end, p_num in [(p1_start, p1_end, 1), (p2_start, p2_end, 2)]:
                total_period_rev = Decimal(0)
                subs = (
                    Subscription.objects.filter(
                        Q(start_date__range=[p_start, p_end])
                        | Q(end_date__range=[p_start, p_end]),
                        organization=organization,
                    )
                    .select_related("billing_plan")
                    .select_related("customer")
                    .prefetch_related("billing_plan__components")
                    .prefetch_related("billing_plan__components__billable_metric")
                )
                for sub in subs:
                    bp = sub.billing_plan
                    flat_bill_date = (
                        sub.start_date if bp.pay_in_advance else sub.end_date
                    )
                    if p_start <= flat_bill_date <= p_end:
                        total_period_rev += bp.flat_rate.amount
                    for plan_component in bp.components.all():
                        billable_metric = plan_component.billable_metric
                        revenue_per_day = calculate_sub_pc_usage_revenue(
                            plan_component,
                            billable_metric,
                            sub.customer,
                            sub.start_date,
                            sub.end_date,
                            revenue_granularity=RevenueCalcGranularity.DAILY,
                        )
                        metric_dict = return_dict[
                            f"daily_usage_revenue_period_{p_num}"
                        ][billable_metric.id]
                        for date, d in revenue_per_day.items():
                            if date in metric_dict["data"]:
                                usage_cost = Decimal(d["revenue"])
                                metric_dict["data"][date] += usage_cost
                                metric_dict["total_revenue"] += usage_cost
                                total_period_rev += usage_cost
                return_dict[f"total_revenue_period_{p_num}"] = total_period_rev
        for p_num in [1, 2]:
            dailies = return_dict[f"daily_usage_revenue_period_{p_num}"]
            dailies = [daily_dict for metric_id, daily_dict in dailies.items()]
            return_dict[f"daily_usage_revenue_period_{p_num}"] = dailies
            for dic in dailies:
                dic["data"] = [
                    {"date": k, "metric_revenue": v} for k, v in dic["data"].items()
                ]
        serializer = PeriodMetricRevenueResponseSerializer(data=return_dict)
        serializer.is_valid(raise_exception=True)
        ret = serializer.validated_data
        make_all_decimals_floats(ret)
        make_all_dates_times_strings(ret)
        return Response(ret, status=status.HTTP_200_OK)


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
        ).values_list("is_new", flat=True)
        return_dict["period_1_total_subscriptions"] = len(p1_subs)
        return_dict["period_1_new_subscriptions"] = sum(p1_subs)

        p2_subs = Subscription.objects.filter(
            Q(start_date__range=[p2_start, p2_end])
            | Q(end_date__range=[p2_start, p2_end]),
            organization=organization,
        ).values_list("is_new", flat=True)
        return_dict["period_2_total_subscriptions"] = len(p2_subs)
        return_dict["period_2_new_subscriptions"] = sum(p2_subs)

        serializer = PeriodSubscriptionsResponseSerializer(data=return_dict)
        serializer.is_valid(raise_exception=True)
        ret = serializer.validated_data
        make_all_decimals_floats(ret)
        return Response(ret, status=status.HTTP_200_OK)


class PeriodMetricUsageView(APIView):

    permission_classes = [IsAuthenticated]

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
            usage_summary = get_metric_usage(
                metric, q_start, q_end, time_period_agg="day"
            )
            return_dict[str(metric)] = {
                "data": {},
                "total_usage": 0,
                "top_n_customers": {},
            }
            metric_dict = return_dict[str(metric)]
            for obj in usage_summary:
                customer, date, qty = [
                    obj[key]
                    for key in ["customer_name", "time_created_quantized", "usage_qty"]
                ]
                date = date.date()
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
            metric_d["data"] = sorted(metric_d["data"], key=lambda x: x["date"])
        return_dict = {"metrics": return_dict}
        serializer = PeriodMetricUsageResponseSerializer(data=return_dict)
        serializer.is_valid(raise_exception=True)
        ret = serializer.validated_data
        make_all_decimals_floats(ret)
        return Response(ret, status=status.HTTP_200_OK)


@extend_schema(
    responses={
        200: inline_serializer(
            name="APIKeyCreateSuccess",
            fields={
                "api_key": serializers.CharField(),
            },
        ),
    },
)
class APIKeyCreate(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        """
        Revokes the current API key and returns a new one.
        """
        organization = parse_organization(request)
        APIToken.objects.filter(organization=organization).delete()
        api_key, key = APIToken.objects.create_key(
            name="new_api_key", organization=organization
        )
        posthog.capture(
            organization.company_name,
            event="create_api_key",
            properties={},
        )
        return Response({"api_key": key}, status=status.HTTP_200_OK)


class SettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        """
        Get the current settings for the organization.
        """
        organization = parse_organization(request)
        return Response(
            {"organization": organization.company_name}, status=status.HTTP_200_OK
        )


class CustomersSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: CustomerSummarySerializer},
    )
    def get(self, request, format=None):
        """
        Get the current settings for the organization.
        """
        organization = parse_organization(request)
        customers = Customer.objects.filter(organization=organization).prefetch_related(
            Prefetch(
                "subscription_set",
                queryset=Subscription.objects.filter(organization=organization),
                to_attr="subscriptions",
            ),
            Prefetch(
                "subscription_set__billing_plan",
                queryset=BillingPlan.objects.filter(organization=organization),
                to_attr="billing_plans",
            ),
        )
        serializer = CustomerSummarySerializer(customers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CustomerDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: CustomerDetailSerializer},
    )
    def get(self, request, format=None):
        """
        Get the current settings for the organization.
        """
        organization = parse_organization(request)
        customer_id = request.query_params.get("customer_id")
        customer = (
            Customer.objects.filter(organization=organization, customer_id=customer_id)
            .prefetch_related(
                Prefetch(
                    "subscription_set",
                    queryset=Subscription.objects.filter(organization=organization),
                    to_attr="subscriptions",
                ),
                Prefetch(
                    "subscription_set__billing_plan",
                    queryset=BillingPlan.objects.filter(organization=organization),
                    to_attr="billing_plans",
                ),
            )
            .get()
        )
        sub_usg_summaries = get_customer_usage_and_revenue(customer)
        total_revenue_due = sum(
            x["total_revenue_due"] for x in sub_usg_summaries["subscriptions"]
        )
        invoices = Invoice.objects.filter(
            organization__company_name=organization.company_name,
            customer__customer_id=customer.customer_id,
        )
        serializer = CustomerDetailSerializer(
            customer,
            context={
                "total_revenue_due": total_revenue_due,
                "invoices": invoices,
            },
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class CustomersWithRevenueView(APIView):

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: CustomerWithRevenueSerializer(many=True)},
    )
    def get(self, request, format=None):
        """
        Return current usage for a customer during a given billing period.
        """
        organization = parse_organization(request)
        customers = Customer.objects.filter(organization=organization)
        cust = []
        for customer in customers:
            sub_usg_summaries = get_customer_usage_and_revenue(customer)
            customer_total_revenue_due = sum(
                x["total_revenue_due"] for x in sub_usg_summaries["subscriptions"]
            )
            serializer = CustomerWithRevenueSerializer(
                customer,
                context={
                    "total_revenue_due": customer_total_revenue_due,
                },
            )
            cust.append(serializer.data)
        make_all_decimals_floats(cust)
        return Response(cust, status=status.HTTP_200_OK)


class EventPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[EventPreviewRequestSerializer],
        responses={200: EventPreviewSerializer},
    )
    def get(self, request, format=None):
        """
        Pagination-enabled endpoint for retrieving an organization's event stream.
        """
        serializer = EventPreviewRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        page_number = serializer.validated_data.get("page")
        organization = parse_organization(request)
        now = datetime.datetime.now(datetime.timezone.utc)
        events = (
            Event.objects.filter(organization=organization, time_created__lt=now)
            .order_by("-time_created")
            .select_related("customer")
        )
        paginator = Paginator(events, per_page=20)
        page_obj = paginator.get_page(page_number)
        ret = {}
        ret["total_pages"] = paginator.num_pages
        ret["events"] = list(page_obj.object_list)
        serializer = EventPreviewSerializer(ret)
        if page_number == 1:
            posthog.capture(
                organization.company_name,
                event="event_preview",
                properties={
                    "num_events": len(ret["events"]),
                },
            )
        return Response(serializer.data, status=status.HTTP_200_OK)


class DraftInvoiceView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[DraftInvoiceRequestSerializer],
        responses={200: InvoiceSerializer},
    )
    def get(self, request, format=None):
        """
        Pagination-enabled endpoint for retrieving an organization's event stream.
        """
        organization = parse_organization(request)
        serializer = DraftInvoiceRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        try:
            customer = Customer.objects.get(
                organization=organization,
                customer_id=serializer.validated_data.get("customer_id"),
            )
        except:
            return Response(
                {"error": "Customer not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        subs = Subscription.objects.filter(
            customer=customer, organization=organization, status="active"
        )
        invoices = [generate_invoice(sub, draft=True) for sub in subs]
        serializer = InvoiceSerializer(invoices, many=True)
        posthog.capture(
            organization.company_name,
            event="draft_invoice",
            properties={},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class CancelSubscriptionView(APIView):
    permission_classes = [IsAuthenticated | HasUserAPIKey]

    @extend_schema(
        request=CancelSubscriptionRequestSerializer,
        responses={
            200: inline_serializer(
                name="CancelSubscriptionSuccess",
                fields={
                    "status": serializers.ChoiceField(choices=["success"]),
                    "detail": serializers.CharField(),
                },
            ),
            400: inline_serializer(
                name="CancelSubscriptionFailure",
                fields={
                    "status": serializers.ChoiceField(choices=["error"]),
                    "detail": serializers.CharField(),
                },
            ),
        },
    )
    def post(self, request, format=None):
        serializer = CancelSubscriptionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization = parse_organization(request)
        sub_uid = serializer.validated_data["subscription_uid"]
        bill_now = serializer.validated_data["bill_now"]
        revoke_access = serializer.validated_data["revoke_access"]
        try:
            sub = Subscription.objects.get(
                organization=organization, subscription_uid=sub_uid
            )
        except:
            return Response(
                {"status": "error", "detail": "Subscription not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if sub.status == "ended":
            return Response(
                {"status": "error", "detail": "Subscription already ended"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        elif sub.status == "not_started":
            Subscription.objects.get(
                organization=organization, subscription_uid=sub_uid
            ).delete()
            return Response(
                {
                    "status": "success",
                    "detail": "Subscription hadn't started, has been deleted",
                },
                status=status.HTTP_200_OK,
            )
        sub.auto_renew = False
        if revoke_access:
            sub.status = "canceled"
        sub.save()
        posthog.capture(
            organization.company_name,
            event="cancel_subscription",
            properties={},
        )
        if bill_now and revoke_access:
            generate_invoice(sub, issue_date=datetime.datetime.now().date())
            return Response(
                {
                    "status": "success",
                    "detail": "Created invoice and payment intent for subscription",
                },
                status=status.HTTP_200_OK,
            )
        else:
            return Response(
                {
                    "status": "success",
                    "detail": "Subscription ended without generating invoice",
                },
                status=status.HTTP_200_OK,
            )


class GetCustomerAccessView(APIView):
    permission_classes = [IsAuthenticated | HasUserAPIKey]

    @extend_schema(
        parameters=[GetCustomerAccessRequestSerializer],
        responses={
            200: inline_serializer(
                name="GetCustomerAccessSuccess",
                fields={
                    "access": serializers.BooleanField(),
                    "usages": serializers.ListField(
                        child=inline_serializer(
                            name="MetricUsageSerializer",
                            fields={
                                "metric_name": serializers.CharField(),
                                "metric_usage": serializers.FloatField(),
                                "metric_limit": serializers.FloatField(),
                                "access": serializers.BooleanField(),
                            },
                        ),
                        required=False,
                    ),
                },
            ),
            400: inline_serializer(
                name="GetCustomerAccessFailure",
                fields={
                    "status": serializers.ChoiceField(choices=["error"]),
                    "detail": serializers.CharField(),
                },
            ),
        },
    )
    def get(self, request, format=None):
        serializer = GetCustomerAccessRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        organization = parse_organization(request)
        posthog.capture(
            organization.company_name,
            event="get_access",
            properties={},
        )
        customer_id = serializer.validated_data["customer_id"]
        try:
            customer = Customer.objects.get(
                organization=organization, customer_id=customer_id
            )
        except Customer.DoesNotExist:
            return Response(
                {"status": "error", "detail": "Customer not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        event_name = serializer.validated_data.get("event_name")
        feature_name = serializer.validated_data.get("feature_name")
        event_limit_type = serializer.validated_data.get("event_limit_type")
        subscriptions = Subscription.objects.select_related("billing_plan").filter(
            organization=organization,
            status="active",
            customer=customer,
        )
        if event_name:
            subscriptions = subscriptions.prefetch_related(
                "billing_plan__components", "billing_plan__components__billable_metric"
            )
            metric_usages = {}
            for sub in subscriptions:
                for component in sub.billing_plan.components.all():
                    if component.billable_metric.event_name == event_name:
                        metric = component.billable_metric
                        if event_limit_type == "free":
                            metric_limit = component.free_metric_units
                        elif event_limit_type == "total":
                            metric_limit = component.max_metric_units
                        if not metric_limit:
                            metric_usages[metric.billable_metric_name] = {
                                "metric_usage": None,
                                "metric_limit": None,
                                "access": True,
                            }
                            continue
                        metric_usage = get_metric_usage(
                            metric,
                            query_start_date=sub.start_date,
                            query_end_date=sub.end_date,
                            customer=customer,
                        )
                        metric_usage = list(metric_usage)
                        if len(metric_usage) > 0:
                            metric_usage = metric_usage[0]["usage_qty"]
                        else:
                            metric_usage = 0
                        metric_usages[metric.billable_metric_name] = {
                            "metric_usage": metric_usage,
                            "metric_limit": metric_limit,
                            "access": metric_usage < metric_limit,
                        }
            if all(v["access"] for k, v in metric_usages.items()):
                return Response(
                    {
                        "access": True,
                        "usages": [
                            v.update({"metric_name": k})
                            for k, v in metric_usages.items()
                        ],
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {
                        "access": False,
                        "usages": [
                            v.update({"metric_name": k})
                            for k, v in metric_usages.items()
                        ],
                    },
                    status=status.HTTP_200_OK,
                )
        elif feature_name:
            subscriptions = subscriptions.prefetch_related("billing_plan__features")
            for sub in subscriptions:
                for feature in sub.billing_plan.features.all():
                    if feature.feature_name == feature_name:
                        return Response(
                            {"access": True},
                            status=status.HTTP_200_OK,
                        )

        return Response(
            {"access": False},
            status=status.HTTP_200_OK,
        )


class UpdateBillingPlanView(APIView):
    permission_classes = [IsAuthenticated | HasUserAPIKey]

    @extend_schema(
        request=UpdateBillingPlanRequestSerializer,
        responses={
            200: inline_serializer(
                name="UpdateBillingPlanSuccess",
                fields={
                    "status": serializers.ChoiceField(choices=["success"]),
                    "detail": serializers.CharField(),
                },
            ),
            400: inline_serializer(
                name="UpdateBillingPlanFailure",
                fields={
                    "status": serializers.ChoiceField(choices=["error"]),
                    "detail": serializers.CharField(),
                },
            ),
        },
    )
    def post(self, request, format=None):
        organization = parse_organization(request)
        serializer = UpdateBillingPlanRequestSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        old_billing_plan_id = serializer.validated_data["old_billing_plan_id"]
        old_bp = BillingPlan.objects.get(
            organization=organization, billing_plan_id=old_billing_plan_id
        )
        updated_bp = serializer.save()
        update_behavior = serializer.validated_data["update_behavior"]

        posthog.capture(
            organization.company_name,
            event="update_billing_plan",
            properties={},
        )
        if update_behavior == "replace_immediately":
            today = datetime.date.today()
            sub_qs = Subscription.objects.filter(
                organization=organization,
                billing_plan=old_bp,
            )
            for sub in sub_qs:
                start = sub.start_date
                updated_end = updated_bp.calculate_end_date(start)
                if updated_end < today:
                    return Response(
                        {
                            "status": "error",
                            "detail": "At least one subscription would have an updated end date in the past. Please choose a different update behavior.",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            if updated_bp.pay_in_advance and not old_bp.pay_in_advance:
                # need to bill the customer immediately for the flat fee (prorated)
                for sub in sub_qs:
                    sub.billing_plan = updated_bp
                    sub.save()
                    new_sub_daily_cost_dict = sub.prorated_flat_costs_dict
                    prorated_cost = sum(new_sub_daily_cost_dict.values())
                    due = (
                        prorated_cost
                        - sub.customer.balance
                        - sub.flat_fee_already_billed
                    )
                    sub.flat_fee_already_billed = prorated_cost
                    sub.save()
                    if due > 0:
                        sub.customer.balance = 0
                        today = datetime.date.today()
                        generate_adjustment_invoice(sub, today, due)
                    else:
                        sub.customer.balance = abs(due)
                    sub.customer.save()
            old_bp.delete()
            return Response(
                {
                    "status": "success",
                    "detail": "All subscriptions updated with new plan and old plan deleted.",
                },
                status=status.HTTP_200_OK,
            )
        elif update_behavior == "replace_on_renewal":
            old_bp.scheduled_for_deletion = True
            old_bp.replacement_billing_plan = updated_bp
            BillingPlan.objects.filter(replacement_billing_plan=old_bp).update(
                replacement_billing_plan=updated_bp
            )
            old_bp.save()
            return Response(
                {
                    "status": "success",
                    "detail": "Billing plan scheduled for deletion. Auto-renews of subscriptions with this plan will use the updated version instead. Subscriptions set to be renewed with this plan will now be renewed with the updated plan. Once there are no more subscriptions using this plan, it will be deleted.",
                },
                status=status.HTTP_200_OK,
            )


class UpdateSubscriptionBillingPlanView(APIView):
    permission_classes = [IsAuthenticated | HasUserAPIKey]

    @extend_schema(
        request=UpdateSubscriptionBillingPlanRequestSerializer,
        responses={
            200: inline_serializer(
                name="UpdateSubscriptionBillingPlanSuccess",
                fields={
                    "status": serializers.ChoiceField(choices=["success"]),
                    "detail": serializers.CharField(),
                },
            ),
            400: inline_serializer(
                name="UpdateSubscriptionBillingPlanFailure",
                fields={
                    "status": serializers.ChoiceField(choices=["error"]),
                    "detail": serializers.CharField(),
                },
            ),
        },
    )
    def post(self, request, format=None):
        serializer = UpdateSubscriptionBillingPlanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization = parse_organization(request)

        subscription_uid = serializer.validated_data["subscription_uid"]
        try:
            sub = Subscription.objects.get(
                organization=organization,
                subscription_uid=subscription_uid,
                status="active",
            ).select_related("billing_plan")
        except Subscription.DoesNotExist:
            return Response(
                {
                    "status": "error",
                    "detail": f"Subscription with id {subscription_uid} not found.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_billing_plan_id = serializer.validated_data["new_billing_plan_id"]
        try:
            updated_bp = BillingPlan.objects.get(
                organization=organization, billing_plan_id=new_billing_plan_id
            )
        except BillingPlan.DoesNotExist:
            return Response(
                {
                    "status": "error",
                    "detail": f"Billing plan with id {new_billing_plan_id} not found.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        update_behavior = serializer.validated_data["update_behavior"]
        if update_behavior == "replace_immediately":
            sub.billing_plan = updated_bp
            sub.save()
            if updated_bp.pay_in_advance:
                new_sub_daily_cost_dict = sub.prorated_flat_costs_dict
                prorated_cost = sum(new_sub_daily_cost_dict.values())
                due = prorated_cost - sub.customer.balance - sub.flat_fee_already_billed
                if due < 0:
                    customer = sub.customer
                    customer.balance = abs(due)
                elif due > 0:
                    today = datetime.date.today()
                    generate_adjustment_invoice(sub, today, due)
                    sub.flat_fee_already_billed += due
                    sub.save()
                    sub.customer.balance = 0
                    sub.customer.save()
            return Response(
                {
                    "status": "success",
                    "detail": f"Subscription {subscription_uid} updated to use billing plan {new_billing_plan_id}.",
                },
                status=status.HTTP_200_OK,
            )
        elif update_behavior == "replace_on_renewal":
            sub.auto_renew_billing_plan = updated_bp
            sub.save()
            return Response(
                {
                    "status": "success",
                    "detail": f"Subscription {subscription_uid} scheduled to be updated to use billing plan {new_billing_plan_id} on next renewal.",
                },
                status=status.HTTP_200_OK,
            )
