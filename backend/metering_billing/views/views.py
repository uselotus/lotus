import datetime
from decimal import Decimal

import posthog
from dateutil import parser
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q, F
from drf_spectacular.utils import extend_schema, inline_serializer
from metering_billing.invoice import generate_invoice
from metering_billing.models import APIToken, BillableMetric, Customer, Subscription
from metering_billing.permissions import HasUserAPIKey
from metering_billing.serializers.internal_serializers import *
from metering_billing.serializers.model_serializers import *
from metering_billing.view_utils import (
    REVENUE_CALC_GRANULARITY,
    periods_bwn_twodates,
    sync_payment_provider_customers,
)
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..auth_utils import parse_organization
from ..invoice import generate_invoice
from ..utils import (
    SUB_STATUS_TYPES,
    convert_to_decimal,
    make_all_dates_times_strings,
    make_all_decimals_floats,
)
from ..view_utils import (
    calculate_sub_pc_usage_revenue,
    get_customer_usage_and_revenue,
    get_metric_usage,
)

POSTHOG_PERSON = settings.POSTHOG_PERSON


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
                            x: Decimal(0)
                            for x in periods_bwn_twodates(
                                REVENUE_CALC_GRANULARITY.DAILY, p_start, p_end
                            )
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
                            revenue_granularity=REVENUE_CALC_GRANULARITY.DAILY,
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
                    {"date": str(k.date()), "metric_revenue": v}
                    for k, v in dic["data"].items()
                ]
        serializer = PeriodMetricRevenueResponseSerializer(data=return_dict)
        serializer.is_valid(raise_exception=True)
        ret = serializer.validated_data
        ret = make_all_decimals_floats(ret)
        ret = make_all_dates_times_strings(ret)
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
        ret = make_all_decimals_floats(ret)
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
        if type(q_start) == str:
            q_start = parser.parse(q_start).date()
        if type(q_end) == str:
            q_end = parser.parse(q_end).date()

        metrics = BillableMetric.objects.filter(organization=organization)
        return_dict = {}
        for metric in metrics:
            usage_summary = get_metric_usage(
                metric,
                q_start,
                q_end,
                granularity=REVENUE_CALC_GRANULARITY.DAILY,
            )
            return_dict[str(metric)] = {
                "data": {},
                "total_usage": 0,
                "top_n_customers": {},
            }
            metric_dict = return_dict[str(metric)]
            for customer_name, period_dict in usage_summary.items():
                for datetime, qty in period_dict.items():
                    qty = convert_to_decimal(qty)
                    if datetime not in metric_dict["data"]:
                        metric_dict["data"][datetime] = {
                            "total_usage": Decimal(0),
                            "customer_usages": {},
                        }
                    date_dict = metric_dict["data"][datetime]
                    date_dict["total_usage"] += qty
                    date_dict["customer_usages"][customer_name] = qty
                    metric_dict["total_usage"] += qty
                    if customer_name not in metric_dict["top_n_customers"]:
                        metric_dict["top_n_customers"][customer_name] = 0
                    metric_dict["top_n_customers"][customer_name] += qty
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
                    "date": str(k.date()),
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
        ret = make_all_decimals_floats(ret)
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
            POSTHOG_PERSON if POSTHOG_PERSON else organization.company_name,
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
        responses={200: AllSubstitutionResultsSerializer},
    )
    def get(self, request, format=None):
        """
        Get the current settings for the organization.
        """
        organization = parse_organization(request)
        customers = Customer.objects.filter(organization=organization).prefetch_related(
            Prefetch(
                "customer_subscriptions",
                queryset=Subscription.objects.filter(organization=organization),
                to_attr="subscriptions",
            ),
            Prefetch(
                "customer_subscriptions__billing_plan",
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
                    "customer_subscriptions",
                    queryset=Subscription.objects.filter(organization=organization),
                    to_attr="subscriptions",
                ),
                Prefetch(
                    "subscriptions__billing_plan",
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
        cust = make_all_decimals_floats(cust)
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
                POSTHOG_PERSON if POSTHOG_PERSON else organization.company_name,
                event="event_preview",
                properties={
                    "num_events": len(ret["events"]),
                },
            )
        return Response(serializer.data, status=status.HTTP_200_OK)


class DraftInvoiceView(APIView):
    permission_classes = [IsAuthenticated | HasUserAPIKey]

    @extend_schema(
        parameters=[DraftInvoiceRequestSerializer],
        responses={200: DraftInvoiceSerializer},
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
            customer=customer, organization=organization, status=SUB_STATUS_TYPES.ACTIVE
        )
        invoices = [generate_invoice(sub, draft=True) for sub in subs]
        serializer = DraftInvoiceSerializer(invoices, many=True)
        posthog.capture(
            POSTHOG_PERSON if POSTHOG_PERSON else organization.company_name,
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
        sub_id = serializer.validated_data["subscription_id"]
        bill_now = serializer.validated_data["bill_now"]
        revoke_access = serializer.validated_data["revoke_access"]
        try:
            sub = Subscription.objects.get(
                organization=organization, subscription_id=sub_id
            )
        except:
            return Response(
                {"status": "error", "detail": "Subscription not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if sub.status == SUB_STATUS_TYPES.ENDED:
            return Response(
                {"status": "error", "detail": "Subscription already ended"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        elif sub.status == SUB_STATUS_TYPES.NOT_STARTED:
            Subscription.objects.get(
                organization=organization, subscription_id=sub_id
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
            sub.status = SUB_STATUS_TYPES.CANCELED
        sub.save()
        posthog.capture(
            POSTHOG_PERSON if POSTHOG_PERSON else organization.company_name,
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
            POSTHOG_PERSON if POSTHOG_PERSON else organization.company_name,
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
            status=SUB_STATUS_TYPES.ACTIVE,
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
                            sub.start_date,
                            sub.end_date,
                            granularity=REVENUE_CALC_GRANULARITY.TOTAL,
                            customer=customer,
                        )
                        metric_usage = metric_usage.get(customer.name, {})
                        metric_usage = list(metric_usage.values())
                        if len(metric_usage) > 0:
                            metric_usage = metric_usage[0]
                        else:
                            metric_usage = Decimal(0)
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
            POSTHOG_PERSON if POSTHOG_PERSON else organization.company_name,
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
            # need to bill the customer immediately for the flat fee (prorated)
            for sub in sub_qs:
                sub.billing_plan = updated_bp
                sub.save()
                if updated_bp.pay_in_advance and not old_bp.pay_in_advance:
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
                        generate_invoice(sub, draft=False, issue_date=today, amount=due)
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

        subscription_id = serializer.validated_data["subscription_id"]
        try:
            sub = Subscription.objects.get(
                organization=organization,
                subscription_id=subscription_id,
                status=SUB_STATUS_TYPES.ACTIVE,
            ).select_related("billing_plan")
        except Subscription.DoesNotExist:
            return Response(
                {
                    "status": "error",
                    "detail": f"Subscription with id {subscription_id} not found.",
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
                    generate_invoice(sub, draft=False, issue_date=today, amount=due)
                    sub.flat_fee_already_billed += due
                    sub.save()
                    sub.customer.balance = 0
                    sub.customer.save()
            return Response(
                {
                    "status": "success",
                    "detail": f"Subscription {subscription_id} updated to use billing plan {new_billing_plan_id}.",
                },
                status=status.HTTP_200_OK,
            )
        elif update_behavior == "replace_on_renewal":
            sub.auto_renew_billing_plan = updated_bp
            sub.save()
            return Response(
                {
                    "status": "success",
                    "detail": f"Subscription {subscription_id} scheduled to be updated to use billing plan {new_billing_plan_id} on next renewal.",
                },
                status=status.HTTP_200_OK,
            )


class MergeCustomersView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=MergeCustomersRequestSerializer,
        responses={
            200: inline_serializer(
                name="MergeCustomerSuccess",
                fields={
                    "status": serializers.ChoiceField(choices=["success"]),
                    "detail": serializers.CharField(),
                },
            ),
            400: inline_serializer(
                name="MergeCustomerFailure",
                fields={
                    "status": serializers.ChoiceField(choices=["error"]),
                    "detail": serializers.CharField(),
                },
            ),
        },
    )
    def post(self, request, format=None):
        serializer = MergeCustomersRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization = parse_organization(request)

        try:
            cust1_id = serializer.validated_data["subscription_id"]
            cust1 = Customer.objects.get(
                organization=organization, customer_id=cust1_id
            )
        except Customer.DoesNotExist:
            return Response(
                {
                    "status": "error",
                    "detail": f"Customer with id {cust1_id} not found.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            cust2_id = serializer.validated_data["subscription_id"]
            cust2 = Customer.objects.get(
                organization=organization, customer_id=cust2_id
            )
        except Customer.DoesNotExist:
            return Response(
                {
                    "status": "error",
                    "detail": f"Customer with id {cust2_id} not found.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(set(cust1.sources) & set(cust2.sources)) > 0:
            return Response(
                {
                    "status": "error",
                    "detail": f"Customers {cust1_id} and {cust2_id} have overlapping sources.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_customer_dict = {
            "organization": organization,
            "name": cust1.name,
            "email": cust1.email,
            "payment_providers": cust1.payment_providers.update(
                cust2.payment_providers
            ),
            "sources": cust1.sources + cust2.sources,
            "properties": cust1.properties.update(cust2.properties),
            "balance": cust1.balance + cust2.balance,
        }
        if "lotus" in cust1.sources:
            new_customer_dict["customer_id"] = cust1.customer_id
        elif "lotus" in cust2.sources:
            new_customer_dict["customer_id"] = cust2.customer_id
        else:
            new_customer_dict["customer_id"] = cust1.customer_id

        cust1.delete()
        cust2.delete()
        new_customer = Customer.objects.create(**new_customer_dict)
        new_cust_id = new_customer.customer_id
        return Response(
            {
                "status": "success",
                "detail": f"Customers w/ ids {cust1_id} and {cust2_id} were succesfully merged into customer with id {new_cust_id}.",
            },
            status=status.HTTP_200_OK,
        )


class SyncCustomersView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=inline_serializer(
            name="SyncCustomersRequest",
            fields={},
        ),
        responses={
            200: inline_serializer(
                name="SyncCustomerSuccess",
                fields={
                    "status": serializers.ChoiceField(choices=["success"]),
                    "detail": serializers.CharField(),
                },
            ),
            400: inline_serializer(
                name="SyncCustomerFailure",
                fields={
                    "status": serializers.ChoiceField(choices=["error"]),
                    "detail": serializers.CharField(),
                },
            ),
        },
    )
    def post(self, request, format=None):
        organization = parse_organization(request)

        try:
            success_providers = sync_payment_provider_customers(organization)
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "detail": f"Error syncing customers: {e}",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "status": "success",
                "detail": f"Customers succesfully imported from {success_providers}.",
            },
            status=status.HTTP_201_CREATED,
        )


class ExperimentalToActiveView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ExperimentalToActiveRequestSerializer(),
        responses={
            200: inline_serializer(
                name="ExperimentalToActiveSuccess",
                fields={
                    "status": serializers.ChoiceField(choices=["success"]),
                    "detail": serializers.CharField(),
                },
            ),
            400: inline_serializer(
                name="ExperimentalToActiveFailure",
                fields={
                    "status": serializers.ChoiceField(choices=["error"]),
                    "detail": serializers.CharField(),
                },
            ),
        },
    )
    def post(self, request, format=None):
        organization = parse_organization(request)
        serializer = ExperimentalToActiveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        billing_plan = serializer.validated_data["billing_plan_id"]
        try:
            billing_plan.status = PLAN_STATUS.ACTIVE
        except Exception as e:
            return Response(
                {
                    "status": "error",
                    "detail": f"Error converting experimental plan to active plan: {e}",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "status": "success",
                "detail": f"Plan {billing_plan} succesfully converted from experimental to active.",
            },
            status=status.HTTP_200_OK,
        )


class PlansByNumCustomersView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=inline_serializer(
            name="PlansByNumCustomersRequest",
            fields={},
        ),
        responses={
            200: inline_serializer(
                name="PlansByNumCustomers",
                fields={
                    "results": serializers.ListField(
                        child=inline_serializer(
                            name="SinglePlanNumCustomers",
                            fields={
                                "plan_name": serializers.CharField(),
                                "num_customers": serializers.IntegerField(),
                                "percent_total": serializers.FloatField(),
                            },
                        )
                    ),
                    "status": serializers.ChoiceField(choices=["success"]),
                },
            ),
        },
    )
    def get(self, request, format=None):
        organization = parse_organization(request)
        plans = (
            Subscription.objects.filter(
                organization=organization, status=SUB_STATUS_TYPES.ACTIVE
            )
            .values(plan_name=F("billing_plan__name"))
            .annotate(num_customers=Count("customer"))
            .order_by("-num_customers")
        )
        tot_plans = sum([plan["num_customers"] for plan in plans])
        plans = [
            {**plan, "percent_total": plan["num_customers"] / tot_plans}
            for plan in plans
        ]
        return Response(
            {
                "status": "success",
                "results": plans,
            },
            status=status.HTTP_200_OK,
        )
