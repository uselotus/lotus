# Create your views here.
import base64
import copy
import json
import logging
import operator
from decimal import Decimal
from functools import reduce
from itertools import chain
from typing import Optional

import posthog
import pytz
from api.serializers.model_serializers import (
    AddOnSubscriptionRecordCreateSerializer,
    AddonSubscriptionRecordFilterSerializer,
    AddOnSubscriptionRecordSerializer,
    AddonSubscriptionRecordUpdateSerializer,
    CustomerBalanceAdjustmentCreateSerializer,
    CustomerBalanceAdjustmentFilterSerializer,
    CustomerBalanceAdjustmentSerializer,
    CustomerBalanceAdjustmentUpdateSerializer,
    CustomerCreateSerializer,
    CustomerSerializer,
    EventSerializer,
    InvoiceListFilterSerializer,
    InvoiceSerializer,
    InvoiceUpdateSerializer,
    ListPlansFilterSerializer,
    ListSubscriptionRecordFilter,
    PlanSerializer,
    SubscriptionRecordCancelSerializer,
    SubscriptionRecordCreateSerializer,
    SubscriptionRecordFilterSerializer,
    SubscriptionRecordFilterSerializerDelete,
    SubscriptionRecordSerializer,
    SubscriptionRecordUpdateSerializer,
)
from api.serializers.nonmodel_serializers import (
    FeatureAccessRequestSerialzier,
    FeatureAccessResponseSerializer,
    GetCustomerEventAccessRequestSerializer,
    GetCustomerFeatureAccessRequestSerializer,
    GetEventAccessSerializer,
    GetFeatureAccessSerializer,
    GetInvoicePdfURLRequestSerializer,
    MetricAccessRequestSerializer,
    MetricAccessResponseSerializer,
)
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
from drf_spectacular.utils import extend_schema, inline_serializer
from metering_billing.auth.auth_utils import fast_api_key_validation_and_cache
from metering_billing.exceptions import (
    DuplicateCustomer,
    MethodNotAllowed,
    ServerError,
    SwitchPlanDurationMismatch,
    SwitchPlanSamePlanException,
)
from metering_billing.exceptions.exceptions import NotFoundException
from metering_billing.invoice import generate_invoice
from metering_billing.invoice_pdf import get_invoice_presigned_url
from metering_billing.kafka.producer import Producer
from metering_billing.models import (
    CategoricalFilter,
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
from metering_billing.serializers.serializer_utils import (
    AddonUUIDField,
    BalanceAdjustmentUUIDField,
    InvoiceUUIDField,
    MetricUUIDField,
    OrganizationUUIDField,
    PlanUUIDField,
)
from metering_billing.utils import (
    calculate_end_date,
    convert_to_datetime,
    date_as_max_dt,
    now_utc,
)
from metering_billing.utils.enums import (
    CATEGORICAL_FILTER_OPERATORS,
    CUSTOMER_BALANCE_ADJUSTMENT_STATUS,
    FLAT_FEE_BEHAVIOR,
    INVOICING_BEHAVIOR,
    METRIC_STATUS,
    ORGANIZATION_SETTING_NAMES,
    PLAN_STATUS,
    PLAN_VERSION_STATUS,
    SUBSCRIPTION_STATUS,
    USAGE_BEHAVIOR,
    USAGE_BILLING_BEHAVIOR,
    USAGE_BILLING_FREQUENCY,
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

POSTHOG_PERSON = settings.POSTHOG_PERSON
SVIX_CONNECTOR = settings.SVIX_CONNECTOR


logger = logging.getLogger("django.server")


class PermissionPolicyMixin:
    def check_permissions(self, request):
        try:
            # This line is heavily inspired from `APIView.dispatch`.
            # It returns the method associated with an endpoint.
            handler = getattr(self, request.method.lower())
        except AttributeError:
            handler = None

        try:
            if (
                handler
                and self.permission_classes_per_method
                and self.permission_classes_per_method.get(handler.__name__)
            ):
                self.permission_classes = self.permission_classes_per_method.get(
                    handler.__name__
                )
        except Exception:
            pass

        super().check_permissions(request)


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
                    "filters",
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
                            "associated_recurring_charge",
                            "associated_plan_component",
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
                "invoices__cost_due",
                filter=Q(invoices__payment_status=Invoice.PaymentStatus.UNPAID),
                output_field=DecimalField(),
            )
        )
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return CustomerCreateSerializer
        return CustomerSerializer

    @extend_schema(responses=CustomerSerializer)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        customer_data = CustomerSerializer(instance).data
        return Response(customer_data, status=status.HTTP_201_CREATED)

    # @extend_schema(
    #     request=inline_serializer(
    #         name="CustomerBatchCreateRequest",
    #         fields={
    #             "customers": CustomerCreateSerializer(many=True),
    #             "behavior_on_existing": serializers.ChoiceField(
    #                 choices=["merge", "ignore", "overwrite"],
    #                 help_text="Determines what to do if a customer with the same email or customer_id already exists. Ignore skips, merge merges the existing customer with the new customer, and overwrite overwrites the existing customer with the new customer.",
    #             ),
    #         },
    #     ),
    #     responses={
    #         201: inline_serializer(
    #             name="CustomerBatchCreateSuccess",
    #             fields={
    #                 "success": serializers.ChoiceField(choices=["all", "some"]),
    #                 "failed_customers": serializers.DictField(
    #                     required=False,
    #                     help_text="Returns the customers that failed to be created, if any, in the same format as the request.",
    #                 ),
    #             },
    #         ),
    #         400: inline_serializer(
    #             name="CustomerBatchCreateFailure",
    #             fields={
    #                 "success": serializers.ChoiceField(choices=["none"]),
    #                 "failed_customers": serializers.DictField(
    #                     help_text="Returns the customers that failed to be created in the same format as the request."
    #                 ),
    #             },
    #         ),
    #     },
    # )
    # @action(detail=False, methods=["post"])
    # def batch(self, request, format=None):
    #     organization = request.organization
    #     serializer = CustomerCreateSerializer(
    #         data=request.data["customers"],
    #         many=True,
    #         context={"organization": organization},
    #     )
    #     serializer.is_valid(raise_exception=True)
    #     failed_customers = {}
    #     behavior = request.data.get("behavior_on_existing", "merge")
    #     for customer in serializer.validated_data:
    #         try:
    #             match = Customer.objects.filter(
    #                 Q(email=customer["email"]) | Q(customer_id=customer["customer_id"]),
    #                 organization=organization,
    #             )
    #             if match.exists():
    #                 match = match.first()
    #                 if behavior == "ignore":
    #                     pass
    #                 else:
    #                     if "customer_id" in customer:
    #                         non_unique_id = Customer.objects.filter(
    #                             ~Q(pk=match.pk), customer_id=customer["customer_id"]
    #                         ).exists()
    #                         if non_unique_id:
    #                             failed_customers[
    #                                 customer["customer_id"]
    #                             ] = "customer_id already exists"
    #                             continue
    #                     CustomerUpdateSerializer().update(
    #                         match, customer, behavior=behavior
    #                     )
    #             else:
    #                 customer["organization"] = organization
    #                 CustomerCreateSerializer().create(customer)
    #         except Exception as e:
    #             identifier = customer.get("customer_id", customer.get("email"))
    #             failed_customers[identifier] = str(e)

    #     if len(failed_customers) == 0 or len(failed_customers) < len(
    #         serializer.validated_data
    #     ):
    #         return Response(
    #             {
    #                 "success": "all" if len(failed_customers) == 0 else "some",
    #                 "failed_customers": failed_customers,
    #             },
    #             status=status.HTTP_201_CREATED,
    #         )
    #     return Response(
    #         {
    #             "success": "none",
    #             "failed_customers": failed_customers,
    #         },
    #         status=status.HTTP_400_BAD_REQUEST,
    #     )

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
        return response


class PlanViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    serializer_class = PlanSerializer
    lookup_field = "plan_id"
    http_method_names = ["get", "head"]
    queryset = Plan.objects.all().order_by(
        F("created_on").desc(nulls_last=False), F("plan_name")
    )

    def get_object(self):
        string_uuid = str(self.kwargs[self.lookup_field])
        if "plan_" in string_uuid:
            uuid = PlanUUIDField().to_internal_value(string_uuid)
        else:
            uuid = AddonUUIDField().to_internal_value(string_uuid)
        self.kwargs[self.lookup_field] = uuid
        return super().get_object()

    def get_queryset(self):
        from metering_billing.models import PlanVersion

        now = now_utc()
        organization = self.request.organization
        qs = (
            Plan.objects.all()
            .order_by(F("created_on").desc(nulls_last=False), F("plan_name"))
            .filter(organization=organization, status=PLAN_STATUS.ACTIVE)
        )
        # first go for the ones that are one away (FK) and not nested
        qs = qs.select_related(
            "organization",
            "target_customer",
            "created_by",
            "parent_plan",
            "display_version",
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
        active_subscriptions_subquery = SubscriptionRecord.objects.filter(
            billing_plan=OuterRef("pk"),
            start_date__lte=now,
            end_date__gte=now,
        ).annotate(active_subscriptions=Count("*"))
        qs = qs.prefetch_related(
            Prefetch(
                "versions",
                queryset=PlanVersion.objects.filter(
                    ~Q(status=PLAN_VERSION_STATUS.ARCHIVED),
                    organization=organization,
                )
                .annotate(
                    active_subscriptions=Coalesce(
                        Subquery(
                            active_subscriptions_subquery.values(
                                "active_subscriptions"
                            )[:1]
                        ),
                        Value(0),
                    )
                )
                .select_related("price_adjustment", "created_by", "pricing_unit")
                .prefetch_related(
                    "usage_alerts",
                    "features",
                )
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
                .order_by("version"),
                to_attr="versions_prefetched",
            ),
        )

        plan_filter_serializer = ListPlansFilterSerializer(
            data=self.request.query_params
        )

        if not plan_filter_serializer.is_valid():
            return qs

        include_tags = plan_filter_serializer.validated_data.get("include_tags")
        include_tags_all = plan_filter_serializer.validated_data.get("include_tags_all")
        exclude_tags = plan_filter_serializer.validated_data.get("exclude_tags")

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
        parameters=[ListPlansFilterSerializer],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request)


class SubscriptionViewSet(
    PermissionPolicyMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    http_method_names = [
        "get",
        "head",
        "post",
    ]
    queryset = SubscriptionRecord.objects.all()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        organization = self.request.organization
        context.update({"organization": organization})
        return context

    def get_serializer_class(self):
        if self.action == "edit":
            return SubscriptionRecordUpdateSerializer
        elif self.action == "cancel" or self.action == "cancel_addon":
            return SubscriptionRecordCancelSerializer
        elif self.action == "add":
            return SubscriptionRecordCreateSerializer
        elif self.action == "attach_addon":
            return AddOnSubscriptionRecordCreateSerializer
        elif self.action == "update_addon":
            return AddonSubscriptionRecordUpdateSerializer
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
        if self.action in ["cancel_addon", "update_addon"]:
            qs = SubscriptionRecord.addon_objects.all()
        else:
            qs = SubscriptionRecord.base_objects.all()
        now = now_utc()
        organization = self.request.organization
        qs = qs.filter(organization=organization)
        context = self.get_serializer_context()
        context["organization"] = organization
        if self.action in ["list", "edit", "cancel"]:
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
            elif self.action == "cancel":
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
                filters = []
                for filter in serializer.validated_data["subscription_filters"]:
                    m2m, _ = CategoricalFilter.objects.get_or_create(
                        organization=organization,
                        property_name=filter["property_name"],
                        comparison_value=[filter["value"]],
                        operator=CATEGORICAL_FILTER_OPERATORS.ISIN,
                    )
                    filters.append(m2m)
                query = reduce(
                    lambda acc, filter: acc & Q(filters=filter), filters, Q()
                )
                qs = qs.filter(query)
        elif self.action in ["cancel_addon", "update_addon"]:
            subscription_filters = self.request.query_params.getlist(
                "subscription_filters[]"
            )
            subscription_filters = [json.loads(x) for x in subscription_filters]
            dict_params = self.request.query_params.dict()
            data = {
                "subscription_filters": subscription_filters,
                "attached_customer_id": dict_params.get("attached_customer_id"),
                "attached_plan_id": dict_params.get("attached_plan_id"),
                "addon_id": dict_params.get("addon_id"),
            }
            serializer = AddonSubscriptionRecordFilterSerializer(
                data=data, context=context
            )
            serializer.is_valid(raise_exception=True)

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
                filters = []
                for filter in serializer.validated_data["subscription_filters"]:
                    m2m, _ = CategoricalFilter.objects.get_or_create(
                        organization=organization,
                        property_name=filter["property_name"],
                        comparison_value=[filter["value"]],
                        operator=CATEGORICAL_FILTER_OPERATORS.ISIN,
                    )
                    filters.append(m2m)
                query = reduce(
                    lambda acc, filter: acc & Q(filters=filter), filters, Q()
                )
                qs = qs.filter(query)
        return qs

    @extend_schema(
        parameters=[ListSubscriptionRecordFilter],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request)

    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed(
            "Cannot use the create method on the subscription endpoint. Please use the /subscriptions/add endpoint to attach a plan and create a subscription."
        )

    # ad hoc methods
    @extend_schema(responses=SubscriptionRecordSerializer)
    @action(detail=False, methods=["post"])
    def add(self, request, *args, **kwargs):
        now = now_utc()
        # run checks to make sure it's valid
        organization = self.request.organization
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # make sure subscription filters are valid
        subscription_filters = serializer.validated_data.get("subscription_filters", [])
        sf_setting = organization.settings.get(
            setting_name=ORGANIZATION_SETTING_NAMES.SUBSCRIPTION_FILTER_KEYS
        )
        for sf in subscription_filters:
            if sf["property_name"] not in sf_setting.setting_values:
                raise ValidationError(
                    "Invalid subscription filter. Please check your subscription filters setting."
                )
        # check to see if subscription exists
        duration = serializer.validated_data["billing_plan"].plan.plan_duration
        billing_freq = serializer.validated_data["billing_plan"].usage_billing_frequency
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
        if billing_freq in [
            USAGE_BILLING_FREQUENCY.MONTHLY,
            USAGE_BILLING_FREQUENCY.QUARTERLY,
        ]:
            found = False
            i = 0
            num_months = 1 if billing_freq == USAGE_BILLING_FREQUENCY.MONTHLY else 3
            while not found:
                tentative_nbd = date_as_max_dt(
                    start_date + relativedelta(months=i, day=day_anchor, days=-1)
                )
                if tentative_nbd <= start_date:
                    i += 1
                    continue
                elif tentative_nbd > end_date:
                    tentative_nbd = end_date
                    break
                months_btwn = relativedelta(end_date, tentative_nbd).months
                if months_btwn % num_months == 0:
                    found = True
                else:
                    i += 1
            serializer.validated_data[
                "next_billing_date"
            ] = tentative_nbd  # end_date - i * relativedelta(months=num_months)
        subscription_record = serializer.save(
            organization=organization,
        )

        # now we can actually create the subscription record
        response = SubscriptionRecordSerializer(subscription_record).data
        return Response(
            response,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        parameters=[
            SubscriptionRecordFilterSerializerDelete,
        ],
        responses={200: SubscriptionRecordSerializer(many=True)},
    )
    @action(detail=False, methods=["post"])
    def cancel(self, request, *args, **kwargs):
        qs = self.get_queryset()
        original_qs = list(copy.copy(qs).values_list("pk", flat=True))
        organization = self.request.organization
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        flat_fee_behavior = serializer.validated_data["flat_fee_behavior"]
        usage_behavior = serializer.validated_data["usage_behavior"]
        invoicing_behavior = serializer.validated_data["invoicing_behavior"]
        now = now_utc()
        qs_pks = list(qs.values_list("pk", flat=True))
        qs.update(
            flat_fee_behavior=flat_fee_behavior,
            invoice_usage_charges=usage_behavior == USAGE_BILLING_BEHAVIOR.BILL_FULL,
            auto_renew=False,
            end_date=now,
            fully_billed=invoicing_behavior == INVOICING_BEHAVIOR.INVOICE_NOW,
        )
        qs = SubscriptionRecord.objects.filter(pk__in=qs_pks, organization=organization)
        customer_ids = qs.values_list("customer", flat=True).distinct()
        customer_set = Customer.objects.filter(
            id__in=customer_ids, organization=organization
        )
        if invoicing_behavior == INVOICING_BEHAVIOR.INVOICE_NOW:
            for customer in customer_set:
                generate_invoice(qs.filter(customer=customer))

        return_qs = SubscriptionRecord.base_objects.filter(
            pk__in=original_qs, organization=organization
        )
        ret = SubscriptionRecordSerializer(return_qs, many=True).data
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
        replace_billing_plan = serializer.validated_data.get("billing_plan")
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
                billing_plan__plan__addon_spec__isnull=True
            )  # no addons in replace
            now = now_utc()
            keep_separate = usage_behavior == USAGE_BEHAVIOR.KEEP_SEPARATE
            replace_plan_metrics = {
                pc.billable_metric for pc in replace_billing_plan.plan_components.all()
            }
            for subscription_record in qs:
                original_sub_record_plan_metrics = {
                    pc.billable_metric
                    for sub_rec in subscription_record.addon_subscription_records.all()
                    for pc in sub_rec.billing_plan.plan_components.all()
                }
                if replace_plan_metrics.intersection(original_sub_record_plan_metrics):
                    logger.debug(
                        "Cannot switch to a plan with overlapping metrics with the current addons."
                    )
                    original_qs.remove(subscription_record.pk)
                    continue
                sr = SubscriptionRecord.objects.create(
                    organization=subscription_record.organization,
                    customer=subscription_record.customer,
                    billing_plan=replace_billing_plan,
                    start_date=now,
                    end_date=subscription_record.end_date,
                    next_billing_date=subscription_record.next_billing_date,
                    last_billing_date=subscription_record.last_billing_date,
                    usage_start_date=now
                    if keep_separate
                    else subscription_record.usage_start_date,
                    auto_renew=subscription_record.auto_renew,
                    fully_billed=False,
                    unadjusted_duration_microseconds=subscription_record.unadjusted_duration_microseconds,
                )
                for filter in subscription_record.filters.all():
                    sr.filters.add(filter)
                subscription_record.flat_fee_behavior = (
                    FLAT_FEE_BEHAVIOR.CHARGE_PRORATED
                )
                subscription_record.invoice_usage_charges = keep_separate
                subscription_record.auto_renew = False
                subscription_record.end_date = now
                subscription_record.fully_billed = (
                    billing_behavior == INVOICING_BEHAVIOR.INVOICE_NOW
                )
                subscription_record.save()
            new_qs = SubscriptionRecord.objects.filter(
                pk__in=original_qs, organization=organization
            )
            if billing_behavior == INVOICING_BEHAVIOR.INVOICE_NOW:
                generate_invoice(new_qs)
        else:
            update_dict = {}
            if turn_off_auto_renew:
                update_dict["auto_renew"] = False
            if end_date:
                update_dict["end_date"] = end_date
                update_dict["next_billing_date"] = end_date
            if len(update_dict) > 0:
                qs.update(**update_dict)

        return_qs = SubscriptionRecord.base_objects.filter(
            pk__in=original_qs, organization=organization
        )
        ret = SubscriptionRecordSerializer(return_qs, many=True).data
        return Response(ret, status=status.HTTP_200_OK)

    @extend_schema(responses=AddOnSubscriptionRecordSerializer)
    @action(detail=False, methods=["post"], url_path="addons/add")
    def attach_addon(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sr = serializer.save()
        return Response(
            AddOnSubscriptionRecordSerializer(sr).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        parameters=[AddonSubscriptionRecordFilterSerializer],
        responses=AddOnSubscriptionRecordSerializer(many=True),
    )
    @action(detail=False, methods=["post"], url_path="addons/update")
    def update_addon(self, request, *args, **kwargs):
        qs = self.get_queryset()
        organization = self.request.organization
        original_qs = list(copy.copy(qs).values_list("pk", flat=True))
        if qs.count() == 0:
            raise NotFoundException("Subscription matching the given filters not found")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        billing_behavior = serializer.validated_data.get("invoicing_behavior")
        turn_off_auto_renew = serializer.validated_data.get("turn_off_auto_renew")
        end_date = serializer.validated_data.get("end_date")
        quantity = serializer.validated_data.get("quantity")
        update_dict = {}
        if turn_off_auto_renew:
            update_dict["auto_renew"] = False
        if end_date:
            update_dict["end_date"] = end_date
            update_dict["next_billing_date"] = end_date
        if quantity:
            update_dict["quantity"] = quantity
        if len(update_dict) > 0:
            qs.update(**update_dict)
        if (
            billing_behavior == INVOICING_BEHAVIOR.INVOICE_NOW
            and "quantity" in update_dict
        ):
            new_qs = SubscriptionRecord.addon_objects.filter(
                pk__in=original_qs, organization=organization
            )
            if billing_behavior == INVOICING_BEHAVIOR.INVOICE_NOW:
                generate_invoice(new_qs)

        return_qs = SubscriptionRecord.addon_objects.filter(
            pk__in=original_qs, organization=organization
        )
        return Response(
            AddOnSubscriptionRecordSerializer(return_qs, many=True).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        parameters=[AddonSubscriptionRecordFilterSerializer],
        responses=AddOnSubscriptionRecordSerializer(many=True),
    )
    @action(detail=False, methods=["post"], url_path="addons/cancel")
    def cancel_addon(self, request, *args, **kwargs):
        qs = self.get_queryset()
        original_qs = list(copy.copy(qs).values_list("pk", flat=True))
        organization = self.request.organization
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        flat_fee_behavior = serializer.validated_data["flat_fee_behavior"]
        usage_behavior = serializer.validated_data["usage_behavior"]
        invoicing_behavior = serializer.validated_data["invoicing_behavior"]
        now = now_utc()
        qs_pks = list(qs.values_list("pk", flat=True))
        qs.update(
            flat_fee_behavior=flat_fee_behavior,
            invoice_usage_charges=usage_behavior == USAGE_BILLING_BEHAVIOR.BILL_FULL,
            auto_renew=False,
            end_date=now,
            fully_billed=invoicing_behavior == INVOICING_BEHAVIOR.INVOICE_NOW,
        )
        qs = SubscriptionRecord.addon_objects.filter(
            pk__in=qs_pks, organization=organization
        )
        customer_ids = qs.values_list("customer", flat=True).distinct()
        customer_set = Customer.objects.filter(
            id__in=customer_ids, organization=organization
        )
        if invoicing_behavior == INVOICING_BEHAVIOR.INVOICE_NOW:
            for customer in customer_set:
                generate_invoice(qs.filter(customer=customer))

        return_qs = SubscriptionRecord.addon_objects.filter(
            pk__in=original_qs, organization=organization
        )
        return Response(
            AddOnSubscriptionRecordSerializer(return_qs, many=True).data,
            status=status.HTTP_200_OK,
        )

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except Exception:
                username = None
            organization = self.request.organization
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
        string_uuid = self.kwargs[self.lookup_field]
        uuid = InvoiceUUIDField().to_internal_value(string_uuid)
        self.kwargs[self.lookup_field] = uuid
        return super().get_object()

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

    def get_serializer_class(self):
        if self.action == "partial_update":
            return InvoiceUpdateSerializer
        return InvoiceSerializer

    @extend_schema(responses=InvoiceSerializer)
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
        return response

    @extend_schema(
        parameters=[InvoiceListFilterSerializer],
    )
    def list(self, request):
        return super().list(request)


class EmptySerializer(serializers.Serializer):
    pass


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

    @extend_schema(responses=CustomerBalanceAdjustmentSerializer)
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

    @extend_schema(responses=CustomerBalanceAdjustmentSerializer)
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

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except Exception:
                username = None
            organization = self.request.organization
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
            "billing_plan__plan_components",
            "billing_plan__plan_components__billable_metric",
            "billing_plan__plan_components__tiers",
            "billing_plan__plan",
            "filters",
        )
        return_dict = {
            "customer": customer,
            "metric": metric,
            "access": False,
            "access_per_subscription": [],
        }
        for sr in subscription_records.filter(
            billing_plan__plan__addon_spec__isnull=True
        ):
            if subscription_filters_set:
                sr_filters_set = {(x.property_name, x.value) for x in sr.filters.all()}
                if not subscription_filters_set.issubset(sr_filters_set):
                    continue
            single_sr_dict = {
                "subscription": sr,
                "metric_usage": 0,
                "metric_free_limit": 0,
                "metric_total_limit": 0,
            }
            components = sr.billing_plan.plan_components.all()
            for addon in sr.addon_subscription_records.all():
                components = components | addon.billing_plan.plan_components.all()
            for component in components:
                check_metric = component.billable_metric
                if check_metric == metric:
                    tiers = sorted(component.tiers.all(), key=lambda x: x.range_start)
                    free_limit = (
                        tiers[0].range_end
                        if tiers[0].type == PriceTier.PriceTierType.FREE
                        else 0
                    )
                    total_limit = tiers[-1].range_end
                    current_usage = metric.get_subscription_record_current_usage(sr)
                    single_sr_dict["metric_usage"] = current_usage
                    single_sr_dict["metric_free_limit"] = free_limit
                    single_sr_dict["metric_total_limit"] = total_limit
                    break
            # addon_srs = sr.addon_subscription_records.all()
            # for addon_sr in addon_srs:
            #     for component in addon_sr.billing_plan.plan_components.all():
            #         check_metric = component.billable_metric
            #         if check_metric == metric:
            #             total_limit = tiers[-1].range_end
            #             current_usage = metric.get_subscription_record_current_usage(
            #                 addon_sr
            #             )
            #             if single_sr_dict["metric_total_limit"] is None:
            #                 single_sr_dict["metric_total_limit"] += total_limit
            #             elif total_limit is None:
            #                 single_sr_dict["metric_total_limit"] = None
            #             else:
            #                 single_sr_dict["metric_total_limit"] += total_limit
            #             break
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
        parameters=[FeatureAccessRequestSerialzier],
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
        serializer = FeatureAccessRequestSerialzier(
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
            "filters",
        )
        return_dict = {
            "customer": customer,
            "feature": feature,
            "access": False,
            "access_per_subscription": [],
        }
        for sr in subscription_records.filter(
            billing_plan__plan__addon_spec__isnull=True
        ):
            if subscription_filters_set:
                sr_filters_set = {(x.property_name, x.value) for x in sr.filters.all()}
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
        responses={
            200: inline_serializer(
                name="ConfirmConnected",
                fields={
                    "organization_id": serializers.CharField(),
                },
            ),
        },
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


class GetInvoicePdfURL(APIView):
    permission_classes = [IsAuthenticated | HasUserAPIKey]

    @extend_schema(
        parameters=[GetInvoicePdfURLRequestSerializer],
        responses={
            200: inline_serializer(
                name="GetInvoicePdfURLResponse",
                fields={
                    "url": serializers.URLField(),
                },
            ),
        },
    )
    def get(self, request, format=None):
        organization = request.organization
        serializer = GetInvoicePdfURLRequestSerializer(
            data=request.query_params, context={"organization": organization}
        )
        serializer.is_valid(raise_exception=True)
        invoice = serializer.validated_data["invoice"]
        url = get_invoice_presigned_url(invoice).get("url")
        return Response({"url": url}, status=status.HTTP_200_OK)


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
            events = Event.objects.filter(
                organization=organization,
                time_created__gte=now_minus_lookback,
                idempotency_id__in=idem_batch,
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


logger = logging.getLogger("django.server")
kafka_producer = Producer()


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
        try:
            transformed_event = ingest_event(data, customer_id, organization_pk)
            stream_events = {
                "events": [transformed_event],
                "organization_id": organization_pk,
            }
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
        result, success = fast_api_key_validation_and_cache(request)
        if not success:
            return result
        else:
            organization_pk = result
        serializer = GetCustomerFeatureAccessRequestSerializer(
            data=request.query_params, context={"organization_pk": organization_pk}
        )
        serializer.is_valid(raise_exception=True)
        # try:
        #     username = self.request.user.username
        # except Exception as e:
        #     username = None
        # posthog.capture(
        #     POSTHOG_PERSON
        #     if POSTHOG_PERSON
        #     else (username if username else organization.organization_name + " (Unknown)"),
        #     event="get_access",
        #     properties={"organization": organization.organization_name},
        # )
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
            key = f"properties__{key}"
            subscriptions = subscriptions.filter(**{key: value})
        features = []
        subscriptions = subscriptions.prefetch_related("billing_plan__features")
        for sub in subscriptions:
            subscription_filters = []
            for filter in sub.filters.all():
                subscription_filters.append(
                    {
                        "property_name": filter.property_name,
                        "value": filter.comparison_value[0],
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
        result, success = fast_api_key_validation_and_cache(request)
        if not success:
            return result
        else:
            organization_pk = result
        serializer = GetCustomerEventAccessRequestSerializer(
            data=request.query_params, context={"organization_pk": organization_pk}
        )
        serializer.is_valid(raise_exception=True)
        # try:
        #     username = self.request.user.username
        # except Exception as e:
        #     username = None
        # posthog.capture(
        #     POSTHOG_PERSON
        #     if POSTHOG_PERSON
        #     else (username if username else organization.organization_name + " (Unknown)"),
        #     event="get_access",
        #     properties={"organization": organization.organization_name},
        # )
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
            key = f"properties__{key}"
            subscription_records = subscription_records.filter(**{key: value})
        metrics = []
        subscription_records = subscription_records.prefetch_related(
            "billing_plan__plan_components",
            "billing_plan__plan_components__billable_metric",
            "billing_plan__plan_components__tiers",
            "filters",
        )
        for sr in subscription_records:
            subscription_filters = []
            for filter in sr.filters.all():
                subscription_filters.append(
                    {
                        "property_name": filter.property_name,
                        "value": filter.comparison_value[0],
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
                    current_usage = metric.get_subscription_record_current_usage(sr)
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
