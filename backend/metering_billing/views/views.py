import logging
from decimal import Decimal

import pytz
from django.conf import settings
from django.db.models import Count, F, Q, Sum
from drf_spectacular.utils import extend_schema, inline_serializer
from metering_billing.exceptions import (
    ExternalConnectionFailure,
    ExternalConnectionInvalid,
)
from metering_billing.models import (
    Event,
    Invoice,
    Metric,
    Organization,
    SubscriptionRecord,
)
from metering_billing.netsuite_csv import get_invoices_csv_presigned_url
from metering_billing.payment_processors import PAYMENT_PROCESSOR_MAP
from metering_billing.permissions import HasUserAPIKey, ValidOrganization
from metering_billing.serializers.model_serializers import MetricDetailSerializer
from metering_billing.serializers.request_serializers import (
    CostAnalysisRequestSerializer,
    OptionalPeriodRequestSerializer,
    PeriodComparisonRequestSerializer,
    PeriodMetricUsageRequestSerializer,
    URLResponseSerializer,
)
from metering_billing.serializers.response_serializers import (
    CostAnalysisSerializer,
    PeriodEventsResponseSerializer,
    PeriodMetricRevenueResponseSerializer,
    PeriodMetricUsageResponseSerializer,
    PeriodSubscriptionsResponseSerializer,
)
from metering_billing.serializers.serializer_utils import OrganizationUUIDField
from metering_billing.tasks import import_customers_from_payment_processor
from metering_billing.utils import (
    convert_to_date,
    convert_to_datetime,
    convert_to_decimal,
    date_as_max_dt,
    date_as_min_dt,
    dates_bwn_two_dts,
    make_all_dates_times_strings,
    make_all_decimals_floats,
)
from metering_billing.utils.enums import METRIC_STATUS, METRIC_TYPE, PAYMENT_PROCESSORS
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


logger = logging.getLogger("django.server")
POSTHOG_PERSON = settings.POSTHOG_PERSON


class PeriodMetricRevenueView(APIView):
    permission_classes = [IsAuthenticated | ValidOrganization]

    @extend_schema(
        request=PeriodComparisonRequestSerializer,
        parameters=[PeriodComparisonRequestSerializer],
        responses={200: PeriodMetricRevenueResponseSerializer},
    )
    def get(self, request, format=None):
        """
        Returns the revenue for an organization in a given time period.
        """
        organization = request.organization
        timezone = organization.timezone
        serializer = PeriodComparisonRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        p1_start, p1_end, p2_start, p2_end = (
            serializer.validated_data.get(key, None)
            for key in [
                "period_1_start_date",
                "period_1_end_date",
                "period_2_start_date",
                "period_2_end_date",
            ]
        )
        p1_start, p2_start = date_as_min_dt(p1_start, timezone), date_as_min_dt(
            p2_start, timezone
        )
        p1_end, p2_end = date_as_max_dt(p1_end, timezone), date_as_max_dt(
            p2_end, timezone
        )
        return_dict = {}
        # collected
        p1_collected = Invoice.objects.filter(
            organization=organization,
            issue_date__gte=p1_start,
            issue_date__lte=p1_end,
            payment_status=Invoice.PaymentStatus.PAID,
        ).aggregate(tot=Sum("amount"))["tot"]
        p2_collected = Invoice.objects.filter(
            organization=organization,
            issue_date__gte=p2_start,
            issue_date__lte=p2_end,
            payment_status=Invoice.PaymentStatus.PAID,
        ).aggregate(tot=Sum("amount"))["tot"]
        return_dict["total_revenue_period_1"] = p1_collected or Decimal(0)
        return_dict["total_revenue_period_2"] = p2_collected or Decimal(0)
        # earned
        for start, end, num in [(p1_start, p1_end, 1), (p2_start, p2_end, 2)]:
            subs = (
                SubscriptionRecord.objects.filter(
                    Q(start_date__range=(start, end))
                    | Q(end_date__range=(start, end))
                    | Q(start_date__lte=start, end_date__gte=end),
                    organization=organization,
                )
                .select_related("billing_plan")
                .select_related("customer")
                .prefetch_related("billing_plan__recurring_charges")
                .prefetch_related("billing_plan__plan_components")
                .prefetch_related("billing_plan__plan_components__billable_metric")
                .prefetch_related("billing_plan__plan_components__tiers")
            )
            per_day_dict = {}
            for period in dates_bwn_two_dts(start, end):
                period = convert_to_date(period)
                per_day_dict[period] = {
                    "date": period,
                    "revenue": Decimal(0),
                }
            for subscription in subs:
                earned_revenue = subscription.calculate_earned_revenue_per_day()
                for date, earned_revenue in earned_revenue.items():
                    date = convert_to_date(date)
                    if date in per_day_dict:
                        per_day_dict[date]["revenue"] += earned_revenue
            return_dict[f"earned_revenue_period_{num}"] = sum(
                [x["revenue"] for x in per_day_dict.values()]
            )
        serializer = PeriodMetricRevenueResponseSerializer(data=return_dict)
        serializer.is_valid(raise_exception=True)
        ret = serializer.validated_data
        ret = make_all_decimals_floats(ret)
        ret = make_all_dates_times_strings(ret)
        return Response(ret, status=status.HTTP_200_OK)


class PeriodEventsView(APIView):
    permission_classes = [IsAuthenticated | ValidOrganization]

    @extend_schema(
        parameters=[PeriodComparisonRequestSerializer],
        responses={200: PeriodMetricRevenueResponseSerializer},
    )
    def get(self, request, format=None):
        """
        Returns the revenue for an organization in a given time period.
        """
        organization = request.organization
        timezone = organization.timezone
        serializer = PeriodComparisonRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        p1_start, p1_end, p2_start, p2_end = (
            serializer.validated_data.get(key, None)
            for key in [
                "period_1_start_date",
                "period_1_end_date",
                "period_2_start_date",
                "period_2_end_date",
            ]
        )
        p1_start, p2_start = date_as_min_dt(
            p1_start, timezone=timezone
        ), date_as_min_dt(p2_start, timezone=timezone)
        p1_end, p2_end = date_as_max_dt(p1_end, timezone=timezone), date_as_max_dt(
            p2_end, timezone=timezone
        )
        return_dict = {}
        # earned
        for start, end, num in [(p1_start, p1_end, 1), (p2_start, p2_end, 2)]:
            n_events = Event.objects.filter(
                organization=organization,
                time_created__gte=start,
                time_created__lte=end,
            ).count()
            return_dict[f"total_events_period_{num}"] = n_events
        serializer = PeriodEventsResponseSerializer(data=return_dict)
        serializer.is_valid(raise_exception=True)
        ret = serializer.validated_data
        return Response(ret, status=status.HTTP_200_OK)


class PeriodSubscriptionsView(APIView):
    permission_classes = [IsAuthenticated | ValidOrganization]

    @extend_schema(
        parameters=[PeriodComparisonRequestSerializer],
        responses={200: PeriodSubscriptionsResponseSerializer},
    )
    def get(self, request, format=None):
        organization = request.organization
        timezone = organization.timezone
        serializer = PeriodComparisonRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        p1_start, p1_end, p2_start, p2_end = (
            serializer.validated_data.get(key, None)
            for key in [
                "period_1_start_date",
                "period_1_end_date",
                "period_2_start_date",
                "period_2_end_date",
            ]
        )
        p1_start, p2_start = date_as_min_dt(
            p1_start, timezone=timezone
        ), date_as_min_dt(p2_start, timezone=timezone)
        p1_end, p2_end = date_as_max_dt(p1_end, timezone=timezone), date_as_max_dt(
            p2_end, timezone=timezone
        )

        return_dict = {}
        for i, (p_start, p_end) in enumerate([[p1_start, p1_end], [p2_start, p2_end]]):
            p_subs = (
                SubscriptionRecord.objects.filter(
                    Q(start_date__range=[p_start, p_end])
                    | Q(end_date__range=[p_start, p_end]),
                    organization=organization,
                )
                .select_related("customer")
                .values(customer_name=F("customer__customer_name"), new=F("is_new"))
            )
            seen_dict = {}
            for sub in p_subs:
                if (
                    sub["customer_name"] in seen_dict
                ):  # seen before then they're def not new
                    seen_dict[sub["customer_name"]] = False
                else:
                    seen_dict[sub["customer_name"]] = sub["new"]
            return_dict[f"period_{i+1}_total_subscriptions"] = len(seen_dict)
            return_dict[f"period_{i+1}_new_subscriptions"] = sum(
                [1 for k, v in seen_dict.items() if v]
            )
        serializer = PeriodSubscriptionsResponseSerializer(data=return_dict)
        serializer.is_valid(raise_exception=True)
        ret = serializer.validated_data
        ret = make_all_decimals_floats(ret)
        return Response(ret, status=status.HTTP_200_OK)


class PeriodMetricUsageView(APIView):
    permission_classes = [IsAuthenticated | ValidOrganization]

    @extend_schema(
        request=PeriodMetricUsageRequestSerializer,
        parameters=[PeriodMetricUsageRequestSerializer],
        responses={200: PeriodMetricUsageResponseSerializer},
    )
    def get(self, request, format=None):
        """
        Return current usage for a customer during a given billing period.
        """
        organization = request.organization
        serializer = PeriodMetricUsageRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        q_start, q_end, top_n = (
            serializer.validated_data.get(key, None)
            for key in ["start_date", "end_date", "top_n_customers"]
        )
        q_start = convert_to_datetime(q_start, date_behavior="min")
        q_end = convert_to_datetime(q_end, date_behavior="max")
        final_results = {}
        metrics = organization.metrics.filter(
            ~Q(metric_type=METRIC_TYPE.CUSTOM), status=METRIC_STATUS.ACTIVE
        )
        for metric in metrics:
            metric_dict = {}
            per_customer_usage = metric.get_daily_total_usage(
                start_date=q_start, end_date=q_end, customer=None, top_n=top_n
            )
            for customer, customer_dict in per_customer_usage.items():
                for date, usage in customer_dict.items():
                    if date not in metric_dict:
                        metric_dict[date] = {}
                    cust = customer if customer == "Other" else customer.customer_name
                    metric_dict[date][cust] = convert_to_decimal(usage)
            final_results[metric.billable_metric_name] = {
                "data": sorted(
                    [{"date": k, "customer_usages": v} for k, v in metric_dict.items()],
                    key=lambda x: x["date"],
                )
            }
        serializer = PeriodMetricUsageResponseSerializer(
            data={"metrics": final_results}
        )
        serializer.is_valid(raise_exception=True)
        ret = serializer.validated_data
        ret = make_all_decimals_floats(ret)
        ret = make_all_dates_times_strings(ret)
        return Response(ret, status=status.HTTP_200_OK)


class SettingsView(APIView):
    permission_classes = [IsAuthenticated | ValidOrganization]

    def get(self, request, format=None):
        """
        Get the current settings for the organization.
        """
        organization = request.organization
        return Response(
            {"organization": organization.organization_name}, status=status.HTTP_200_OK
        )


class ChangeUserOrganizationView(APIView):
    permission_classes = [IsAuthenticated | ValidOrganization]

    @extend_schema(
        request=inline_serializer(
            name="ChangeUserOrganizationRequestSerializer",
            fields={
                "transfer_to_organization_id": serializers.CharField(
                    help_text="The organization ID to transfer to"
                )
            },
        ),
        responses={
            200: inline_serializer(
                name="ChangeUserOrganizationResponseSerializer", fields={}
            )
        },
    )
    def post(self, request, format=None):
        """
        Get the current settings for the organization.
        """
        user = request.user
        new_organization_id = request.data.get("transfer_to_organization_id")
        if not new_organization_id:
            raise ValidationError("No organization ID provided")
        org_uuid = OrganizationUUIDField().to_internal_value(new_organization_id)
        new_organization = Organization.objects.filter(organization_id=org_uuid).first()
        if not new_organization:
            raise ValidationError("Organization not found")
        user.organization = new_organization
        user.save()
        return Response(status=status.HTTP_200_OK)


class TimezonesView(APIView):
    permission_classes = [IsAuthenticated | HasUserAPIKey]

    @extend_schema(
        request=None,
        parameters=None,
        responses={
            200: inline_serializer(
                name="TimezonesResponseSerializer",
                fields={
                    "timezones": serializers.ListField(child=serializers.CharField())
                },
            )
        },
    )
    def get(self, request, format=None):
        """
        Pagination-enabled endpoint for retrieving an organization's event stream.
        """
        response = {"timezones": pytz.common_timezones}
        return Response(response, status=status.HTTP_200_OK)


class ImportCustomersView(APIView):
    permission_classes = [IsAuthenticated | ValidOrganization]

    @extend_schema(
        request=inline_serializer(
            name="ImportCustomersRequest",
            fields={
                "source": serializers.ChoiceField(choices=PAYMENT_PROCESSORS.choices)
            },
        ),
        responses={
            200: inline_serializer(
                name="ImportCustomerSuccess",
                fields={
                    "status": serializers.ChoiceField(choices=["success"]),
                    "detail": serializers.CharField(),
                },
            ),
            400: inline_serializer(
                name="ImportCustomerFailure",
                fields={
                    "status": serializers.ChoiceField(choices=["error"]),
                    "detail": serializers.CharField(),
                },
            ),
        },
    )
    def post(self, request, format=None):
        organization = request.organization
        source = request.data["source"]
        if source not in [choice[0] for choice in PAYMENT_PROCESSORS.choices]:
            raise ExternalConnectionInvalid(f"Invalid source: {source}")

        try:
            import_customers_from_payment_processor.delay(source, organization.id)
        except Exception as e:
            raise ExternalConnectionFailure(f"Error importing customers: {e}")
        return Response(
            {
                "status": "success",
                "detail": f"Started customer transfer from {source}.",
            },
            status=status.HTTP_201_CREATED,
        )


class ImportPaymentObjectsView(APIView):
    permission_classes = [IsAuthenticated | ValidOrganization]

    @extend_schema(
        request=inline_serializer(
            name="ImportPaymentObjectsRequest",
            fields={
                "source": serializers.ChoiceField(choices=PAYMENT_PROCESSORS.choices)
            },
        ),
        responses={
            200: inline_serializer(
                name="ImportPaymentObjectSuccess",
                fields={
                    "status": serializers.ChoiceField(choices=["success"]),
                    "detail": serializers.CharField(),
                },
            ),
            400: inline_serializer(
                name="ImportPaymentObjectFailure",
                fields={
                    "status": serializers.ChoiceField(choices=["error"]),
                    "detail": serializers.CharField(),
                },
            ),
        },
    )
    def post(self, request, format=None):
        organization = request.organization
        source = request.data["source"]
        if source not in [choice[0] for choice in PAYMENT_PROCESSORS.choices]:
            raise ExternalConnectionInvalid(f"Invalid source: {source}")
        connector = PAYMENT_PROCESSOR_MAP[source]
        try:
            num = connector.import_payment_objects(organization)
        except Exception as e:
            raise ExternalConnectionFailure(f"Error importing payment objects: {e}")
        num = sum([len(v) for v in num.values()])
        return Response(
            {
                "status": "success",
                "detail": f"Payment objects succesfully imported {num} payment objects from {source}.",
            },
            status=status.HTTP_201_CREATED,
        )


class TransferSubscriptionsView(APIView):
    permission_classes = [IsAuthenticated | ValidOrganization]

    @extend_schema(
        request=inline_serializer(
            name="TransferSubscriptionsRequest",
            fields={
                "source": serializers.ChoiceField(choices=PAYMENT_PROCESSORS.choices),
                "end_now": serializers.BooleanField(),
            },
        ),
        responses={
            200: inline_serializer(
                name="TransferSubscriptionsSuccess",
                fields={
                    "status": serializers.ChoiceField(choices=["success"]),
                    "detail": serializers.CharField(),
                },
            ),
            400: inline_serializer(
                name="TransferSubscriptionsFailure",
                fields={
                    "status": serializers.ChoiceField(choices=["error"]),
                    "detail": serializers.CharField(),
                },
            ),
        },
    )
    def post(self, request, format=None):
        organization = request.organization
        source = request.data["source"]
        if source not in [choice[0] for choice in PAYMENT_PROCESSORS.choices]:
            raise ExternalConnectionInvalid(f"Invalid source: {source}")
        end_now = request.data.get("end_now", False)
        connector = PAYMENT_PROCESSOR_MAP[source]
        try:
            num = connector.transfer_subscriptions(organization, end_now)
        except Exception as e:
            raise ExternalConnectionFailure(f"Error transferring susbcriptions: {e}")
        return Response(
            {
                "status": "success",
                "detail": f"Succesfully transferred {num} subscriptions from {source}.",
            },
            status=status.HTTP_201_CREATED,
        )


class PlansByNumCustomersView(APIView):
    permission_classes = [IsAuthenticated | ValidOrganization]

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
        organization = request.organization
        plans = (
            SubscriptionRecord.objects.active()
            .filter(
                organization=organization,
            )
            .values(plan_name=F("billing_plan__plan__plan_name"))
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


class NetsuiteInvoiceCSVView(APIView):
    permission_classes = [IsAuthenticated | ValidOrganization]

    @extend_schema(
        request=OptionalPeriodRequestSerializer,
        responses=URLResponseSerializer,
    )
    def get(self, request, format=None):
        organization = request.organization
        serializer = OptionalPeriodRequestSerializer(
            data=request.query_params, context={"organization": organization}
        )
        serializer.is_valid(raise_exception=True)
        start_date = serializer.validated_data.get("start_date")
        end_date = serializer.validated_data.get("end_date")
        ret = get_invoices_csv_presigned_url(organization, start_date, end_date)
        return Response(
            URLResponseSerializer(ret).data,
            status=status.HTTP_200_OK,
        )


class NetsuiteCustomerCSVView(APIView):
    permission_classes = [IsAuthenticated | ValidOrganization]

    @extend_schema(
        request=OptionalPeriodRequestSerializer,
        responses=URLResponseSerializer,
    )
    def get(self, request, format=None):
        organization = request.organization
        serializer = OptionalPeriodRequestSerializer(
            data=request.query_params, context={"organization": organization}
        )
        serializer.is_valid(raise_exception=True)
        # start_date = serializer.validated_data.get("start_date")
        # end_date = serializer.validated_data.get("end_date")
        # ret = get_customers_csv_presigned_url(organization, start_date, end_date)
        # data = URLResponseSerializer(ret).data
        return Response(
            {},
            status=status.HTTP_200_OK,
        )
