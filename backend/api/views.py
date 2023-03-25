# Create your views here.
import base64
import copy
import json
import logging
import operator
import re
import uuid
from decimal import Decimal
from functools import reduce
from itertools import chain
from typing import Optional

import posthog
import pytz
from dateutil import parser
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db.models import (
    Count,
    DecimalField,
    F,
    Max,
    Min,
    OuterRef,
    Prefetch,
    Q,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce
from django.db.utils import IntegrityError
from django.http import HttpRequest, HttpResponseBadRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    extend_schema,
    inline_serializer,
)
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import (
    action,
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers.model_serializers import (
    AddOnSubscriptionRecordCreateSerializer,
    AddOnSubscriptionRecordSerializer,
    AddOnSubscriptionRecordUpdateSerializer,
    CustomerBalanceAdjustmentCreateSerializer,
    CustomerBalanceAdjustmentFilterSerializer,
    CustomerBalanceAdjustmentSerializer,
    CustomerBalanceAdjustmentUpdateSerializer,
    CustomerCreateSerializer,
    CustomerSerializer,
    EventSerializer,
    InvoiceListFilterSerializer,
    InvoicePaymentSerializer,
    InvoiceSerializer,
    InvoiceUpdateSerializer,
    ListPlansFilterSerializer,
    ListPlanVersionsFilterSerializer,
    ListSubscriptionRecordFilter,
    PlanSerializer,
    SubscriptionFilterSerializer,
    SubscriptionRecordCancelSerializer,
    SubscriptionRecordCreateSerializer,
    SubscriptionRecordCreateSerializerOld,
    SubscriptionRecordFilterSerializer,
    SubscriptionRecordFilterSerializerDelete,
    SubscriptionRecordSerializer,
    SubscriptionRecordSwitchPlanSerializer,
    SubscriptionRecordUpdateSerializer,
    SubscriptionRecordUpdateSerializerOld,
)
from api.serializers.nonmodel_serializers import (
    ChangePrepaidUnitsSerializer,
    CustomerDeleteResponseSerializer,
    FeatureAccessRequestSerializer,
    FeatureAccessResponseSerializer,
    MetricAccessRequestSerializer,
    MetricAccessResponseSerializer,
)
from metering_billing.auth.auth_utils import (
    PermissionPolicyMixin,
    fast_api_key_validation_and_cache,
)
from metering_billing.exceptions import (
    DuplicateCustomer,
    ServerError,
    SwitchPlanDurationMismatch,
    SwitchPlanSamePlanException,
)
from metering_billing.exceptions.exceptions import InvalidOperation, NotFoundException
from metering_billing.invoice import generate_invoice
from metering_billing.invoice_pdf import get_invoice_presigned_url
from metering_billing.kafka.producer import Producer
from metering_billing.models import (
    ComponentChargeRecord,
    Customer,
    CustomerBalanceAdjustment,
    Event,
    Invoice,
    InvoiceLineItem,
    Metric,
    Plan,
    PlanComponent,
    PriceTier,
    RecurringCharge,
    SubscriptionRecord,
    Tag,
)
from metering_billing.permissions import HasUserAPIKey, ValidOrganization
from metering_billing.serializers.model_serializers import (
    DraftInvoiceSerializer,
    MetricDetailSerializer,
)
from metering_billing.serializers.request_serializers import (
    DraftInvoiceRequestSerializer,
    PeriodRequestSerializer,
)
from metering_billing.serializers.response_serializers import CostAnalysisSerializer
from metering_billing.serializers.serializer_utils import (
    AddOnUUIDField,
    AddOnVersionUUIDField,
    BalanceAdjustmentUUIDField,
    InvoiceUUIDField,
    MetricUUIDField,
    OrganizationUUIDField,
    PlanUUIDField,
    SlugRelatedFieldWithOrganizationPK,
    SubscriptionUUIDField,
)
from metering_billing.utils import (
    calculate_end_date,
    convert_to_date,
    convert_to_datetime,
    convert_to_decimal,
    dates_bwn_two_dts,
    make_all_dates_times_strings,
    make_all_decimals_floats,
    now_utc,
)
from metering_billing.utils.enums import (
    CUSTOMER_BALANCE_ADJUSTMENT_STATUS,
    INVOICING_BEHAVIOR,
    METRIC_STATUS,
    PLAN_CUSTOM_TYPE,
    SUBSCRIPTION_STATUS,
    USAGE_BEHAVIOR,
    USAGE_BILLING_BEHAVIOR,
)
from metering_billing.webhooks import (
    customer_created_webhook,
    subscription_cancelled_webhook,
    subscription_created_webhook,
)

POSTHOG_PERSON = settings.POSTHOG_PERSON
SVIX_CONNECTOR = settings.SVIX_CONNECTOR
IDEMPOTENCY_ID_NAMESPACE = settings.IDEMPOTENCY_ID_NAMESPACE
logger = logging.getLogger("django.server")
USE_KAFKA = settings.USE_KAFKA
if USE_KAFKA:
    kafka_producer = Producer()
else:
    kafka_producer = None

logger = logging.getLogger("django.server")


class EmptySerializer(serializers.Serializer):
    pass


class CustomerViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    lookup_field = "customer_id"
    http_method_names = ["get", "post", "head"]
    queryset = Customer.objects.all()

    def get_queryset(self):
        now = now_utc()
        organization = self.request.organization
        qs = Customer.objects.filter(organization=organization)
        qs = qs.select_related("default_currency")
        qs = qs.prefetch_related(
            "organization",
            Prefetch(
                "subscription_records",
                queryset=SubscriptionRecord.base_objects.active(now)
                .filter(
                    organization=organization,
                )
                .select_related("customer", "billing_plan", "billing_plan__plan")
                .prefetch_related(
                    "addon_subscription_records",
                    "organization",
                ),
                to_attr="active_subscription_records",
            ),
            Prefetch(
                "invoices",
                queryset=Invoice.objects.filter(
                    organization=organization,
                    payment_status__in=[
                        Invoice.PaymentStatus.PAID,
                        Invoice.PaymentStatus.UNPAID,
                    ],
                )
                .order_by("-issue_date")
                .select_related("currency")
                .prefetch_related(
                    "organization",
                    Prefetch(
                        "line_items",
                        queryset=InvoiceLineItem.objects.all()
                        .select_related(
                            "pricing_unit",
                            "associated_subscription_record",
                            "associated_plan_version",
                            "associated_billing_record",
                        )
                        .prefetch_related("organization"),
                    ),
                )
                .annotate(
                    min_date=Min("line_items__start_date"),
                    max_date=Max("line_items__end_date"),
                ),
                to_attr="active_invoices",
            ),
        )
        qs = qs.annotate(
            total_amount_due=Sum(
                "invoices__amount",
                filter=Q(invoices__payment_status=Invoice.PaymentStatus.UNPAID),
                output_field=DecimalField(),
            )
        )
        return qs

    def get_serializer_class(self, default=None):
        if self.action == "create":
            return CustomerCreateSerializer
        elif self.action == "archive":
            return EmptySerializer
        elif self.action == "cost_analysis":
            return PeriodRequestSerializer
        if default:
            return default
        return CustomerSerializer

    @extend_schema(responses=CustomerSerializer)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)

        # return serializer
        self.action = "retrieve"
        customer_data = self.get_serializer(instance).data
        customer_created_webhook(instance, customer_data=customer_data)
        return Response(customer_data, status=status.HTTP_201_CREATED)

    @extend_schema(
        responses=CustomerDeleteResponseSerializer,
    )
    @action(detail=True, methods=["post"], url_path="delete", url_name="delete")
    def archive(self, request, customer_id=None):
        customer = self.get_object()

        now = now_utc()

        return_data = {
            "customer_id": customer.customer_id,
            "email": customer.email,
            "deleted": now,
        }
        customer.deleted = now
        customer.save()
        subscription_records = customer.subscription_records.active().all()
        n_subs = subscription_records.filter(
            billing_plan__addon_spec__isnull=True
        ).count()
        return_data["num_subscriptions_deleted"] = n_subs
        n_addons = subscription_records.filter(
            billing_plan__addon_spec__isnull=False
        ).count()
        return_data["num_addons_deleted"] = n_addons
        for subscription_record in subscription_records:
            subscription_record.delete_subscription(delete_time=now)
        versions = customer.plan_versions.all()
        for version in versions:
            version.target_customers.remove(customer)
        CustomerDeleteResponseSerializer().validate(return_data)
        return Response(return_data, status=status.HTTP_200_OK)

    @extend_schema(
        request=DraftInvoiceRequestSerializer,
        parameters=[DraftInvoiceRequestSerializer],
        responses={
            200: inline_serializer(
                name="DraftInvoiceResponse", fields={"invoice": DraftInvoiceSerializer}
            )
        },
    )
    @action(
        detail=True, methods=["get"], url_path="draft_invoice", url_name="draft_invoice"
    )
    def draft_invoice(self, request, customer_id=None):
        customer = self.get_object()
        organization = request.organization
        serializer = DraftInvoiceRequestSerializer(
            data=request.query_params, context={"organization": organization}
        )
        serializer.is_valid(raise_exception=True)
        sub_records = SubscriptionRecord.objects.active().filter(
            organization=organization, customer=customer
        )
        response = {"invoices": None}
        if sub_records is None or len(sub_records) == 0:
            response = {"invoices": []}
        else:
            sub_records = sub_records.select_related("billing_plan").prefetch_related(
                "billing_plan__plan_components",
                "billing_plan__plan_components__billable_metric",
                "billing_plan__plan_components__tiers",
                "billing_plan__currency",
            )
            invoices = generate_invoice(
                sub_records,
                draft=True,
                charge_next_plan=serializer.validated_data.get(
                    "include_next_period", True
                ),
            )
            serializer = DraftInvoiceSerializer(invoices, many=True).data
            for invoice in invoices:
                invoice.delete()
            response = {"invoices": serializer or []}
        return Response(response, status=status.HTTP_200_OK)

    @extend_schema(
        request=None,
        parameters=[PeriodRequestSerializer],
        responses={200: CostAnalysisSerializer},
    )
    @action(
        detail=True, methods=["get"], url_path="cost_analysis", url_name="cost_analysis"
    )
    def cost_analysis(self, request, customer_id=None):
        organization = request.organization
        serializer = self.get_serializer(
            data=request.query_params,
        )
        serializer.is_valid(raise_exception=True)
        customer = self.get_object()
        start_date, end_date = (
            serializer.validated_data.get(key, None)
            for key in ["start_date", "end_date"]
        )
        start_time = convert_to_datetime(start_date, date_behavior="min")
        end_time = convert_to_datetime(end_date, date_behavior="max")
        per_day_dict = {}
        for period in dates_bwn_two_dts(start_date, end_date):
            period = convert_to_date(period)
            per_day_dict[period] = {
                "date": period,
                "cost_data": {},
                "revenue": Decimal(0),
            }
        cost_metrics = Metric.objects.filter(
            organization=organization, is_cost_metric=True, status=METRIC_STATUS.ACTIVE
        )
        for metric in cost_metrics:
            usage_ret = metric.get_daily_total_usage(
                start_date,
                end_date,
                customer=customer,
            ).get(customer, {})
            for date, usage in usage_ret.items():
                date = convert_to_date(date)
                usage = convert_to_decimal(usage)
                if date in per_day_dict:
                    if (
                        metric.billable_metric_name
                        not in per_day_dict[date]["cost_data"]
                    ):
                        per_day_dict[date]["cost_data"][metric.billable_metric_name] = {
                            "metric": MetricDetailSerializer(metric).data,
                            "cost": Decimal(0),
                        }
                    per_day_dict[date]["cost_data"][metric.billable_metric_name][
                        "cost"
                    ] += usage
        for date, items in per_day_dict.items():
            items["cost_data"] = [v for k, v in items["cost_data"].items()]
        subscriptions = (
            SubscriptionRecord.objects.filter(
                Q(start_date__range=[start_time, end_time])
                | Q(end_date__range=[start_time, end_time])
                | (Q(start_date__lte=start_time) & Q(end_date__gte=end_time)),
                organization=organization,
                customer=customer,
            )
            .select_related("billing_plan")
            .select_related("customer")
            .prefetch_related("billing_plan__recurring_charges")
            .prefetch_related("billing_plan__plan_components")
            .prefetch_related("billing_plan__plan_components__billable_metric")
            .prefetch_related("billing_plan__plan_components__tiers")
            .prefetch_related("billing_records")
            .prefetch_related("billing_records__component")
            .prefetch_related("billing_records__recurring_charge")
            .prefetch_related("billing_records__component__billable_metric")
            .prefetch_related("billing_records__component__tiers")
        )
        for subscription in subscriptions:
            earned_revenue = subscription.calculate_earned_revenue_per_day()
            for date, earned_revenue in earned_revenue.items():
                date = convert_to_date(date)
                if date in per_day_dict:
                    per_day_dict[date]["revenue"] += earned_revenue
        return_dict = {
            "per_day": [v for k, v in per_day_dict.items()],
        }
        total_cost = Decimal(0)
        for day in per_day_dict.values():
            for cost_data in day["cost_data"]:
                total_cost += convert_to_decimal(cost_data["cost"])
        total_revenue = Decimal(0)
        for day in per_day_dict.values():
            total_revenue += day["revenue"]
        return_dict["total_cost"] = total_cost
        return_dict["total_revenue"] = total_revenue
        if total_revenue == 0:
            return_dict["profit_margin"] = 0
        else:
            return_dict["profit_margin"] = convert_to_decimal(
                (total_revenue - total_cost) / total_revenue
            )
        if total_cost == 0:
            return_dict["markup"] = 0
        else:
            return_dict["markup"] = convert_to_decimal(
                (total_revenue - total_cost) / total_cost
            )
        serializer = CostAnalysisSerializer(data=return_dict)
        serializer.is_valid(raise_exception=True)
        ret = serializer.validated_data
        ret = make_all_decimals_floats(ret)
        ret = make_all_dates_times_strings(ret)
        return Response(ret, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        try:
            return serializer.save(organization=self.request.organization)
        except IntegrityError as e:
            cause = e.__cause__
            if "unique_email" in str(cause):
                raise DuplicateCustomer("Customer email already exists")
            elif "unique_customer_id" in str(cause):
                raise DuplicateCustomer("Customer ID already exists")
            raise ServerError("Unknown error: " + str(cause))

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"organization": self.request.organization})
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except Exception:
                username = None
            organization = self.request.organization or self.request.user.organization
            try:
                posthog.capture(
                    POSTHOG_PERSON
                    if POSTHOG_PERSON
                    else (
                        username
                        if username
                        else organization.organization_name + " (API Key)"
                    ),
                    event=f"{self.action}_customer",
                    properties={"organization": organization.organization_name},
                )
            except Exception:
                pass
        return response


class PlanViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    serializer_class = PlanSerializer
    lookup_field = "plan_id"
    http_method_names = ["get", "head"]
    queryset = Plan.plans.all().order_by(
        F("created_on").desc(nulls_last=False), F("plan_name")
    )

    def get_object(self):
        string_uuid = str(self.kwargs[self.lookup_field])
        if "plan_" in string_uuid:
            uuid = PlanUUIDField().to_internal_value(string_uuid)
        else:
            uuid = AddOnUUIDField().to_internal_value(string_uuid)
        self.kwargs[self.lookup_field] = uuid
        return super().get_object()

    def get_queryset(self):
        from metering_billing.models import PlanVersion

        now = now_utc()
        organization = self.request.organization
        # first filter plans
        plan_filter_serializer = ListPlansFilterSerializer(
            data=self.request.query_params
        )
        plan_filter_serializer.is_valid(raise_exception=True)

        plans_filters = []

        include_tags = plan_filter_serializer.validated_data.get("include_tags")
        include_tags_all = plan_filter_serializer.validated_data.get("include_tags_all")
        exclude_tags = plan_filter_serializer.validated_data.get("exclude_tags")
        duration = plan_filter_serializer.validated_data.get("duration")

        if duration:
            plans_filters.append(Q(duration=duration))

        # then filter plan versions
        versions_filters = []

        plan_version_filter_serializer = ListPlanVersionsFilterSerializer(
            data=self.request.query_params
        )
        plan_version_filter_serializer.is_valid(raise_exception=True)
        validated_data = plan_version_filter_serializer.validated_data
        version_currency = validated_data.get("version_currency")
        version_status = validated_data.get("version_status")
        version_custom_type = validated_data.get("version_custom_type")
        status_combo = []
        if SUBSCRIPTION_STATUS.ACTIVE in version_status:
            status_combo.append(
                (
                    Q(active_from__lte=now)
                    & (Q(active_to__gte=now) | Q(active_to__isnull=True))
                )
            )
        if SUBSCRIPTION_STATUS.ENDED in version_status:
            status_combo.append(Q(active_to__lt=now))
        if SUBSCRIPTION_STATUS.NOT_STARTED in version_status:
            status_combo.append((Q(active_from__gt=now) | Q(active_from__isnull=True)))
        if status_combo:
            combined_filter = reduce(operator.or_, status_combo)
            versions_filters.append(combined_filter)
        if version_currency:
            versions_filters.append(Q(currency=version_currency))
        if version_custom_type == PLAN_CUSTOM_TYPE.PUBLIC_ONLY:
            versions_filters.append(Q(is_custom=False))
        elif version_custom_type == PLAN_CUSTOM_TYPE.CUSTOM_ONLY:
            versions_filters.append(Q(is_custom=True))

        qs = (
            Plan.plans.all()
            .order_by(F("created_on").desc(nulls_last=False), F("plan_name"))
            .filter(*plans_filters, organization=organization)
        )
        # first go for the ones that are one away (FK) and not nested
        qs = qs.select_related(
            "organization",
            "created_by",
        )
        # then for many to many / reverse FK but still have
        qs = qs.prefetch_related(
            "external_links",
            Prefetch("tags", queryset=Tag.objects.filter(organization=organization)),
        )
        # then come the really deep boys
        # we need to construct the prefetch objects so that we are prefetching the more
        # deeply nested objectsd as part of the call:
        # https://forum.djangoproject.com/t/drf-and-nested-serialisers-optimisation-with-prefect-related/4272
        qs = qs.prefetch_related(
            Prefetch(
                "versions",
                queryset=PlanVersion.plan_versions.filter(
                    *versions_filters,
                    organization=organization,
                )
                .annotate(
                    active_subscriptions=Coalesce(
                        Subquery(
                            SubscriptionRecord.objects.filter(
                                billing_plan=OuterRef("pk"),
                                start_date__lte=now,
                                end_date__gte=now,
                            )
                            .values("billing_plan")
                            .annotate(active_subscriptions=Count("id"))
                            .values("active_subscriptions")[:1]
                        ),
                        Value(0),
                    )
                )
                .select_related("price_adjustment", "created_by", "currency")
                .prefetch_related("usage_alerts", "features", "target_customers")
                .prefetch_related(
                    Prefetch(
                        "plan_components",
                        queryset=PlanComponent.objects.filter(
                            organization=organization,
                        )
                        .select_related("pricing_unit")
                        .prefetch_related(
                            Prefetch(
                                "tiers",
                                queryset=PriceTier.objects.filter(
                                    organization=organization
                                ),
                            ),
                            Prefetch(
                                "billable_metric",
                                queryset=Metric.objects.filter(
                                    organization=organization,
                                    status=METRIC_STATUS.ACTIVE,
                                ).prefetch_related(
                                    "numeric_filters",
                                    "categorical_filters",
                                ),
                            ),
                        ),
                    ),
                    Prefetch(
                        "recurring_charges",
                        queryset=RecurringCharge.objects.filter(
                            organization=organization,
                        ).select_related("pricing_unit", "organization"),
                        to_attr="recurring_charges_prefetched",
                    ),
                )
                .order_by("created_on"),
                to_attr="versions_prefetched",
            ),
        )

        if include_tags:
            # Filter to plans that have any of the tags in this list
            q_objects = Q()
            for tag in include_tags:
                q_objects |= Q(tags__tag_name__iexact=tag)
            qs = qs.filter(q_objects)

        if include_tags_all:
            # Filter to plans that have all of the tags in this list
            q_objects = Q()
            for tag in include_tags_all:
                q_objects &= Q(tags__tag_name__iexact=tag)
            qs = qs.filter(q_objects)

        if exclude_tags:
            # Filter to plans that do not have any of the tags in this list
            q_objects = Q()
            for tag in exclude_tags:
                q_objects &= ~Q(tags__tag_name__iexact=tag)
            qs = qs.filter(q_objects)

        return qs

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except Exception:
                username = None
            organization = self.request.organization
            try:
                posthog.capture(
                    POSTHOG_PERSON
                    if POSTHOG_PERSON
                    else (
                        username
                        if username
                        else organization.organization_name + " (API Key)"
                    ),
                    event=f"{self.action}_plan",
                    properties={"organization": organization.organization_name},
                )
            except Exception:
                pass
        return response

    def get_serializer_context(self):
        context = super().get_serializer_context()
        organization = self.request.organization
        if self.request.user.is_authenticated:
            user = self.request.user
        else:
            user = None
        context.update({"organization": organization, "user": user})
        return context

    @extend_schema(
        parameters=[ListPlansFilterSerializer, ListPlanVersionsFilterSerializer],
    )
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        ret = []
        for plan in data:
            if len(plan["versions"]) > 0:
                ret.append(plan)
        return Response(ret)

    @extend_schema(
        parameters=[ListPlanVersionsFilterSerializer],
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


class SubscriptionViewSet(
    PermissionPolicyMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    http_method_names = [
        "get",
        "head",
        "post",
    ]
    queryset = SubscriptionRecord.base_objects.all()
    lookup_field = "subscription_id"

    def get_object(self):
        subscription_id = self.kwargs.get("subscription_id")
        subscription_uuid = SubscriptionUUIDField().to_internal_value(subscription_id)
        addon_id = self.kwargs.get("addon_id")
        if addon_id:
            try:
                addon_uuid = AddOnUUIDField().to_internal_value(addon_id)
            except Exception as e:
                try:
                    addon_uuid = AddOnVersionUUIDField().to_internal_value(addon_id)
                except Exception:
                    raise e
        else:
            addon_uuid = None
        if not subscription_uuid:
            raise ServerError(
                "Unexpected state. Could not find subscription_id in request."
            )
        try:
            obj = self.queryset.get(subscription_record_id=subscription_uuid)
        except SubscriptionRecord.DoesNotExist:
            raise NotFoundException(
                f"Subscription with subscription_id {subscription_id} not found"
            )
        if addon_uuid:
            addons_for_sr = obj.addon_subscription_records.filter(
                billing_plan__version_id=addon_uuid
            )
            if not addons_for_sr.exists():
                addons_for_sr = obj.addon_subscription_records.filter(
                    billing_plan__plan__plan_id=addon_uuid
                )
            if not addons_for_sr.exists():
                raise NotFoundException(
                    f"Addon with addon_id {addon_uuid} not found for subscription {subscription_id}"
                )
            elif addons_for_sr.count() > 1:
                raise ServerError(
                    f"Unexpected state. More than one addon found for subscription {subscription_id} and addon_id {addon_uuid}"
                )
            obj = addons_for_sr.first()
        return obj

    def get_serializer_context(self):
        context = super().get_serializer_context()
        organization = self.request.organization
        context.update({"organization": organization})
        return context

    def get_serializer_class(self):
        if self.action == "edit":
            return SubscriptionRecordUpdateSerializerOld
        elif self.action == "update_subscription":
            return SubscriptionRecordUpdateSerializer
        elif self.action == "switch_plan":
            return SubscriptionRecordSwitchPlanSerializer
        elif (
            self.action == "cancel_multi"
            or self.action == "cancel_addon"
            or self.action == "cancel"
        ):
            return SubscriptionRecordCancelSerializer
        elif self.action == "add":
            return SubscriptionRecordCreateSerializerOld
        elif self.action == "create":
            return SubscriptionRecordCreateSerializer
        elif self.action == "attach_addon":
            return AddOnSubscriptionRecordCreateSerializer
        elif self.action == "update_addon":
            return AddOnSubscriptionRecordUpdateSerializer
        elif self.action == "change_prepaid_units":
            return ChangePrepaidUnitsSerializer
        else:
            return SubscriptionRecordSerializer

    def _prefetch_qs(self, qs):
        qs = qs.select_related("billing_plan")
        qs = qs.prefetch_related(
            Prefetch(
                "billing_plan__plan_components",
                queryset=PlanComponent.objects.all(),
            ),
            Prefetch(
                "billing_plan__plan_components__billable_metric",
                queryset=Metric.objects.all(),
            ),
            Prefetch(
                "billing_plan__plan_components__tiers",
                queryset=PriceTier.objects.all(),
            ),
            Prefetch(
                "addon_subscription_records",
                queryset=SubscriptionRecord.addon_objects.select_related(
                    "billing_plan"
                ).prefetch_related(
                    Prefetch(
                        "billing_plan__plan_components",
                        queryset=PlanComponent.objects.all(),
                    ),
                    Prefetch(
                        "billing_plan__plan_components__tiers",
                        queryset=PriceTier.objects.all(),
                    ),
                ),
            ),
        )
        return qs

    def get_queryset(self):
        qs = SubscriptionRecord.base_objects.all()
        now = now_utc()
        organization = self.request.organization
        qs = qs.filter(organization=organization)
        context = self.get_serializer_context()
        context["organization"] = organization
        if self.action in ["list", "edit", "cancel_multi"]:
            subscription_filters = self.request.query_params.getlist(
                "subscription_filters[]"
            )
            subscription_filters = [json.loads(x) for x in subscription_filters]
            dict_params = self.request.query_params.dict()
            data = {
                "subscription_filters": subscription_filters,
                "customer_id": dict_params.get("customer_id"),
            }
            if dict_params.get("plan_id"):
                data["plan_id"] = dict_params.get("plan_id")
            if self.action == "edit":
                serializer = SubscriptionRecordFilterSerializer(
                    data=data, context=context
                )
            elif self.action == "cancel_multi":
                serializer = SubscriptionRecordFilterSerializerDelete(
                    data=data, context=context
                )
            elif self.action == "list":
                serializer = ListSubscriptionRecordFilter(
                    data=self.request.query_params, context=context
                )
            else:
                raise Exception("Invalid action")
            serializer.is_valid(raise_exception=True)
            # unpack whats in the serialized data

            customer = serializer.validated_data.get("customer")
            subscription_filters = serializer.validated_data.get("subscription_filters")
            allowed_status = serializer.validated_data.get(
                "status", [SUBSCRIPTION_STATUS.ACTIVE]
            )
            range_start = serializer.validated_data.get("range_start")
            range_end = serializer.validated_data.get("range_end")
            plan = serializer.validated_data.get("plan")
            # add onto args
            args = []
            if customer:
                args.append(Q(customer=customer))
            if allowed_status:
                status_combo = []
                if SUBSCRIPTION_STATUS.ACTIVE in allowed_status:
                    status_combo.append(Q(start_date__lte=now, end_date__gte=now))
                if SUBSCRIPTION_STATUS.ENDED in allowed_status:
                    status_combo.append(Q(end_date__lt=now))
                if SUBSCRIPTION_STATUS.NOT_STARTED in allowed_status:
                    status_combo.append(Q(start_date__gt=now))
                args.append(reduce(operator.or_, status_combo))
            if range_start:
                args.append(Q(end_date__gte=range_start))
            if range_end:
                args.append(Q(start_date__lte=range_end))
            if plan:
                args.append(Q(billing_plan__plan=plan))

            qs = qs.filter(*args)
            qs = self._prefetch_qs(qs)
            qs = SubscriptionRecord.objects.filter(
                pk__in=[
                    sr.pk
                    for sr in chain(
                        qs, *[r.addon_subscription_records.all() for r in qs]
                    )
                ]
            )

            if serializer.validated_data.get("subscription_filters"):
                for filter in serializer.validated_data["subscription_filters"]:
                    qs = qs.filter(
                        subscription_filters__contains=[
                            [filter["property_name"], filter["value"]]
                        ]
                    )

        return qs

    @extend_schema(
        parameters=[ListSubscriptionRecordFilter],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request)

    @extend_schema(
        responses=SubscriptionRecordSerializer,
    )
    def create(self, request, *args, **kwargs):
        now = now_utc()
        # run checks to make sure it's valid
        organization = self.request.organization
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # make sure subscription filters are valid
        subscription_filters = serializer.validated_data.get("subscription_filters", [])
        for sf in subscription_filters:
            if sf["property_name"] not in organization.subscription_filter_keys:
                raise ValidationError(
                    "Invalid subscription filter. Please check your subscription filters setting."
                )
        # check to see if subscription exists
        duration = serializer.validated_data["billing_plan"].plan.plan_duration
        start_date = convert_to_datetime(
            serializer.validated_data["start_date"], date_behavior="min"
        )
        day_anchor = (
            serializer.validated_data["billing_plan"].day_anchor
            or start_date.date().day
        )
        month_anchor = (
            serializer.validated_data["billing_plan"].month_anchor
            or start_date.date().month
        )
        timezone = serializer.validated_data["customer"].timezone
        end_date = calculate_end_date(
            duration,
            start_date,
            timezone,
            day_anchor=day_anchor,
            month_anchor=month_anchor,
        )
        end_date = serializer.validated_data.get("end_date", end_date)
        if end_date < now:
            raise ValidationError(
                "End date cannot be in the past. For historical backfilling of subscriptions, please contact support."
            )
        subscription_record = serializer.save(
            organization=organization,
        )

        # now we can actually create the subscription record
        response = SubscriptionRecordSerializer(subscription_record).data
        return Response(
            response,
            status=status.HTTP_201_CREATED,
        )

    # REGULAR SUBSCRIPTION RECORDS
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="subscription_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="The ID of the subscription to cancel.",
            )
        ],
        responses=SubscriptionRecordSerializer,
    )
    @action(detail=True, methods=["post"], url_path="cancel", url_name="cancel")
    def cancel(self, request, *args, **kwargs):
        sr = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        flat_fee_behavior = serializer.validated_data["flat_fee_behavior"]
        usage_behavior = serializer.validated_data["usage_behavior"]
        invoicing_behavior = serializer.validated_data["invoicing_behavior"]
        sr.cancel_subscription(
            bill_usage=usage_behavior == USAGE_BILLING_BEHAVIOR.BILL_FULL,
            flat_fee_behavior=flat_fee_behavior,
            invoice_now=invoicing_behavior == INVOICING_BEHAVIOR.INVOICE_NOW,
        )

        ret = SubscriptionRecordSerializer(sr).data
        return Response(ret, status=status.HTTP_200_OK)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="subscription_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="The ID of the subscription to update.",
            )
        ],
        responses=SubscriptionRecordSerializer,
    )
    @action(detail=True, methods=["post"], url_path="update", url_name="update")
    def update_subscription(self, request, *args, **kwargs):
        sr = self.get_object()
        serializer = self.get_serializer(sr, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        if getattr(sr, "_prefetched_objects_cache", None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            sr._prefetched_objects_cache = {}

        return Response(
            SubscriptionRecordSerializer(
                sr, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="subscription_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="The ID of the subscription which will have its plans switched.",
            )
        ],
        responses=SubscriptionRecordSerializer,
    )
    @action(
        detail=True, methods=["post"], url_path="switch_plan", url_name="switch_plan"
    )
    def switch_plan(self, request, *args, **kwargs):
        current_sr = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if "plan_version" in serializer.validated_data:
            new_billing_plan = serializer.validated_data["plan_version"]
        else:
            plan = serializer.validated_data["plan"]
            new_billing_plan = plan.get_version_for_customer(current_sr.customer)
        if new_billing_plan == current_sr.billing_plan:
            raise ValidationError("Cannot switch to the same plan.")
        if (
            new_billing_plan.plan.plan_duration
            != current_sr.billing_plan.plan.plan_duration
        ):
            raise ValidationError("Cannot switch to a plan with a different duration.")
        sr_plan_metrics = {
            pc.billable_metric
            for sub_rec in current_sr.addon_subscription_records.all()
            for pc in sub_rec.billing_plan.plan_components.all()
        }
        switch_plan_metrics = {
            pc.billable_metric for pc in new_billing_plan.plan_components.all()
        }
        if switch_plan_metrics.intersection(sr_plan_metrics):
            logger.debug(
                "Cannot switch to a plan with overlapping metrics with the current addons."
            )
            raise ValidationError(
                "Cannot switch to a plan with overlapping metrics with the current addons."
            )
        usage_behavior = serializer.validated_data.get("usage_behavior")
        billing_behavior = serializer.validated_data.get("invoicing_behavior")
        new_sr = current_sr.switch_plan(
            new_billing_plan,
            transfer_usage=usage_behavior
            == USAGE_BEHAVIOR.TRANSFER_TO_NEW_SUBSCRIPTION,
            invoice_now=billing_behavior == INVOICING_BEHAVIOR.INVOICE_NOW,
            component_fixed_charges_initial_units=serializer.validated_data.get(
                "component_fixed_charges_initial_units", []
            ),
        )
        current_sr.addon_subscription_records.update(parent=new_sr)
        return Response(
            SubscriptionRecordSerializer(new_sr).data, status=status.HTTP_200_OK
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="subscription_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="The ID of the subscription which will have its plans switched.",
            ),
            OpenApiParameter(
                name="metric_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="The ID of the metric to alter the prepaid usage for.",
            ),
        ],
        request=ChangePrepaidUnitsSerializer,
        responses=SubscriptionRecordSerializer,
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="components/(?P<metric_id>[^/.]+)/change_prepaid_units",
        url_name="change_prepaid_units",
    )
    def change_prepaid_units(self, request, *args, **kwargs):
        now = now_utc()
        organization = self.request.organization
        current_sr = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        parsed_metric_id = MetricUUIDField().to_internal_value(kwargs["metric_id"])
        metric = Metric.objects.get(
            metric_id=parsed_metric_id, organization=organization
        )
        units = serializer.validated_data["units"]
        current_billing_plan = current_sr.billing_plan
        target_plan_component = current_billing_plan.plan_components.filter(
            billable_metric=metric
        ).first()
        if not target_plan_component:
            raise ValidationError(
                "A plan component with the specified metric is not in the plan."
            )
        if target_plan_component.fixed_charge is None:
            raise ValidationError(
                "Cannot change prepaid units for a plan component with no fixed charge."
            )
        future_component_records = ComponentChargeRecord.objects.filter(
            billing_record__subscription=current_sr,
            component=target_plan_component,
            start_date__gt=now,
        )
        current_component_record = ComponentChargeRecord.objects.get(
            start_date__lte=now,
            end_date__gt=now,
            billing_record__subscription=current_sr,
            component=target_plan_component,
        )
        ComponentChargeRecord.objects.create(
            billing_record=current_component_record.billing_record,
            organization=organization,
            component_charge=target_plan_component.fixed_charge,
            component=target_plan_component,
            start_date=now,
            end_date=current_component_record.end_date,
            units=units,
        )
        current_component_record.end_date = now
        current_component_record.fully_billed = False
        current_component_record.save()
        future_component_records.update(units=units)
        if serializer.validated_data.get("invoice_now"):
            br = current_component_record.billing_record
            br.invoicing_dates = sorted(set(br.invoicing_dates + [now]))
            br.next_invoicing_date = now
            br.save()
            generate_invoice(current_sr)
        return Response(
            SubscriptionRecordSerializer(current_sr).data, status=status.HTTP_200_OK
        )

    # ADDON SUBSCRIPTION RECORDS
    @extend_schema(
        responses=AddOnSubscriptionRecordSerializer,
        parameters=[
            OpenApiParameter(
                name="subscription_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="The ID of the subscription to add an addon to.",
            )
        ],
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="addons/attach",
        url_name="attach_addon",
    )
    def attach_addon(self, request, *args, **kwargs):
        attach_to_sr = self.get_object()
        serializer = self.get_serializer(
            data=request.data,
            context={
                "attach_to_subscription_record": attach_to_sr,
                "customer": attach_to_sr.customer,
            },
        )
        serializer.is_valid(raise_exception=True)
        sr = serializer.save()
        return Response(
            AddOnSubscriptionRecordSerializer(sr).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="subscription_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="The ID of the subscription to update.",
            ),
            OpenApiParameter(
                name="addon_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="The ID of the addon within the subscription update.",
            ),
        ],
        responses=AddOnSubscriptionRecordSerializer(many=True),
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="addons/(?P<addon_id>[^/.]+)/cancel",
        url_name="cancel_addon",
    )
    def cancel_addon(self, request, *args, **kwargs):
        addon_sr = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        flat_fee_behavior = serializer.validated_data["flat_fee_behavior"]
        usage_behavior = serializer.validated_data["usage_behavior"]
        invoicing_behavior = serializer.validated_data["invoicing_behavior"]
        addon_sr.cancel_subscription(
            bill_usage=usage_behavior == USAGE_BILLING_BEHAVIOR.BILL_FULL,
            flat_fee_behavior=flat_fee_behavior,
            invoice_now=invoicing_behavior == INVOICING_BEHAVIOR.INVOICE_NOW,
        )
        return Response(
            AddOnSubscriptionRecordSerializer(addon_sr).data,
            status=status.HTTP_200_OK,
        )

    ## DEPRECATED METHODS
    @extend_schema(responses=SubscriptionRecordSerializer, deprecated=True)
    @action(detail=False, methods=["post"])
    def add(self, request, *args, **kwargs):
        now = now_utc()
        # run checks to make sure it's valid
        organization = self.request.organization
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # make sure subscription filters are valid
        subscription_filters = serializer.validated_data.get("subscription_filters", [])
        for sf in subscription_filters:
            if sf["property_name"] not in organization.subscription_filter_keys:
                raise ValidationError(
                    "Invalid subscription filter. Please check your subscription filters setting."
                )
        # check to see if subscription exists
        duration = serializer.validated_data["billing_plan"].plan.plan_duration
        start_date = convert_to_datetime(
            serializer.validated_data["start_date"], date_behavior="min"
        )
        day_anchor = (
            serializer.validated_data["billing_plan"].day_anchor
            or start_date.date().day
        )
        month_anchor = (
            serializer.validated_data["billing_plan"].month_anchor
            or start_date.date().month
        )
        timezone = serializer.validated_data["customer"].timezone
        end_date = calculate_end_date(
            duration,
            start_date,
            timezone,
            day_anchor=day_anchor,
            month_anchor=month_anchor,
        )
        end_date = serializer.validated_data.get("end_date", end_date)
        if end_date < now:
            raise ValidationError(
                "End date cannot be in the past. For historical backfilling of subscriptions, please contact support."
            )
        subscription_record = serializer.save(
            organization=organization,
        )

        # now we can actually create the subscription record
        response = SubscriptionRecordSerializer(subscription_record).data
        subscription_created_webhook(subscription_record, subscription_data=response)

        try:
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (organization.organization_name + " (Unknown)"),
                event="DEPRECATED_add_subscription",
                properties={
                    "organization": organization.organization_name,
                    "subscription": response,
                },
            )
        except Exception:
            pass
        return Response(
            response,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        parameters=[
            SubscriptionRecordFilterSerializerDelete,
        ],
        responses={200: SubscriptionRecordSerializer(many=True)},
        deprecated=True,
    )
    @action(detail=False, methods=["post"], url_path="cancel", url_name="multi-cancel")
    def cancel_multi(self, request, *args, **kwargs):
        qs = self.get_queryset()
        original_qs = list(copy.copy(qs).values_list("pk", flat=True))
        organization = self.request.organization
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        flat_fee_behavior = serializer.validated_data["flat_fee_behavior"]
        usage_behavior = serializer.validated_data["usage_behavior"]
        invoicing_behavior = serializer.validated_data["invoicing_behavior"]
        for sr in qs:
            sr.cancel_subscription(
                bill_usage=usage_behavior == USAGE_BILLING_BEHAVIOR.BILL_FULL,
                flat_fee_behavior=flat_fee_behavior,
                invoice_now=invoicing_behavior == INVOICING_BEHAVIOR.INVOICE_NOW,
            )

        return_qs = SubscriptionRecord.base_objects.filter(
            pk__in=original_qs, organization=organization
        )

        ret = SubscriptionRecordSerializer(return_qs, many=True).data

        for subscription in qs:
            subscription_data = SubscriptionRecordSerializer(subscription).data
            subscription_cancelled_webhook(subscription, subscription_data)

            try:
                posthog.capture(
                    POSTHOG_PERSON
                    if POSTHOG_PERSON
                    else (organization.organization_name + " (Unknown)"),
                    event="DEPRECATED_cancel_subscription",
                    properties={
                        "organization": organization.organization_name,
                        "subscription": subscription_data,
                    },
                )
            except Exception:
                pass

        return Response(ret, status=status.HTTP_200_OK)

    @extend_schema(
        parameters=[SubscriptionRecordFilterSerializer],
        responses={200: SubscriptionRecordSerializer(many=True)},
    )
    @action(detail=False, methods=["post"], url_path="update")
    def edit(self, request, *args, **kwargs):
        qs = self.get_queryset()
        organization = self.request.organization
        original_qs = list(copy.copy(qs).values_list("pk", flat=True))
        if qs.count() == 0:
            raise NotFoundException("Subscription matching the given filters not found")
        plan_to_replace = qs.first().billing_plan
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        switch_plan = serializer.validated_data.get("plan")
        if switch_plan:
            possible_billing_plans = switch_plan.versions.all()
            current_currency = qs.first().billing_plan.currency
            possible_billing_plans = possible_billing_plans.filter(
                currency=current_currency
            )
            if possible_billing_plans.count() == 0:
                raise InvalidOperation(
                    "Cannot switch to a plan with a different currency"
                )
            elif possible_billing_plans.count() == 1:
                replace_billing_plan = possible_billing_plans.first()
            else:
                # if there are multiple billing plans with the same currency, we need to
                # prioritize 1. active billing plans, 2. billing plans with customer as target
                active_billing_plans = possible_billing_plans.active()
                if active_billing_plans.count() == 0:
                    raise InvalidOperation(
                        "Cannot switch to a plan with no matching active versions"
                    )
                elif active_billing_plans.count() == 1:
                    replace_billing_plan = active_billing_plans.first()
                else:
                    matching_plans_active = []
                    for bp in active_billing_plans:
                        if qs.first().customer in bp.target_customers.all():
                            matching_plans_active.append(bp)
                    if len(matching_plans_active) == 1:
                        replace_billing_plan = matching_plans_active[0]
                    else:
                        raise InvalidOperation(
                            "Could not determine correct billing plan to replace with"
                        )
        else:
            replace_billing_plan = None
        if replace_billing_plan:
            if replace_billing_plan == plan_to_replace:
                raise SwitchPlanSamePlanException("Cannot switch to the same plan")
            elif (
                replace_billing_plan.plan.plan_duration
                != plan_to_replace.plan.plan_duration
            ):
                raise SwitchPlanDurationMismatch(
                    "Cannot switch to a plan with a different duration"
                )
        billing_behavior = serializer.validated_data.get("invoicing_behavior")
        usage_behavior = serializer.validated_data.get("usage_behavior")
        turn_off_auto_renew = serializer.validated_data.get("turn_off_auto_renew")
        end_date = serializer.validated_data.get("end_date")
        if replace_billing_plan:
            qs = qs.filter(
                billing_plan__addon_spec__isnull=True
            )  # no addons in replace
            switch_plan_metrics = {
                pc.billable_metric for pc in replace_billing_plan.plan_components.all()
            }
            for subscription_record in qs:
                original_sub_record_plan_metrics = {
                    pc.billable_metric
                    for sub_rec in subscription_record.addon_subscription_records.all()
                    for pc in sub_rec.billing_plan.plan_components.all()
                }
                if switch_plan_metrics.intersection(original_sub_record_plan_metrics):
                    logger.debug(
                        "Cannot switch to a plan with overlapping metrics with the current addons."
                    )
                    original_qs.remove(subscription_record.pk)
                    continue
                subscription_record.switch_plan(
                    replace_billing_plan,
                    transfer_usage=usage_behavior
                    == USAGE_BEHAVIOR.TRANSFER_TO_NEW_SUBSCRIPTION,
                    invoice_now=billing_behavior == INVOICING_BEHAVIOR.INVOICE_NOW,
                )
        else:
            update_dict = {}
            if turn_off_auto_renew:
                update_dict["auto_renew"] = False
            if end_date:
                update_dict["end_date"] = end_date
            if len(update_dict) > 0:
                qs.update(**update_dict)

        return_qs = SubscriptionRecord.base_objects.filter(
            pk__in=original_qs, organization=organization
        )
        ret = SubscriptionRecordSerializer(return_qs, many=True).data

        try:
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (organization.organization_name + " (Unknown)"),
                event="DEPRECATED_update_subscription",
                properties={
                    "organization": organization.organization_name,
                },
            )
        except Exception:
            pass
        return Response(ret, status=status.HTTP_200_OK)

        ## DISPATCH

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except Exception:
                username = None
            organization = self.request.organization
            try:
                posthog.capture(
                    POSTHOG_PERSON
                    if POSTHOG_PERSON
                    else (
                        username
                        if username
                        else organization.organization_name + " (API Key)"
                    ),
                    event=f"{self.action}_subscription",
                    properties={"organization": organization.organization_name},
                )
            except Exception:
                pass
            # if username:
            #     if self.action == "plans":
            #         action.send(
            #             self.request.user,
            #             verb="attached",
            #             action_object=instance.customer,
            #             target=instance.billing_plan,
            #         )

        return response


class InvoiceViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    http_method_names = ["get", "patch", "head"]
    lookup_field = "invoice_id"
    queryset = Invoice.objects.all()
    permission_classes_per_method = {
        "partial_update": [IsAuthenticated & ValidOrganization],
    }

    def get_object(self):
        lookup_field = "invoice_id"
        string_id = self.kwargs[lookup_field]
        # Check if the string_id matches the invoice number format YYMMDD-000001
        if re.match(r"\d{6}-\d{6}", string_id):
            lookup_field = "invoice_number"
        else:
            # Check if the string_id starts with "invoice_"
            if string_id.startswith("invoice_"):
                string_id = string_id[8:]
            # Replace dashes in the string_id if any
            string_id = InvoiceUUIDField().to_internal_value(string_id.replace("-", ""))
        self.kwargs[lookup_field] = string_id
        # Log the lookup value using drf-spectacular
        self.instance = super().get_object()
        return self.instance

    def get_queryset(self):
        args = [
            ~Q(payment_status=Invoice.PaymentStatus.DRAFT),
            Q(organization=self.request.organization),
        ]
        if self.action == "list":
            serializer = InvoiceListFilterSerializer(
                data=self.request.query_params, context=self.get_serializer_context()
            )
            serializer.is_valid(raise_exception=True)
            args.append(
                Q(payment_status__in=serializer.validated_data["payment_status"])
            )
            if serializer.validated_data.get("customer"):
                args.append(Q(customer=serializer.validated_data["customer"]))

        return Invoice.objects.filter(*args)

    def get_serializer_class(self, default=None):
        if self.action == "partial_update":
            return InvoiceUpdateSerializer
        if default:
            return default
        return InvoiceSerializer

    @extend_schema(request=InvoiceUpdateSerializer, responses=InvoicePaymentSerializer)
    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        invoice = self.get_object()
        serializer = self.get_serializer(invoice, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        if getattr(invoice, "_prefetched_objects_cache", None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            invoice._prefetched_objects_cache = {}

        return Response(
            InvoiceSerializer(invoice, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        organization = self.request.organization
        context.update({"organization": organization})
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except Exception:
                username = None
            organization = self.request.organization
            try:
                posthog.capture(
                    POSTHOG_PERSON
                    if POSTHOG_PERSON
                    else (
                        username
                        if username
                        else organization.organization_name + " (API Key)"
                    ),
                    event=f"{self.action}_invoice",
                    properties={"organization": organization.organization_name},
                )
            except Exception:
                pass
        return response

    @extend_schema(
        parameters=[InvoiceListFilterSerializer],
    )
    def list(self, request):
        return super().list(request)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="invoice_id",
                required=True,
                location=OpenApiParameter.PATH,
                description="Either an invoice ID (in the format `invoice_<uuid>`) or an invoice number (in the format `YYMMDD-000001`)",
            )
        ]
    )
    @action(detail=True, methods=["get"])
    def pdf_url(self, request, *args, **kwargs):
        invoice = self.get_object()
        url = get_invoice_presigned_url(invoice).get("url")
        return Response(
            {"url": url},
            status=status.HTTP_200_OK,
        )


class CustomerBalanceAdjustmentViewSet(
    PermissionPolicyMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [ValidOrganization]
    http_method_names = ["get", "head", "post"]
    serializer_class = CustomerBalanceAdjustmentSerializer
    lookup_field = "credit_id"
    queryset = CustomerBalanceAdjustment.objects.all()

    def get_object(self):
        string_uuid = self.kwargs.pop(self.lookup_field, None)
        uuid = BalanceAdjustmentUUIDField().to_internal_value(string_uuid)
        if self.lookup_field == "credit_id":
            self.lookup_field = "adjustment_id"
        self.kwargs[self.lookup_field] = uuid
        obj = super().get_object()
        self.lookup_field = "credit_id"
        return obj

    def get_serializer_class(self):
        if self.action == "list":
            return CustomerBalanceAdjustmentSerializer
        elif self.action == "create":
            return CustomerBalanceAdjustmentCreateSerializer
        elif self.action == "void":
            return EmptySerializer
        elif self.action == "edit":
            return CustomerBalanceAdjustmentUpdateSerializer
        return CustomerBalanceAdjustmentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        organization = self.request.organization
        qs = qs.filter(organization=organization)
        context = self.get_serializer_context()
        context["organization"] = organization
        qs = qs.filter(amount__gt=0)
        qs = qs.select_related("customer", "pricing_unit", "amount_paid_currency")
        qs = qs.prefetch_related("drawdowns")
        qs = qs.annotate(
            total_drawdowns=Sum("drawdowns__amount"),
        )
        if self.action == "list":
            args = []
            serializer = CustomerBalanceAdjustmentFilterSerializer(
                data=self.request.query_params, context=context
            )
            serializer.is_valid(raise_exception=True)
            allowed_status = serializer.validated_data.get("status")
            if len(allowed_status) == 0:
                allowed_status = [
                    CUSTOMER_BALANCE_ADJUSTMENT_STATUS.ACTIVE,
                    CUSTOMER_BALANCE_ADJUSTMENT_STATUS.INACTIVE,
                ]
            expires_before = serializer.validated_data.get("expires_before")
            expires_after = serializer.validated_data.get("expires_after")
            issued_before = serializer.validated_data.get("issued_before")
            issued_after = serializer.validated_data.get("issued_after")
            effective_before = serializer.validated_data.get("effective_before")
            effective_after = serializer.validated_data.get("effective_after")
            if expires_after:
                args.append(
                    Q(expires_at__gte=expires_after) | Q(expires_at__isnull=True)
                )
            if expires_before:
                args.append(Q(expires_at__lte=expires_before))
            if issued_after:
                args.append(Q(created__gte=issued_after))
            if issued_before:
                args.append(Q(created__lte=issued_before))
            if effective_after:
                args.append(Q(effective_at__gte=effective_after))
            if effective_before:
                args.append(Q(effective_at__lte=effective_before))
            args.append(Q(customer=serializer.validated_data["customer"]))
            status_combo = []
            for baladj_status in allowed_status:
                status_combo.append(Q(status=baladj_status))
            args.append(reduce(operator.or_, status_combo))
            if serializer.validated_data.get("pricing_unit"):
                args.append(Q(pricing_unit=serializer.validated_data["pricing_unit"]))
            qs = qs.filter(
                *args,
            ).select_related("customer")
            if serializer.validated_data.get("pricing_unit"):
                qs = qs.select_related("pricing_unit")
        return qs

    def get_serializer_context(self):
        context = super().get_serializer_context()
        organization = self.request.organization
        context.update({"organization": organization})
        return context

    @extend_schema(responses=CustomerBalanceAdjustmentSerializer)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        metric_data = CustomerBalanceAdjustmentSerializer(instance).data
        return Response(metric_data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        return serializer.save(organization=self.request.organization)

    @extend_schema(
        parameters=[CustomerBalanceAdjustmentFilterSerializer],
        responses=CustomerBalanceAdjustmentSerializer(many=True),
    )
    def list(self, request):
        return super().list(request)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="credit_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="The ID of the credit to retrieve or update.",
            )
        ],
        responses=CustomerBalanceAdjustmentSerializer,
    )
    @action(detail=True, methods=["post"])
    def void(self, request, credit_id=None):
        adjustment = self.get_object()
        if adjustment.status != CUSTOMER_BALANCE_ADJUSTMENT_STATUS.ACTIVE:
            raise ValidationError("Cannot void an adjustment that is not active.")
        if adjustment.amount <= 0:
            raise ValidationError("Cannot delete a negative adjustment.")
        adjustment.zero_out(reason="voided")
        return Response(
            CustomerBalanceAdjustmentSerializer(
                adjustment, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="credit_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="The ID of the credit to retrieve or update.",
            )
        ],
        responses=CustomerBalanceAdjustmentSerializer,
    )
    @action(detail=True, methods=["post"], url_path="update")
    def edit(self, request, credit_id=None):
        adjustment = self.get_object()
        serializer = self.get_serializer(adjustment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        if getattr(adjustment, "_prefetched_objects_cache", None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            adjustment._prefetched_objects_cache = {}

        return Response(
            CustomerBalanceAdjustmentSerializer(
                adjustment, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="credit_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="The ID of the credit to retrieve or update.",
            )
        ]
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except Exception:
                username = None
            organization = self.request.organization
            try:
                posthog.capture(
                    POSTHOG_PERSON
                    if POSTHOG_PERSON
                    else (
                        username
                        if username
                        else organization.organization_name + " (API Key)"
                    ),
                    event=f"{self.action}_balance_adjustment",
                    properties={"organization": organization.organization_name},
                )
            except Exception:
                pass
            # if username:
            #     if self.action == "plans":
            #         action.send(
            #             self.request.user,
            #             verb="attached",
            #             action_object=instance.customer,
            #             target=instance.billing_plan,
            #         )

        return response


class MetricAccessView(APIView):
    permission_classes = []
    authentication_classes = []

    @extend_schema(
        parameters=[MetricAccessRequestSerializer],
        responses={
            200: MetricAccessResponseSerializer,
        },
    )
    def get(self, request, format=None):
        result, success = fast_api_key_validation_and_cache(request)
        now = now_utc()
        if not success:
            return result
        else:
            organization_pk = result
        serializer = MetricAccessRequestSerializer(
            data=request.query_params, context={"organization_pk": organization_pk}
        )
        serializer.is_valid(raise_exception=True)
        customer = serializer.validated_data["customer"]
        metric = serializer.validated_data["metric"]
        subscription_records = SubscriptionRecord.objects.active().filter(
            organization_id=organization_pk,
            customer=customer,
        )
        subscription_filters_set = {
            (x["property_name"], x["value"])
            for x in serializer.validated_data.get("subscription_filters", [])
        }
        subscription_records = subscription_records.prefetch_related(
            "billing_records",
            "addon_subscription_records",
            "billing_plan__plan_components",
            "billing_plan__plan_components__billable_metric",
            "billing_plan__plan_components__tiers",
            "billing_plan__plan",
        )
        return_dict = {
            "customer": customer,
            "metric": metric,
            "access": False,
            "access_per_subscription": [],
        }
        for sr in subscription_records.filter(billing_plan__addon_spec__isnull=True):
            if subscription_filters_set:
                sr_filters_set = {tuple(x) for x in sr.subscription_filters}
                if not subscription_filters_set.issubset(sr_filters_set):
                    continue
            single_sr_dict = {
                "subscription": sr,
                "metric_usage": 0,
                "metric_free_limit": 0,
                "metric_total_limit": 0,
            }
            matching_billing_records = sr.billing_records.filter(
                start_date__lte=now,
                end_date__gte=now,
                component__billable_metric=metric,
            )
            for addon_sr in sr.addon_subscription_records.all():
                matching_billing_records = (
                    matching_billing_records
                    | addon_sr.billing_records.filter(
                        start_date__lte=now,
                        end_date__gte=now,
                        component__billable_metric=metric,
                    )
                )
            if len(matching_billing_records) > 0:
                billing_record = matching_billing_records.first()
                component = billing_record.component
                tiers = sorted(component.tiers.all(), key=lambda x: x.range_start)
                free_limit = (
                    tiers[0].range_end
                    if tiers[0].type == PriceTier.PriceTierType.FREE
                    else 0
                )
                total_limit = tiers[-1].range_end
                current_usage = metric.get_billing_record_current_usage(billing_record)
                single_sr_dict["metric_usage"] = current_usage
                single_sr_dict["metric_free_limit"] = free_limit
                single_sr_dict["metric_total_limit"] = total_limit
            return_dict["access_per_subscription"].append(single_sr_dict)
        access = []
        for sr_dict in return_dict["access_per_subscription"]:
            if sr_dict["metric_usage"] < (
                sr_dict["metric_total_limit"] or Decimal("Infinity")
            ):
                access.append(True)
            elif sr_dict["metric_total_limit"] == 0:
                continue
            else:
                access.append(False)
        return_dict["access"] = any(access)
        serializer = MetricAccessResponseSerializer(return_dict)
        return Response(serializer.data, status=status.HTTP_200_OK)


class FeatureAccessView(APIView):
    permission_classes = []
    authentication_classes = []

    @extend_schema(
        parameters=[FeatureAccessRequestSerializer],
        responses={
            200: FeatureAccessResponseSerializer,
        },
    )
    def get(self, request, format=None):
        result, success = fast_api_key_validation_and_cache(request)
        if not success:
            return result
        else:
            organization_pk = result
        serializer = FeatureAccessRequestSerializer(
            data=request.query_params, context={"organization_pk": organization_pk}
        )
        serializer.is_valid(raise_exception=True)
        customer = serializer.validated_data["customer"]
        feature = serializer.validated_data["feature"]
        subscription_records = SubscriptionRecord.objects.active().filter(
            organization_id=organization_pk,
            customer=customer,
        )
        subscription_filters_set = {
            (x["property_name"], x["value"])
            for x in serializer.validated_data.get("subscription_filters", [])
        }
        subscription_records = subscription_records.prefetch_related(
            "billing_plan__features",
            "billing_plan__plan",
        )
        return_dict = {
            "customer": customer,
            "feature": feature,
            "access": False,
            "access_per_subscription": [],
        }
        for sr in subscription_records.filter(billing_plan__addon_spec__isnull=True):
            if subscription_filters_set:
                sr_filters_set = {tuple(x) for x in sr.subscription_filters}
                if not subscription_filters_set.issubset(sr_filters_set):
                    continue
            single_sr_dict = {
                "subscription": sr,
                "access": False,
            }
            all_billing_plan_features = sr.billing_plan.features.all()
            for addon in sr.addon_subscription_records.all():
                all_billing_plan_features = (
                    all_billing_plan_features | addon.billing_plan.features.all()
                )
            if feature in all_billing_plan_features.distinct():
                single_sr_dict["access"] = True
            return_dict["access_per_subscription"].append(single_sr_dict)
        access = [d["access"] for d in return_dict["access_per_subscription"]]
        return_dict["access"] = any(access)
        serializer = FeatureAccessResponseSerializer(return_dict)
        return Response(serializer.data, status=status.HTTP_200_OK)


class Ping(APIView):
    permission_classes = [HasUserAPIKey & ValidOrganization]

    @extend_schema(
        description="Ping the API to check if the API key is valid.",
        responses={
            200: inline_serializer(
                name="ConfirmConnected",
                fields={
                    "organization_id": serializers.CharField(),
                },
            )
        },
        examples=[
            OpenApiExample(
                "ConfirmConnected",
                summary="Example response for ConfirmConnected",
                value={
                    "organization_id": "org_088c5d194bef40ed9aaeb72d42bd7945",
                },
            )
        ],
    )
    def get(self, request, format=None):
        organization = request.organization
        return Response(
            {
                "organization_id": OrganizationUUIDField().to_representation(
                    organization.organization_id
                ),
            },
            status=status.HTTP_200_OK,
        )


class Healthcheck(APIView):
    permission_classes = []
    authentication_classes = []

    @extend_schema(
        responses={
            200: inline_serializer(
                name="HealthcheckResponse",
                fields={},
            ),
        },
    )
    def get(self, request, format=None):
        return Response(
            {},
            status=status.HTTP_200_OK,
        )


class ConfirmIdemsReceivedView(APIView):
    permission_classes = [IsAuthenticated | HasUserAPIKey]

    @extend_schema(
        request=inline_serializer(
            name="ConfirmIdemsReceivedRequest",
            fields={
                "idempotency_ids": serializers.ListField(
                    child=serializers.CharField(), required=True
                ),
                "number_days_lookback": serializers.IntegerField(
                    default=30, required=False
                ),
                "customer_id": serializers.CharField(required=False),
            },
        ),
        responses={
            200: inline_serializer(
                name="ConfirmIdemsReceived",
                fields={
                    "status": serializers.ChoiceField(choices=["success"]),
                    "ids_not_found": serializers.ListField(
                        child=serializers.CharField(), required=True
                    ),
                },
            ),
            400: inline_serializer(
                name="ConfirmIdemsReceivedFailure",
                fields={
                    "status": serializers.ChoiceField(choices=["failure"]),
                    "error": serializers.CharField(),
                },
            ),
        },
    )
    def post(self, request, format=None):
        organization = request.organization
        if request.data.get("idempotency_ids") is None:
            return Response(
                {
                    "status": "failure",
                    "error": "idempotency_ids is required",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if isinstance(request.data.get("idempotency_ids"), str):
            idempotency_ids = {request.data.get("idempotency_ids")}
        else:
            idempotency_ids = list(set(request.data.get("idempotency_ids")))
        number_days_lookback = request.data.get("number_days_lookback", 30)
        now_minus_lookback = now_utc() - relativedelta(days=number_days_lookback)
        num_batches_idems = len(idempotency_ids) // 1000 + 1
        ids_not_found = []
        for i in range(num_batches_idems):
            idem_batch = set(idempotency_ids[i * 1000 : (i + 1) * 1000])
            idem_batch = {uuid.uuid5(IDEMPOTENCY_ID_NAMESPACE, x) for x in idem_batch}
            events = Event.objects.filter(
                organization=organization,
                time_created__gte=now_minus_lookback,
                uuidv5_idempotency_id__in=idem_batch,
            )
            if request.data.get("customer_id"):
                events = events.filter(customer_id=request.data.get("customer_id"))
            events_set = set(events.values_list("idempotency_id", flat=True))
            ids_not_found += list(idem_batch - events_set)
        return Response(
            {
                "status": "success",
                "ids_not_found": ids_not_found,
            },
            status=status.HTTP_200_OK,
        )


def load_event(request: HttpRequest) -> Optional[dict]:
    """
    Loads an event from the request body.
    """
    if request.content_type == "application/json":
        try:
            event_data = json.loads(request.body)
            return event_data
        except json.JSONDecodeError as e:
            logger.error(e)
            # if not, it's probably base64 encoded from other libraries
            event_data = json.loads(
                base64.b64decode(request + "===")
                .decode("utf8", "surrogatepass")
                .encode("utf-16", "surrogatepass")
            )
    else:
        event_data = request.body.decode("utf8")

    return event_data


def ingest_event(data: dict, customer_id: str, organization_pk: int) -> None:
    event_kwargs = {
        "organization_id": organization_pk,
        "cust_id": customer_id,
        "customer_id": customer_id,
        "event_name": data["event_name"],
        "idempotency_id": data["idempotency_id"],
        "time_created": data["time_created"],
        "properties": {},
    }
    if "properties" in data:
        event_kwargs["properties"] = data["properties"]
    return event_kwargs


@csrf_exempt
@extend_schema(
    request=inline_serializer(
        "BatchEventSerializer", fields={"batch": EventSerializer(many=True)}
    ),
    responses={
        201: inline_serializer(
            name="TrackEventSuccess",
            fields={
                "success": serializers.ChoiceField(choices=["all", "some"]),
                "failed_events": serializers.DictField(),
            },
        ),
        400: inline_serializer(
            name="TrackEventFailure",
            fields={
                "success": serializers.ChoiceField(choices=["none"]),
                "failed_events": serializers.DictField(),
            },
        ),
    },
)
@api_view(http_method_names=["POST"])
@authentication_classes([])
@permission_classes([])
def track_event(request):
    result, success = fast_api_key_validation_and_cache(request)
    if not success:
        return result
    else:
        organization_pk = result

    try:
        event_list = load_event(request)
    except Exception as e:
        return HttpResponseBadRequest(f"Invalid event data: {e}")
    if not event_list:
        return HttpResponseBadRequest("No data provided")
    if not isinstance(event_list, list):
        if "batch" in event_list:
            event_list = event_list["batch"]
        else:
            event_list = [event_list]

    bad_events = {}
    now = now_utc()
    for data in event_list:
        customer_id = data.get("customer_id")
        idempotency_id = data.get("idempotency_id")
        time_created = data.get("time_created")
        if not idempotency_id:
            bad_events["no_idempotency_id"] = "No idempotency_id provided"
            continue
        if not customer_id:
            bad_events[idempotency_id] = "No customer_id provided"
            continue
        if not time_created:
            bad_events[idempotency_id] = "Invalid time_created"
            continue
        tc = parser.parse(time_created)
        # Check if the datetime object is naive
        if tc.tzinfo is None or tc.tzinfo.utcoffset(tc) is None:
            # If the datetime object is naive, replace its tzinfo with UTC
            tc = tc.replace(tzinfo=pytz.UTC)
        if not (now - relativedelta(days=30) <= tc <= now + relativedelta(days=1)):
            bad_events[
                idempotency_id
            ] = "Time created too far in the past or future. Events must be within 30 days before or 1 day ahead of current time."
            continue
        data["time_created"] = tc.isoformat()
        try:
            transformed_event = ingest_event(data, customer_id, organization_pk)
            stream_events = {
                "organization_id": organization_pk,
                "event": transformed_event,
            }
            if kafka_producer:
                kafka_producer.produce(customer_id, stream_events)
        except Exception as e:
            bad_events[idempotency_id] = str(e)
            continue

    if len(bad_events) == len(event_list):
        return Response(
            {"success": "none", "failed_events": bad_events},
            status=status.HTTP_400_BAD_REQUEST,
        )
    elif len(bad_events) > 0:
        return JsonResponse(
            {"success": "some", "failed_events": bad_events},
            status=status.HTTP_201_CREATED,
        )
    else:
        return JsonResponse({"success": "all"}, status=status.HTTP_201_CREATED)


###### DEPRECATED ######
class GetCustomerEventAccessRequestSerializer(serializers.Serializer):
    customer_id = SlugRelatedFieldWithOrganizationPK(
        slug_field="customer_id",
        queryset=Customer.objects.all(),
        help_text="The customer_id of the customer you want to check access.",
    )
    event_name = serializers.CharField(
        help_text="The name of the event you are checking access for.",
        required=False,
        allow_null=True,
    )
    metric_id = SlugRelatedFieldWithOrganizationPK(
        slug_field="metric_id",
        queryset=Metric.objects.all(),
        required=False,
        allow_null=True,
        help_text="The metric_id of the metric you are checking access for. Please note that you must porovide exactly one of event_name and metric_id are mutually; a validation error will be thrown if both or none are provided.",
    )
    subscription_filters = SubscriptionFilterSerializer(
        many=True,
        required=False,
        help_text="The subscription filters that are applied to this plan's relationship with the customer. If your billing model does not have the ability multiple plans or subscriptions per customer, this is likely not relevant for you. This must be passed in as a stringified JSON object.",
    )

    def validate(self, data):
        data = super().validate(data)
        data["metric"] = data.pop("metric_id", None)
        data["customer"] = data.pop("customer_id", None)
        if data.get("event_name") is not None and data.get("metric") is not None:
            raise serializers.ValidationError(
                "event_name and metric_id are mutually exclusive. Please only provide one."
            )
        if data.get("event_name") is None and data.get("metric") is None:
            raise serializers.ValidationError(
                "You must provide either an event_name or a metric_id."
            )

        return data


class GetCustomerFeatureAccessRequestSerializer(serializers.Serializer):
    customer_id = SlugRelatedFieldWithOrganizationPK(
        slug_field="customer_id",
        queryset=Customer.objects.all(),
        help_text="The customer_id of the customer you want to check access.",
    )
    feature_name = serializers.CharField(
        help_text="Name of the feature to check access for."
    )
    subscription_filters = SubscriptionFilterSerializer(
        many=True,
        required=False,
        help_text="The subscription filters that are applied to this plan's relationship with the customer. If your billing model does not have the ability multiple plans or subscriptions per customer, this is likely not relevant for you. This must be passed in as a stringified JSON object.",
    )

    def validate(self, data):
        data = super().validate(data)
        data["customer"] = data.pop("customer_id", None)

        return data


class GetFeatureAccessSerializer(serializers.Serializer):
    feature_name = serializers.CharField(
        help_text="Name of the feature to check access for."
    )
    plan_id = serializers.CharField(
        help_text="The plan_id of the plan we are checking that has access to this feature."
    )
    subscription_filters = SubscriptionFilterSerializer(
        many=True,
        help_text="The subscription filters that are applied to this plan's relationship with the customer. If your billing model does not have the ability multiple plans or subscriptions per customer, this is likely not relevant for you.",
    )
    access = serializers.BooleanField(
        help_text="Whether or not the plan has access to this feature. If your customer can have multiple plans or subscriptions, then you must check the 'access' across all returned plans to determine if the customer can access this feature."
    )


class ComponentUsageSerializer(serializers.Serializer):
    event_name = serializers.CharField(
        help_text="The name of the event you are checking access for."
    )
    metric_name = serializers.CharField(help_text="The name of the metric.")
    metric_id = serializers.CharField(
        help_text="The metric_id of the metric. This metric_id can be found in the Lotus frontend if you haven't seen it before."
    )
    metric_usage = serializers.FloatField(
        help_text="The current usage of the metric. Keep in mind the current usage of the metric can be different from the billable usage of the metric."
    )
    metric_free_limit = serializers.FloatField(
        allow_null=True,
        help_text="If you specified a free tier of usage for this metric, this is the amount of usage that is free. Will be null if you did not specify a free tier for this metric.",
    )
    metric_total_limit = serializers.FloatField(
        allow_null=True,
        help_text="The total limit of the metric. Will be null if you did not specify a limit for this metric.",
    )


class GetEventAccessSerializer(serializers.Serializer):
    plan_id = serializers.CharField(
        help_text="The plan_id of the plan we are checking that has access to this feature."
    )
    subscription_filters = SubscriptionFilterSerializer(
        many=True,
        help_text="The subscription filters that are applied to this plan's relationship with the customer. If your billing model does not have the ability multiple plans or subscriptions per customer, this is likely not relevant for you.",
    )
    usage_per_component = ComponentUsageSerializer(
        many=True,
        help_text="The usage of each component of the plan the customer is on. Only components that match the request will be included: If metric_id is provided, this will be a list of length 1. If event_name is provided, this will be a list of length 1 or more depending on how many components of the customer's plan use this event.",
    )


class GetCustomerFeatureAccessView(APIView):
    permission_classes = []
    authentication_classes = []

    @extend_schema(
        parameters=[GetCustomerFeatureAccessRequestSerializer],
        responses={
            200: GetFeatureAccessSerializer(many=True),
        },
        deprecated=True,
    )
    def get(self, request, format=None):
        organization = request.organization
        result, success = fast_api_key_validation_and_cache(request)
        if not success:
            return result
        else:
            organization_pk = result
        serializer = GetCustomerFeatureAccessRequestSerializer(
            data=request.query_params, context={"organization_pk": organization_pk}
        )
        serializer.is_valid(raise_exception=True)
        try:
            username = self.request.user.username
        except Exception:
            username = None
        try:
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (username if username else result + " (Unknown)"),
                event="DEPRECATED_get_feature_access",
                properties={"organization": organization.organization_name},
            )
        except Exception:
            pass
        customer = serializer.validated_data["customer"]
        feature_name = serializer.validated_data.get("feature_name")
        subscriptions = (
            SubscriptionRecord.objects.active()
            .select_related("billing_plan")
            .filter(
                organization_id=organization_pk,
                customer=customer,
            )
        )
        subscription_filters = {
            x["property_name"]: x["value"]
            for x in serializer.validated_data.get("subscription_filters", [])
        }
        for key, value in subscription_filters.items():
            subscriptions = subscriptions.filter(
                subscription_filters__contains=[[key, value]]
            )
        features = []
        subscriptions = subscriptions.prefetch_related("billing_plan__features")
        for sub in subscriptions:
            subscription_filters = []
            for filter_arr in sub.subscription_filters:
                subscription_filters.append(
                    {
                        "property_name": filter_arr[0],
                        "value": filter_arr[1],
                    }
                )
            sub_dict = {
                "feature_name": feature_name,
                "plan_id": PlanUUIDField().to_representation(
                    sub.billing_plan.plan.plan_id
                ),
                "subscription_filters": subscription_filters,
                "access": False,
            }
            for feature in sub.billing_plan.features.all():
                if feature.feature_name == feature_name:
                    sub_dict["access"] = True
            features.append(sub_dict)
        GetFeatureAccessSerializer(many=True).validate(features)
        return Response(
            features,
            status=status.HTTP_200_OK,
        )


class GetCustomerEventAccessView(APIView):
    permission_classes = []
    authentication_classes = []

    @extend_schema(
        parameters=[GetCustomerEventAccessRequestSerializer],
        responses={
            200: GetEventAccessSerializer(many=True),
        },
        deprecated=True,
    )
    def get(self, request, format=None):
        organization = request.organization
        result, success = fast_api_key_validation_and_cache(request)
        if not success:
            return result
        else:
            organization_pk = result
        serializer = GetCustomerEventAccessRequestSerializer(
            data=request.query_params, context={"organization_pk": organization_pk}
        )
        serializer.is_valid(raise_exception=True)
        try:
            username = self.request.user.username
        except Exception:
            username = None
        try:
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (
                    username
                    if username
                    else organization.organization_name + " (Unknown)"
                ),
                event="DEPRECATED_get_metric_access",
                properties={"organization": organization.organization_name},
            )
        except Exception:
            pass

        customer = serializer.validated_data["customer"]
        event_name = serializer.validated_data.get("event_name")
        access_metric = serializer.validated_data.get("metric")
        subscription_records = (
            SubscriptionRecord.objects.active()
            .select_related("billing_plan")
            .filter(
                organization_id=organization_pk,
                customer=customer,
            )
        )
        subscription_filters = {
            x["property_name"]: x["value"]
            for x in serializer.validated_data.get("subscription_filters", [])
        }
        for key, value in subscription_filters.items():
            subscription_records = subscription_records.filter(
                subscription_filters__contains=[[key, value]]
            )
        metrics = []
        subscription_records = subscription_records.prefetch_related(
            "billing_plan__plan_components",
            "billing_plan__plan_components__billable_metric",
            "billing_plan__plan_components__tiers",
        )
        for sr in subscription_records:
            subscription_filters = []
            for filter_arr in sr.subscription_filters:
                subscription_filters.append(
                    {
                        "property_name": filter_arr[0],
                        "value": filter_arr[1],
                    }
                )
            single_sub_dict = {
                "plan_id": PlanUUIDField().to_representation(
                    sr.billing_plan.plan.plan_id
                ),
                "subscription_filters": subscription_filters,
                "usage_per_component": [],
            }
            for component in sr.billing_plan.plan_components.all():
                metric = component.billable_metric
                if metric.event_name == event_name or access_metric == metric:
                    metric_name = metric.billable_metric_name
                    tiers = sorted(component.tiers.all(), key=lambda x: x.range_start)
                    free_limit = (
                        tiers[0].range_end
                        if tiers[0].type == PriceTier.PriceTierType.FREE
                        else None
                    )
                    total_limit = tiers[-1].range_end
                    current_br = sr.billing_records.filter(
                        component=component,
                        start_date__lte=now_utc(),
                        end_date__gte=now_utc(),
                    ).first()
                    current_usage = metric.get_billing_record_total_billable_usage(
                        current_br
                    )
                    unique_tup_dict = {
                        "event_name": metric.event_name,
                        "metric_name": metric_name,
                        "metric_usage": current_usage,
                        "metric_free_limit": free_limit,
                        "metric_total_limit": total_limit,
                        "metric_id": MetricUUIDField().to_representation(
                            metric.metric_id
                        ),
                    }
                    single_sub_dict["usage_per_component"].append(unique_tup_dict)
            metrics.append(single_sub_dict)
        GetEventAccessSerializer(many=True).validate(metrics)
        return Response(
            metrics,
            status=status.HTTP_200_OK,
        )
        return Response(
            metrics,
            status=status.HTTP_200_OK,
        )
