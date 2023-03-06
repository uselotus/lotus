# import lotus_python
import logging

import posthog
import sentry_sdk
from actstream.models import Action
from django.conf import settings
from django.core.cache import cache
from django.core.validators import MinValueValidator
from django.db.utils import IntegrityError
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiCallback,
    OpenApiParameter,
    extend_schema,
    inline_serializer,
)
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

import api.views as api_views
from api.serializers.nonmodel_serializers import (
    AddFeatureSerializer,
    AddFeatureToAddOnSerializer,
    AddFeatureToPlanSerializer,
    ChangeActiveDatesSerializer,
)
from api.serializers.webhook_serializers import (
    CustomerCreatedSerializer,
    InvoiceCreatedSerializer,
    InvoicePaidSerializer,
    InvoicePastDueSerializer,
    UsageAlertTriggeredSerializer,
)
from metering_billing.exceptions import (
    DuplicateMetric,
    DuplicateWebhookEndpoint,
    InvalidOperation,
    MethodNotAllowed,
    ServerError,
)
from metering_billing.models import (
    APIToken,
    Backtest,
    Event,
    ExternalPlanLink,
    Feature,
    Metric,
    Organization,
    OrganizationSetting,
    Plan,
    PlanVersion,
    PricingUnit,
    Product,
    SubscriptionRecord,
    UsageAlert,
    User,
    WebhookEndpoint,
)
from metering_billing.payment_processors import PAYMENT_PROCESSOR_MAP
from metering_billing.permissions import ValidOrganization
from metering_billing.serializers.backtest_serializers import (
    BacktestCreateSerializer,
    BacktestDetailSerializer,
    BacktestSummarySerializer,
    BacktestUUIDField,
)
from metering_billing.serializers.model_serializers import (
    ActionSerializer,
    AddOnCreateSerializer,
    AddOnDetailSerializer,
    AddOnUpdateSerializer,
    AddOnVersionCreateSerializer,
    AddOnVersionDetailSerializer,
    AddOnVersionUpdateSerializer,
    APITokenSerializer,
    CustomerDetailSerializer,
    CustomerSummarySerializer,
    CustomerUpdateSerializer,
    CustomerWithRevenueSerializer,
    EventDetailSerializer,
    ExternalPlanLinkSerializer,
    FeatureCreateSerializer,
    FeatureDetailSerializer,
    InvoiceDetailSerializer,
    MetricCreateSerializer,
    MetricDetailSerializer,
    MetricUpdateSerializer,
    OrganizationCreateSerializer,
    OrganizationSerializer,
    OrganizationSettingSerializer,
    OrganizationSettingUpdateSerializer,
    OrganizationUpdateSerializer,
    PlanCreateSerializer,
    PlanDetailSerializer,
    PlanUpdateSerializer,
    PlanVersionCreateSerializer,
    PlanVersionDetailSerializer,
    PlanVersionHistoricalSubscriptionSerializer,
    PlanVersionUpdateSerializer,
    PricingUnitDetailSerializer,
    ProductSerializer,
    TagSerializer,
    UsageAlertCreateSerializer,
    UsageAlertSerializer,
    UserSerializer,
    WebhookEndpointSerializer,
)
from metering_billing.serializers.request_serializers import (
    MakeReplaceWithSerializer,
    OrganizationSettingFilterSerializer,
    PlansSetReplaceWithForVersionNumberSerializer,
    PlansSetTransitionToForVersionNumberSerializer,
    SetReplaceWithSerializer,
    TargetCustomersSerializer,
)
from metering_billing.serializers.serializer_utils import (
    AddOnUUIDField,
    AddOnVersionUUIDField,
    MetricUUIDField,
    OrganizationSettingUUIDField,
    OrganizationUUIDField,
    PlanUUIDField,
    PlanVersionUUIDField,
    UsageAlertUUIDField,
    WebhookEndpointUUIDField,
)
from metering_billing.tasks import run_backtest
from metering_billing.utils import make_all_decimals_floats, now_utc
from metering_billing.utils.enums import (
    METRIC_STATUS,
    PAYMENT_PROCESSORS,
    WEBHOOK_TRIGGER_EVENTS,
)

POSTHOG_PERSON = settings.POSTHOG_PERSON
SVIX_CONNECTOR = settings.SVIX_CONNECTOR
logger = logging.getLogger("django.server")


class CustomPagination(CursorPagination):
    def get_paginated_response(self, data):
        if self.get_next_link():
            next_link = self.get_next_link()
            next_cursor = next_link[
                next_link.index(f"{self.cursor_query_param}=")
                + len(f"{self.cursor_query_param}=") :
            ]
        else:
            next_cursor = None
        if self.get_previous_link():
            previous_link = self.get_previous_link()
            previous_cursor = previous_link[
                previous_link.index(f"{self.cursor_query_param}=")
                + len(f"{self.cursor_query_param}=") :
            ]
        else:
            previous_cursor = None
        return Response(
            {
                "next": next_cursor,
                "previous": previous_cursor,
                "results": data,
            }
        )


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


class APITokenViewSet(
    PermissionPolicyMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    API endpoint that allows API Tokens to be viewed or edited.
    """

    serializer_class = APITokenSerializer
    permission_classes = [IsAuthenticated & ValidOrganization]
    http_method_names = ["get", "post", "head", "delete"]
    lookup_field = "prefix"
    queryset = APIToken.objects.all()

    def get_queryset(self):
        organization = self.request.organization
        return APIToken.objects.filter(organization=organization)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        organization = self.request.organization
        context.update({"organization": organization})
        return context

    def perform_create(self, serializer):
        organization = self.request.organization
        api_key, key = serializer.save(organization=organization)
        return api_key, key

    @extend_schema(
        request=APITokenSerializer,
        responses=inline_serializer(
            "APITokenCreateResponse",
            {"api_key": APITokenSerializer(), "key": serializers.CharField()},
        ),
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        api_key, key = self.perform_create(serializer)
        expiry_date = api_key.expiry_date
        timeout = (
            60 * 60 * 24
            if expiry_date is None
            else (expiry_date - now_utc()).total_seconds()
        )
        cache.set(key, api_key.organization.pk, timeout)
        headers = self.get_success_headers(serializer.data)
        return Response(
            {"api_key": serializer.data, "key": key},
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def perform_destroy(self, instance):
        try:
            cache.delete_pattern(f"{instance.prefix}*")
        except Exception as e:
            logger.error("Error deleting cache using delete pattern")
            sentry_sdk.capture_exception(e)
            keys_to_delete = []
            for key in cache.keys(f"{instance.prefix}*"):
                keys_to_delete.append(key)
            cache.delete_many(keys_to_delete)
        return super().perform_destroy(instance)

    @extend_schema(
        request=None,
        responses=inline_serializer(
            "APITokenRollResponse",
            {"api_key": APITokenSerializer(), "key": serializers.CharField()},
        ),
    )
    @action(detail=True, methods=["post"])
    def roll(self, request, prefix):
        api_token = self.get_object()
        data = {
            "name": api_token.name,
            "expiry_date": api_token.expiry_date,
        }
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        api_key, key = self.perform_create(serializer)
        api_key.created = api_token.created
        api_key.save()
        self.perform_destroy(api_token)
        expiry_date = api_key.expiry_date
        timeout = (
            60 * 60 * 24
            if expiry_date is None
            else (expiry_date - now_utc()).total_seconds()
        )
        cache.set(api_key.prefix, api_key.organization.pk, timeout)
        headers = self.get_success_headers(serializer.data)
        return Response(
            {"api_key": serializer.data, "key": key},
            status=status.HTTP_201_CREATED,
            headers=headers,
        )


class EmptySerializer(serializers.Serializer):
    pass


class WebhookViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    API endpoint that allows alerts to be viewed or edited.
    """

    serializer_class = WebhookEndpointSerializer
    permission_classes = [IsAuthenticated & ValidOrganization]
    http_method_names = ["get", "post", "head", "delete"]
    lookup_field = "webhook_endpoint_id"
    permission_classes_per_method = {
        "create": [IsAuthenticated & ValidOrganization],
        "list": [IsAuthenticated & ValidOrganization],
        "retrieve": [IsAuthenticated & ValidOrganization],
        "destroy": [IsAuthenticated & ValidOrganization],
        "partial_update": [IsAuthenticated & ValidOrganization],
    }
    queryset = WebhookEndpoint.objects.all()
    serializer_class = WebhookEndpointSerializer

    def get_serializer_class(self):
        if self.action == "destroy":
            return EmptySerializer
        return WebhookEndpointSerializer

    @extend_schema(
        callbacks=[
            OpenApiCallback(
                WEBHOOK_TRIGGER_EVENTS.INVOICE_CREATED.value,
                "{$request.body#/webhook_url}",
                extend_schema(
                    description="Invoice created webhook",
                    responses={200: InvoiceCreatedSerializer},
                ),
            ),
            OpenApiCallback(
                WEBHOOK_TRIGGER_EVENTS.INVOICE_PAID.value,
                "{$request.body#/webhook_url}",
                extend_schema(
                    description="Invoice paid webhook",
                    responses={200: InvoicePaidSerializer},
                ),
            ),
            OpenApiCallback(
                WEBHOOK_TRIGGER_EVENTS.USAGE_ALERT_TRIGGERED.value,
                "{$request.body#/webhook_url}",
                extend_schema(
                    description="Usage alert triggered webhook",
                    responses={200: UsageAlertTriggeredSerializer},
                ),
            ),
            OpenApiCallback(
                WEBHOOK_TRIGGER_EVENTS.CUSTOMER_CREATED.value,
                "{$request.body#/webhook_url}",
                extend_schema(
                    description="Customer created webhook",
                    responses={200: CustomerCreatedSerializer},
                ),
            ),
            OpenApiCallback(
                WEBHOOK_TRIGGER_EVENTS.INVOICE_PAST_DUE.value,
                "{$request.body#/webhook_url}",
                extend_schema(
                    description="Invoice Past Due webhook",
                    responses={200: InvoicePastDueSerializer},
                ),
            ),
        ]
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def get_object(self):
        string_uuid = self.kwargs[self.lookup_field]
        uuid = WebhookEndpointUUIDField().to_internal_value(string_uuid)
        self.kwargs[self.lookup_field] = uuid
        return super().get_object()

    def get_queryset(self):
        organization = self.request.organization
        return WebhookEndpoint.objects.filter(organization=organization)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        organization = self.request.organization
        context.update({"organization": organization})
        return context

    def perform_create(self, serializer):
        try:
            serializer.save(organization=self.request.organization)
        except ValueError as e:
            raise ServerError(e)
        except IntegrityError:
            raise DuplicateWebhookEndpoint("Webhook endpoint already exists")

    def perform_destroy(self, instance):
        if SVIX_CONNECTOR is not None:
            svix = SVIX_CONNECTOR
            try:
                svix.endpoint.delete(
                    instance.organization.organization_id.hex,
                    instance.webhook_endpoint_id.hex,
                )
            except Exception:
                pass
        instance.delete()

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
                event=f"{self.action}_webhook",
                properties={"organization": organization.organization_name},
            )
        return response


class CursorSetPagination(CustomPagination):
    page_size = 10
    page_size_query_param = "page_size"
    ordering = "-time_created"
    cursor_query_param = "c"


class EventViewSet(
    PermissionPolicyMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):
    """
    API endpoint that allows events to be viewed.
    """

    queryset = Event.objects.all()
    serializer_class = EventDetailSerializer
    pagination_class = CursorSetPagination
    permission_classes = [IsAuthenticated & ValidOrganization]
    http_method_names = [
        "get",
        "head",
    ]

    def get_queryset(self):
        now = now_utc()
        organization = self.request.organization
        return (
            super()
            .get_queryset()
            .filter(organization=organization, time_created__lt=now)
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        organization = self.request.organization
        context.update({"organization": organization})
        return context


class UserViewSet(
    PermissionPolicyMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated & ValidOrganization]
    http_method_names = ["get", "post", "head"]

    def get_queryset(self):
        organization = self.request.organization
        return User.objects.filter(organization=organization)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        organization = self.request.organization
        context.update({"organization": organization})
        return context

    def perform_create(self, serializer):
        serializer.save(organization=self.request.organization)


class CustomerViewSet(api_views.CustomerViewSet):
    http_method_names = ["get", "post", "head", "patch"]

    def get_serializer_class(self):
        if self.action == "partial_update":
            return CustomerUpdateSerializer
        elif self.action == "summary":
            return CustomerSummarySerializer
        return super().get_serializer_class()

    @extend_schema(responses=PlanVersionDetailSerializer)
    def update(self, request, *args, **kwargs):
        customer = self.get_object()
        serializer = self.get_serializer(customer, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        if getattr(customer, "_prefetched_objects_cache", None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            customer._prefetched_objects_cache = {}

        return Response(
            CustomerDetailSerializer(
                customer, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(request=None, responses=CustomerSummarySerializer)
    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        """
        Get the current settings for the organization.
        """
        customers = self.get_queryset()
        serializer = CustomerSummarySerializer(customers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(request=None, responses=CustomerWithRevenueSerializer)
    @action(detail=False, methods=["get"], url_path="totals")
    def totals(self, request, pk=None):
        """
        Get the current settings for the organization.
        """
        customers = self.get_queryset()
        cust = CustomerWithRevenueSerializer(customers, many=True).data
        cust = make_all_decimals_floats(cust)
        return Response(cust, status=status.HTTP_200_OK)


class MetricViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    http_method_names = ["get", "post", "head", "patch"]
    lookup_field = "metric_id"
    permission_classes_per_method = {
        "create": [IsAuthenticated & ValidOrganization],
        "partial_update": [IsAuthenticated & ValidOrganization],
    }
    queryset = Metric.objects.all()

    def get_object(self):
        string_uuid = self.kwargs[self.lookup_field]
        uuid = MetricUUIDField().to_internal_value(string_uuid)
        self.kwargs[self.lookup_field] = uuid
        return super().get_object()

    def get_queryset(self):
        organization = self.request.organization
        return Metric.objects.filter(
            organization=organization, status=METRIC_STATUS.ACTIVE
        )

    def get_serializer_class(self):
        if self.action == "partial_update":
            return MetricUpdateSerializer
        elif self.action == "create":
            return MetricCreateSerializer
        return MetricDetailSerializer

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
                event=f"{self.action}_metric",
                properties={"organization": organization.organization_name},
            )
        return response

    @extend_schema(responses=MetricDetailSerializer)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        metric_data = MetricDetailSerializer(instance).data
        return Response(metric_data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        try:
            instance = serializer.save(organization=self.request.organization)
            return instance
        except IntegrityError as e:
            cause = e.__cause__
            if "unique_org_billable_metric_name" in str(cause):
                error_message = "A billable metric with the same name already exists for this organization. Please choose a different name."
                raise DuplicateMetric(error_message)
            elif "uq_metric_w_null__" in str(cause):
                error_message = "A metric with the same name, type, and other fields already exists for this organization. Please choose a different name or type, or change the other fields."
                raise DuplicateMetric(error_message)
            else:
                raise ServerError(f"Unknown error occurred while creating metric: {e}")


class FeatureViewSet(
    PermissionPolicyMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = FeatureDetailSerializer
    http_method_names = ["get", "post", "head"]
    permission_classes_per_method = {
        "create": [IsAuthenticated & ValidOrganization],
        "destroy": [IsAuthenticated & ValidOrganization],
    }
    queryset = Feature.objects.all()

    def get_serializer_class(self):
        if self.action == "create":
            return FeatureCreateSerializer
        return FeatureDetailSerializer

    def get_queryset(self):
        organization = self.request.organization
        objs = Feature.objects.filter(organization=organization)
        return objs

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
                event=f"{self.action}_feature",
                properties={"organization": organization.organization_name},
            )
        return response

    @extend_schema(responses=FeatureDetailSerializer)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        feature_data = FeatureDetailSerializer(instance).data
        return Response(feature_data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        return serializer.save(organization=self.request.organization)


class PlanVersionViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    serializer_class = PlanVersionDetailSerializer
    lookup_field = "version_id"
    http_method_names = [
        "post",
        "head",
        "patch",
    ]
    permission_classes_per_method = {
        "create": [IsAuthenticated & ValidOrganization],
        "partial_update": [IsAuthenticated & ValidOrganization],
    }
    queryset = PlanVersion.plan_versions.all()

    def get_object(self):
        string_uuid = self.kwargs[self.lookup_field]
        uuid = PlanVersionUUIDField().to_internal_value(string_uuid)
        self.kwargs[self.lookup_field] = uuid
        return super().get_object()

    def get_serializer_class(self):
        if self.action == "partial_update":
            return PlanVersionUpdateSerializer
        elif self.action == "create":
            return PlanVersionCreateSerializer
        return PlanVersionDetailSerializer

    def get_queryset(self):
        organization = self.request.organization
        qs = PlanVersion.plan_versions.filter(
            organization=organization,
        )
        return qs

    def get_serializer_context(self):
        context = super().get_serializer_context()
        organization = self.request.organization
        if self.request.user.is_authenticated:
            user = self.request.user
        else:
            user = None
        context.update({"organization": organization, "user": user})
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
                event=f"{self.action}_plan_version",
                properties={"organization": organization.organization_name},
            )
        return response

    @extend_schema(responses=PlanVersionDetailSerializer)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        plan_version_data = PlanVersionDetailSerializer(instance).data
        return Response(plan_version_data, status=status.HTTP_201_CREATED)

    @extend_schema(responses=PlanVersionDetailSerializer)
    def update(self, request, *args, **kwargs):
        pv = self.get_object()
        serializer = self.get_serializer(pv, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        if getattr(pv, "_prefetched_objects_cache", None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            pv._prefetched_objects_cache = {}

        return Response(
            PlanVersionDetailSerializer(pv, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            user = self.request.user
        else:
            user = None
        instance = serializer.save(
            organization=self.request.organization, created_by=user
        )
        # if user:
        #     action.send(
        #         user,
        #         verb="created",
        #         action_object=instance,
        #         target=instance.plan,
        #     )
        return instance

    @extend_schema(
        request=TargetCustomersSerializer,
        responses=inline_serializer(
            "AddTargetCustomerResponse",
            fields={
                "success": serializers.BooleanField(),
                "message": serializers.CharField(),
            },
        ),
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="target_customers/add",
        url_name="add_target_customer",
    )
    def add_target_customer(self, request, *args, **kwargs):
        plan_version = self.get_object()
        organization = self.request.organization
        serializer = TargetCustomersSerializer(
            data=request.data, context={"organization": organization}
        )
        serializer.is_valid(raise_exception=True)
        customers = serializer.validated_data["customers"]
        ct_before = plan_version.target_customers.all().count()
        if ct_before == 0 and plan_version.is_custom is False:
            # check there's no subscriptions where this plan version is active
            # and the customer is not in the target customers list
            current_subscriptions = plan_version.subscription_records.active().exclude(
                customer__in=customers
            )
            if current_subscriptions.exists():
                return Response(
                    {
                        "success": False,
                        "message": "Cannot add target customers to this plan version. There are active subscriptions for this plan version whose customers are not in the target customers list.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        for customer in customers:
            plan_version.target_customers.add(customer)
        ct_after = plan_version.target_customers.all().count()
        if plan_version.is_custom is False and ct_after > 0:
            plan_version.is_custom = True
            # v0 is reserved for custom plan versions
            plan_version.version = 0
            plan_version.save()
        return Response(
            {
                "success": True,
                "message": f"Added {ct_after - ct_before} new customers to plan version. Total customers: {ct_after}.",
            }
        )

    @extend_schema(
        request=TargetCustomersSerializer,
        responses=inline_serializer(
            "RemoveTargetCustomerResponse",
            fields={
                "success": serializers.BooleanField(),
                "message": serializers.CharField(),
            },
        ),
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="target_customers/remove",
        url_name="remove_target_customer",
    )
    def remove_target_customer(self, request, *args, **kwargs):
        plan_version = self.get_object()
        organization = self.request.organization
        serializer = TargetCustomersSerializer(
            data=request.data, context={"organization": organization}
        )
        serializer.is_valid(raise_exception=True)
        customers = serializer.validated_data["customers"]
        for customer in customers:
            cust_subs = plan_version.subscription_records.active().filter(
                customer=customer
            )
            if cust_subs.count() > 0:
                raise InvalidOperation(
                    f"Customer {customer} has active subscriptions with this plan version. Cannot remove from plan version."
                )
        ct_before = plan_version.target_customers.all().count()
        for customer in customers:
            plan_version.target_customers.remove(customer)
        ct_after = plan_version.target_customers.all().count()
        return Response(
            {
                "success": True,
                "message": f"Removed {ct_before - ct_after} customers from plan version. Total customers: {ct_after}.",
            }
        )

    @extend_schema(
        request=inline_serializer(
            "MakePublicRequest",
            fields={
                "version": serializers.IntegerField(validators=[MinValueValidator(1)]),
            },
        ),
        responses=inline_serializer(
            "MakePublicResponse",
            fields={
                "success": serializers.BooleanField(),
                "message": serializers.CharField(),
            },
        ),
    )
    @action(
        detail=True, methods=["post"], url_path="make_public", url_name="make_public"
    )
    def make_public(self, request, *args, **kwargs):
        new_version = request.data.get("version")
        if new_version is None or new_version < 1:
            raise ValidationError("Invalid version number.")
        plan_version = self.get_object()
        if plan_version.is_custom is True:
            plan_version.is_custom = False
            plan_version.version = new_version
            plan_version.save()
            plan_version.target_customers.clear()
        return Response(
            {
                "success": True,
                "message": f"Plan version {str(plan_version)} made public as version {new_version}.",
            }
        )

    @extend_schema(
        parameters=None,
        request=None,
        responses=inline_serializer(
            "DeletePlanVersionSerializer",
            fields={
                "success": serializers.BooleanField(),
                "message": serializers.CharField(),
            },
        ),
    )
    @action(detail=True, methods=["post"], url_path="delete")
    def delete(self, request, *args, **kwargs):
        organization = self.request.organization
        now = now_utc()
        plan_version = self.get_object()
        num_active_subscriptions = (
            SubscriptionRecord.objects.active()
            .filter(
                organization=organization,
                billing_plan=plan_version,
            )
            .count()
        )
        if num_active_subscriptions > 0:
            raise InvalidOperation(
                "Cannot delete plan version with active subscriptions"
            )
        plan_version.deleted = now
        plan_version.save()
        return Response(
            {
                "success": True,
                "message": f"Deleted  plan version {str(plan_version)}",
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        parameters=None,
        request=SetReplaceWithSerializer,
        responses=inline_serializer(
            "SetReplaceWithResponse",
            fields={
                "success": serializers.BooleanField(),
                "message": serializers.CharField(),
            },
        ),
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="replacement/set",
        url_name="set_replacement",
    )
    def set_replacement(self, request, *args, **kwargs):
        plan_version = self.get_object()
        organization = self.request.organization
        serializer = SetReplaceWithSerializer(
            data=request.data, context={"organization": organization}
        )
        serializer.is_valid(raise_exception=True)
        replacement = serializer.validated_data["replace_with"]
        if replacement == plan_version:
            raise InvalidOperation("Cannot set plan version as its own replacement")
        if replacement.is_custom is True and plan_version.is_custom is False:
            raise InvalidOperation(
                "Cannot set custom plan version as replacement for public plan version"
            )
        if replacement.is_custom is True:
            replacement_target_customers = set(replacement.target_customers.all())
            plan_version_target_customers = set(plan_version.target_customers.all())
            if not plan_version_target_customers.issubset(replacement_target_customers):
                raise InvalidOperation(
                    "There are target customers in the plan version that are not in the replacement plan version. Please add them to the replacement plan version or remove them from the original plan version first."
                )
        plan_version.replace_with = replacement
        plan_version.save()
        return Response(
            {
                "success": True,
                "message": f"Added replacement plan version {str(replacement)} to {str(plan_version)}",
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        parameters=None,
        request=MakeReplaceWithSerializer,
        responses=inline_serializer(
            "MakeReplaceWithResponse",
            fields={
                "success": serializers.BooleanField(),
                "message": serializers.CharField(),
            },
        ),
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="replacement/make",
        url_name="make_replacement",
    )
    def make_replacement(self, request, *args, **kwargs):
        plan_version = self.get_object()
        organization = self.request.organization
        serializer = MakeReplaceWithSerializer(
            data=request.data, context={"organization": organization}
        )
        serializer.is_valid(raise_exception=True)
        versions_to_replace = serializer.validated_data["versions_to_replace"]
        for to_replace_v in versions_to_replace:
            if to_replace_v == plan_version:
                raise InvalidOperation("Cannot set plan version as its own replacement")
            if to_replace_v.is_custom is False and plan_version.is_custom is True:
                raise InvalidOperation(
                    "Cannot set custom plan version as replacement for public plan version"
                )
            if to_replace_v.is_custom is True:
                to_replace_target_customers = set(to_replace_v.target_customers.all())
                plan_version_target_customers = set(plan_version.target_customers.all())
                if not to_replace_target_customers.issubset(
                    plan_version_target_customers
                ):
                    raise InvalidOperation(
                        "There are target customers in the plan version that are not in the replacement plan version. Please add them to the replacement plan version or remove them from the original plan version first."
                    )
        PlanVersion.objects.filter(
            id__in=[v.id for v in versions_to_replace],
            organization=organization,
        ).update(replace_with=plan_version)
        return Response(
            {
                "success": True,
                "message": f"Set plan version {str(plan_version)} as replacement for {len(versions_to_replace)} plan versions",
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=AddFeatureSerializer,
        responses=inline_serializer(
            "AddFeatureResponse",
            fields={
                "success": serializers.BooleanField(),
                "message": serializers.CharField(),
            },
        ),
    )
    @action(
        detail=True, methods=["post"], url_path="features/add", url_name="features_add"
    )
    def add_feature(self, request, *args, **kwargs):
        plan_version = self.get_object()
        organization = self.request.organization
        serializer = AddFeatureSerializer(
            data=request.data, context={"organization": organization}
        )
        serializer.is_valid(raise_exception=True)
        feature = serializer.validated_data["feature"]
        plan_version.features.add(feature)
        return Response(
            {
                "success": True,
                "message": f"Added feature {str(feature)} to {str(plan_version)}",
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=None,
        responses=PlanVersionHistoricalSubscriptionSerializer(many=True),
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="subscriptions",
        url_name="subscriptions",
    )
    def subscriptions(self, request, *args, **kwargs):
        plan_version = self.get_object()
        organization = self.request.organization
        subscriptions = SubscriptionRecord.objects.filter(
            billing_plan=plan_version, organization=organization
        ).select_related("customer", "billing_plan")
        serializer = PlanVersionHistoricalSubscriptionSerializer(
            subscriptions, many=True
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class PlanViewSet(api_views.PlanViewSet):
    """
    ViewSet for viewing and editing Plans.
    """

    serializer_class = PlanDetailSerializer
    lookup_field = "plan_id"
    http_method_names = ["get", "post", "patch", "head"]
    permission_classes_per_method = {
        "create": [IsAuthenticated & ValidOrganization],
        "partial_update": [IsAuthenticated & ValidOrganization],
    }

    def get_object(self):
        string_uuid = self.kwargs[self.lookup_field]
        if "plan_" in string_uuid:
            uuid = PlanUUIDField().to_internal_value(string_uuid)
        else:
            uuid = AddOnUUIDField().to_internal_value(string_uuid)
        self.kwargs[self.lookup_field] = uuid
        return super().get_object()

    def get_queryset(self):
        qs = super().get_queryset()
        return qs

    def get_serializer_class(self):
        if self.action == "partial_update":
            return PlanUpdateSerializer
        elif self.action == "create":
            return PlanCreateSerializer
        return PlanDetailSerializer

    @extend_schema(responses=PlanDetailSerializer)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        metric_data = PlanDetailSerializer(instance).data
        return Response(metric_data, status=status.HTTP_201_CREATED)

    @extend_schema(responses=PlanDetailSerializer)
    def update(self, request, *args, **kwargs):
        plan = self.get_object()
        serializer = self.get_serializer(plan, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        if getattr(plan, "_prefetched_objects_cache", None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            plan._prefetched_objects_cache = {}

        return Response(
            PlanDetailSerializer(plan, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            user = self.request.user
        else:
            user = None
        instance = serializer.save(
            organization=self.request.organization, created_by=user
        )
        return instance

    @extend_schema(
        parameters=None,
        request=None,
        responses=inline_serializer(
            "DeletePlanSerializer",
            fields={
                "success": serializers.BooleanField(),
                "message": serializers.CharField(),
            },
        ),
    )
    @action(detail=True, methods=["post"], url_path="delete")
    def delete(self, request, *args, **kwargs):
        organization = self.request.organization
        now = now_utc()
        plan = self.get_object()
        num_active_subscriptions = (
            SubscriptionRecord.objects.active()
            .filter(
                organization=organization,
                billing_plan__plan=plan,
            )
            .count()
        )
        if num_active_subscriptions > 0:
            raise InvalidOperation("Cannot delete plan with active subscriptions")
        versions = plan.versions.filter(deleted__isnull=True)
        num_versions = versions.count()
        versions.update(deleted=now)
        plan.deleted = now
        plan.save()
        return Response(
            {
                "success": True,
                "message": f"Deleted {num_versions} versions of plan {plan.plan_name}",
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        parameters=None,
        request=inline_serializer(
            "AddPlanTags",
            fields={
                "tags": serializers.ListField(child=TagSerializer(), required=False),
            },
        ),
        responses=inline_serializer(
            "AddPlanTags",
            fields={
                "tags": serializers.ListField(child=TagSerializer(), required=False),
                "success": serializers.BooleanField(),
                "message": serializers.CharField(),
            },
        ),
    )
    @action(detail=True, methods=["post"], url_path="tags/add", url_name="tags_add")
    def add_tags(self, request, *args, **kwargs):
        plan = self.get_object()
        tags = request.data.get("tags", [])
        if not tags:
            return Response(
                {
                    "success": False,
                    "message": "No tags provided",
                    "tags": TagSerializer(plan.tags.all(), many=True).data,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        old_tags_ct = plan.tags.all().count()
        plan.add_tags(tags)
        new_tags = plan.tags.all()
        new_tags_data = TagSerializer(new_tags, many=True).data
        return Response(
            {
                "tags": new_tags_data,
                "success": True,
                "message": f"Added {len(new_tags_data) - old_tags_ct} tags to plan {str(plan)}",
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        parameters=None,
        request=inline_serializer(
            "RemovePlanTags",
            fields={
                "tags": serializers.ListField(child=TagSerializer(), required=False),
            },
        ),
        responses=inline_serializer(
            "RemovePlanTags",
            fields={
                "tags": serializers.ListField(child=TagSerializer(), required=False),
                "success": serializers.BooleanField(),
                "message": serializers.CharField(),
            },
        ),
    )
    @action(
        detail=True, methods=["post"], url_path="tags/remove", url_name="tags_remove"
    )
    def remove_tags(self, request, *args, **kwargs):
        plan = self.get_object()
        tags = request.data.get("tags", [])
        if not tags:
            return Response(
                {
                    "success": False,
                    "message": "No tags provided",
                    "tags": TagSerializer(plan.tags.all(), many=True).data,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        old_tags_ct = plan.tags.all().count()
        plan.remove_tags(tags)
        new_tags = plan.tags.all()
        new_tags_data = TagSerializer(new_tags, many=True).data
        return Response(
            {
                "tags": new_tags_data,
                "success": True,
                "message": f"Removed {old_tags_ct - len(new_tags_data)} tags from plan {str(plan)}",
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        parameters=None,
        request=inline_serializer(
            "SetPlanTags",
            fields={
                "tags": serializers.ListField(child=TagSerializer(), required=False),
            },
        ),
        responses=inline_serializer(
            "SetPlanTagsResponse",
            fields={
                "tags": serializers.ListField(child=TagSerializer(), required=False),
                "success": serializers.BooleanField(),
                "message": serializers.CharField(),
            },
        ),
    )
    @action(detail=True, methods=["post"], url_path="tags/set", url_name="tags_set")
    def set_tags(self, request, *args, **kwargs):
        plan = self.get_object()
        tags = request.data.get("tags", [])
        if not tags:
            return Response(
                {
                    "success": False,
                    "message": "No tags provided",
                    "tags": TagSerializer(plan.tags.all(), many=True).data,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        plan.set_tags(tags)
        new_tags = plan.tags.all()
        new_tags_data = TagSerializer(new_tags, many=True).data
        return Response(
            {
                "tags": new_tags_data,
                "success": True,
                "message": f"Set {len(new_tags_data)} tags on plan {str(plan)}",
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        parameters=None,
        request=AddFeatureToPlanSerializer,
        responses=inline_serializer(
            "AddFeatureToPlanResponse",
            fields={
                "success": serializers.BooleanField(),
                "message": serializers.CharField(),
            },
        ),
    )
    @action(
        detail=True, methods=["post"], url_path="features/add", url_name="features_add"
    )
    def add_feature(self, request, *args, **kwargs):
        plan = self.get_object()
        serializer = AddFeatureToPlanSerializer(
            data=request.data, context={"organization": request.organization}
        )
        serializer.is_valid(raise_exception=True)
        feature = serializer.validated_data["feature"]
        if serializer.validated_data["all_versions"] is True:
            plan_versions = plan.versions.get_queryset()
        else:
            plan_versions = serializer.validated_data["plan_versions"]
        for pv in plan_versions:
            pv.features.add(feature)
        return Response(
            {
                "success": True,
                "message": f"Added feature {feature.feature_name} to {len(plan_versions)} versions of plan {plan.plan_name}",
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="plan_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="The ID of the plan whose versions we're adding a feature to.",
            ),
            OpenApiParameter(
                name="version_number",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The version number to update.",
            ),
        ],
        request=AddFeatureToPlanSerializer,
        responses=inline_serializer(
            "AddFeatureToPlanVersionNumberResponse",
            fields={
                "success": serializers.BooleanField(),
                "message": serializers.CharField(),
            },
        ),
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="versions/(?P<version_number>[^/.]+)/features/add",
        url_name="plan_versions-features-add ",
    )
    def add_feature_to_version_number(self, request, *args, **kwargs):
        plan = self.get_object()
        serializer = AddFeatureToPlanSerializer(
            data=request.data, context={"organization": request.organization}
        )
        serializer.is_valid(raise_exception=True)
        feature = serializer.validated_data["feature"]
        if serializer.validated_data["all_versions"] is True:
            plan_versions = plan.versions.get_queryset()
        else:
            plan_versions = serializer.validated_data["plan_versions"]
        version_number = self.kwargs.get("version_number")
        if version_number is None or version_number < 1:
            raise ValidationError(
                "Valid version number is required when performing this action."
            )
        plan_versions = plan_versions.filter(version=version_number)
        if plan_versions.count() == 0:
            raise ValidationError(
                f"Plan {plan.plan_name} does not have any of the plan versions specified under version number {serializer.validated_data['version_number']} "
            )
        for pv in plan_versions:
            pv.features.add(feature)
        return Response(
            {
                "success": True,
                "message": f"Added feature {feature.feature_name} to {len(plan_versions)} versions of plan {plan.plan_name}",
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="plan_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="The ID of the plan whose versions we're changing the active dates.",
            ),
            OpenApiParameter(
                name="version_number",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The version number to update.",
            ),
        ],
        request=ChangeActiveDatesSerializer,
        responses=inline_serializer(
            "ChangeActiveDateResponse",
            fields={
                "success": serializers.BooleanField(),
                "message": serializers.CharField(),
            },
        ),
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="versions/(?P<version_number>[^/.]+)/active_dates/update",
        url_name="plan_versions-active_dates-update",
    )
    def change_version_number_active_dates(self, request, *args, **kwargs):
        plan = self.get_object()
        serializer = ChangeActiveDatesSerializer(
            data=request.data, context={"organization": request.organization}
        )
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data["all_versions"] is True:
            plan_versions = plan.versions.get_queryset()
        else:
            plan_versions = serializer.validated_data["plan_versions"]
        # get the current version number
        version_number = self.kwargs.get("version_number")
        if version_number is None or version_number < 1:
            raise ValidationError(
                "Valid version number is required when performing this action."
            )
        plan_versions = plan_versions.filter(version=version_number)
        if plan_versions.count() == 0:
            raise ValidationError(
                f"Plan {plan.plan_name} does not have any of the plan versions specified under version number {serializer.validated_data['version_number']} "
            )
        update_kwargs = {}
        if "active_from" in serializer.validated_data:
            update_kwargs["active_from"] = serializer.validated_data["active_from"]
        if "active_to" in serializer.validated_data:
            update_kwargs["active_to"] = serializer.validated_data["active_to"]
        plan_versions.update(**update_kwargs)
        return Response(
            {
                "success": True,
                "message": f"Changed active dates of {len(plan_versions)} instances of version {version_number} of plan {plan.plan_name}",
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        parameters=None,
        request=PlansSetReplaceWithForVersionNumberSerializer,
        responses=inline_serializer(
            "PlanVersionNumberSetReplaceWithResponse",
            fields={
                "success": serializers.BooleanField(),
                "message": serializers.CharField(),
            },
        ),
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="versions/(?P<version_number>[^/.]+)/replacement/set",
        url_name="plan_versions-replacement-set",
    )
    def set_replacement_for_version_number(self, request, *args, **kwargs):
        plan = self.get_object()
        organization = self.request.organization
        serializer = PlansSetReplaceWithForVersionNumberSerializer(
            data=request.data, context={"organization": organization}
        )
        serializer.is_valid(raise_exception=True)
        # extract versions to replace
        if serializer.validated_data["all_versions"] is True:
            plan_versions = plan.versions.get_queryset()
        else:
            plan_versions = serializer.validated_data["plan_versions"]

        # get the current version number
        version_number = self.kwargs.get("version_number")
        if version_number is None or version_number < 1:
            raise ValidationError(
                "Valid version number is required when performing this action."
            )
        current_plan_versions = plan_versions.filter(version=version_number)

        # get the replacement version number
        replacement_version_number = serializer.validated_data[
            "replacement_version_number"
        ]
        if replacement_version_number == version_number:
            raise ValidationError(
                "Replacement version number cannot be the same as the version number."
            )
        replacement_plan_versions = plan_versions.filter(
            version=replacement_version_number
        )

        # build a replacement map to maker sure they're all valid before performing the update
        replacement_map = {}
        for pv in current_plan_versions:
            try:
                replacement_map[pv] = replacement_plan_versions.get(
                    currency=pv.currency
                )
            except PlanVersion.DoesNotExist:
                raise ValidationError(
                    f"Replacement plan version {replacement_version_number} for currency {pv.currency} does not exist."
                )
            except PlanVersion.MultipleObjectsReturned:
                raise ValidationError(
                    f"Multiple replacement plan versions {replacement_version_number} for currency {pv.currency} exist."
                )
        for pv, replacement in replacement_map.items():
            pv.replacement = replacement
            pv.save()
        return Response(
            {
                "success": True,
                "message": f"Added replacement plan version {replacement_version_number} for {len(current_plan_versions)} instances of version {version_number} of plan {plan.plan_name}",
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        parameters=None,
        request=PlansSetTransitionToForVersionNumberSerializer,
        responses=inline_serializer(
            "PlanVersionNumberSetTransitionToResponse",
            fields={
                "success": serializers.BooleanField(),
                "message": serializers.CharField(),
            },
        ),
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="versions/(?P<version_number>[^/.]+)/transition/set",
        url_name="plan_versions-transition-set",
    )
    def set_transition_for_version_number(self, request, *args, **kwargs):
        plan = self.get_object()
        organization = self.request.organization
        serializer = PlansSetTransitionToForVersionNumberSerializer(
            data=request.data, context={"organization": organization}
        )
        serializer.is_valid(raise_exception=True)
        # extract versions to replace
        if serializer.validated_data["all_versions"] is True:
            plan_versions = plan.versions.get_queryset()
        else:
            plan_versions = serializer.validated_data["plan_versions"]

        # get the current version number
        version_number = self.kwargs.get("version_number")
        if version_number is None or version_number < 1:
            raise ValidationError(
                "Valid version number is required when performing this action."
            )
        current_plan_versions = plan_versions.filter(version=version_number)

        # get the replacement version number
        transition_to_plan = serializer.validated_data["transition_to_plan"]
        if transition_to_plan == plan:
            raise ValidationError(
                "Transition to plan cannot be the same as the plan being updated."
            )
        current_plan_versions.update(transition_to=transition_to_plan)
        return Response(
            {
                "success": True,
                "message": f"Added transition to plan {transition_to_plan.plan_name} for {len(current_plan_versions)} instances of version {version_number} of plan {plan.plan_name}",
            },
            status=status.HTTP_200_OK,
        )


class SubscriptionViewSet(api_views.SubscriptionViewSet):
    @extend_schema(exclude=True)
    def add(self, request, *args, **kwargs):
        raise MethodNotAllowed(request.method)

    @extend_schema(exclude=True)
    def cancel_multi(self, request, *args, **kwargs):
        raise MethodNotAllowed(request.method)

    @extend_schema(exclude=True)
    def edit(self, request, *args, **kwargs):
        raise MethodNotAllowed(request.method)


class InvoiceViewSet(api_views.InvoiceViewSet):
    http_method_names = ["get", "patch", "head", "post"]

    def get_serializer_class(self):
        if self.action == "send":
            return InvoiceDetailSerializer
        return super().get_serializer_class()

    @extend_schema(request=None)
    @action(detail=True, methods=["post"])
    def send(self, request, *args, **kwargs):
        invoice = self.get_object()
        customer = invoice.customer
        if customer.payment_provider and invoice.external_payment_obj_type is None:
            connector = PAYMENT_PROCESSOR_MAP.get(customer.payment_provider)
            if connector:
                external_id = connector.create_payment_object(invoice)
                if external_id:
                    invoice.external_payment_obj_id = external_id
                    invoice.external_payment_obj_type = customer.payment_provider
                    invoice.save()
        serializer = self.get_serializer(invoice)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BacktestViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    lookup_field = "backtest_id"
    http_method_names = [
        "get",
        "post",
        "head",
    ]
    permission_classes_per_method = {
        "create": [IsAuthenticated & ValidOrganization],
        "destroy": [IsAuthenticated & ValidOrganization],
    }
    queryset = Backtest.objects.all()

    def get_object(self):
        string_uuid = self.kwargs[self.lookup_field]
        uuid = BacktestUUIDField().to_internal_value(string_uuid)
        self.kwargs[self.lookup_field] = uuid
        return super().get_object()

    def get_serializer_class(self):
        if self.action == "list":
            return BacktestSummarySerializer
        elif self.action == "retrieve":
            return BacktestDetailSerializer
        else:
            return BacktestCreateSerializer

    def get_queryset(self):
        organization = self.request.organization
        return Backtest.objects.filter(organization=organization)

    def perform_create(self, serializer):
        backtest_obj = serializer.save(organization=self.request.organization)
        bt_id = backtest_obj.backtest_id
        run_backtest.delay(bt_id)

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
                event=f"{self.action}_backtest",
                properties={"organization": organization.organization_name},
            )
        return response

    def get_serializer_context(self):
        context = super().get_serializer_context()
        organization = self.request.organization
        context.update({"organization": organization})
        return context


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    lookup_field = "product_id"
    http_method_names = [
        "get",
        "post",
        "head",
    ]
    queryset = Product.objects.all()

    def get_queryset(self):
        organization = self.request.organization
        return Product.objects.filter(organization=organization)

    def perform_create(self, serializer):
        serializer.save(organization=self.request.organization)

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
                event=f"{self.action}_product",
                properties={"organization": organization.organization_name},
            )
        return response

    def get_serializer_context(self):
        context = super().get_serializer_context()
        organization = self.request.organization
        context.update({"organization": organization})
        return context


class ActionCursorSetPagination(CursorSetPagination):
    ordering = "-timestamp"


class ActionViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    API endpoint that allows events to be viewed.
    """

    queryset = Action.objects.all()
    serializer_class = ActionSerializer
    pagination_class = ActionCursorSetPagination
    permission_classes = [IsAuthenticated & ValidOrganization]
    http_method_names = [
        "get",
        "head",
    ]

    def get_queryset(self):
        organization = self.request.organization
        return (
            super()
            .get_queryset()
            .filter(
                actor_object_id__in=list(
                    User.objects.filter(organization=organization).values_list(
                        "id", flat=True
                    )
                )
            )
        )


class ExternalPlanLinkViewSet(viewsets.ModelViewSet):
    serializer_class = ExternalPlanLinkSerializer
    permission_classes = [IsAuthenticated & ValidOrganization]
    lookup_field = "external_plan_id"
    http_method_names = ["post", "head", "delete"]
    queryset = ExternalPlanLink.objects.all()

    def get_queryset(self):
        filter_kwargs = {"organization": self.request.organization}
        source = self.request.query_params.get("source")
        if source:
            filter_kwargs["source"] = source
        return ExternalPlanLink.objects.filter(**filter_kwargs)

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
                event=f"{self.action}_external_plan_link",
                properties={"organization": organization.organization_name},
            )
        return response

    def perform_create(self, serializer):
        serializer.save(organization=self.request.organization)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        organization = self.request.organization
        context.update({"organization": organization})
        return context

    @extend_schema(
        parameters=[
            inline_serializer(
                name="SourceSerializer",
                fields={
                    "source": serializers.ChoiceField(
                        choices=PAYMENT_PROCESSORS.choices
                    )
                },
            ),
        ],
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request)


class OrganizationSettingViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated & ValidOrganization]
    http_method_names = ["get", "head", "patch"]
    lookup_field = "setting_id"
    queryset = OrganizationSetting.objects.all()

    def get_object(self):
        string_uuid = self.kwargs[self.lookup_field]
        uuid = OrganizationSettingUUIDField().to_internal_value(string_uuid)
        self.kwargs[self.lookup_field] = uuid
        return super().get_object()

    def get_serializer_class(self):
        if self.action == "partial_update":
            return OrganizationSettingUpdateSerializer
        return OrganizationSettingSerializer

    def get_queryset(self):
        filter_kwargs = {"organization": self.request.organization}
        serializer = OrganizationSettingFilterSerializer(
            data=self.request.query_params,
        )
        serializer.is_valid(raise_exception=True)
        setting_name = serializer.validated_data.get("setting_name", [])
        if len(setting_name) > 0:
            filter_kwargs["setting_name__in"] = setting_name
        setting_group = serializer.validated_data.get("setting_group", None)
        if setting_group:
            filter_kwargs["setting_group"] = setting_group
        return OrganizationSetting.objects.filter(**filter_kwargs)

    @extend_schema(
        parameters=[OrganizationSettingFilterSerializer],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request)

    @extend_schema(responses=OrganizationSettingSerializer)
    def update(self, request, *args, **kwargs):
        organization_setting = self.get_object()
        serializer = self.get_serializer(
            organization_setting, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        if getattr(organization_setting, "_prefetched_objects_cache", None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            organization_setting._prefetched_objects_cache = {}

        return Response(
            OrganizationSettingSerializer(
                organization_setting, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_200_OK,
        )


class PricingUnitViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):
    serializer_class = PricingUnitDetailSerializer
    permission_classes = [IsAuthenticated & ValidOrganization]
    http_method_names = ["get", "post", "head"]

    def get_queryset(self):
        organization = self.request.organization
        return PricingUnit.objects.filter(organization=organization).prefetch_related(
            "organization"
        )

    def perform_create(self, serializer):
        serializer.save(organization=self.request.organization)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        organization = self.request.organization
        context.update({"organization": organization})
        return context


class OrganizationViewSet(
    PermissionPolicyMixin,
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated & ValidOrganization]
    http_method_names = ["get", "patch", "head", "post"]
    permission_classes_per_method = {
        "list": [IsAuthenticated & ValidOrganization],
        "partial_update": [IsAuthenticated & ValidOrganization],
    }
    lookup_field = "organization_id"
    queryset = Organization.objects.all()

    def get_object(self):
        string_uuid = self.kwargs[self.lookup_field]
        uuid = OrganizationUUIDField().to_internal_value(string_uuid)
        self.kwargs[self.lookup_field] = uuid
        return super().get_object()

    def get_queryset(self):
        organization = self.request.organization
        return Organization.objects.filter(pk=organization.pk).prefetch_related(
            "settings"
        )

    def get_serializer_class(self):
        if self.action == "partial_update":
            return OrganizationUpdateSerializer
        elif self.action == "create":
            return OrganizationCreateSerializer
        return OrganizationSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        organization = self.request.organization
        user = self.request.user
        context.update({"organization": organization, "user": user})
        return context

    @extend_schema(responses=OrganizationSerializer)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        org_data = OrganizationSerializer(instance).data
        return Response(org_data, status=status.HTTP_201_CREATED)

    @extend_schema(responses=OrganizationSerializer)
    def update(self, request, *args, **kwargs):
        org = self.get_object()
        serializer = self.get_serializer(org, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        if getattr(org, "_prefetched_objects_cache", None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            org._prefetched_objects_cache = {}
        return Response(
            OrganizationSerializer(org, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(responses=OrganizationSerializer)
    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)


class CustomerBalanceAdjustmentViewSet(api_views.CustomerBalanceAdjustmentViewSet):
    pass


class AddOnViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated & ValidOrganization]
    http_method_names = ["get", "post", "patch", "head"]
    lookup_field = "plan_id"
    lookup_url_kwarg = "addon_id"
    queryset = Plan.addons.all()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        organization = self.request.organization
        context.update({"organization": organization})
        return context

    def get_object(self):
        string_uuid = self.kwargs[self.lookup_url_kwarg]
        uuid = AddOnUUIDField().to_internal_value(string_uuid)
        self.kwargs[self.lookup_url_kwarg] = uuid
        return super().get_object()

    def get_serializer_class(self):
        if self.action == "create":
            return AddOnCreateSerializer
        elif self.action == "partial_update":
            return AddOnUpdateSerializer
        return AddOnDetailSerializer

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            user = self.request.user
        else:
            user = None
        instance = serializer.save(
            organization=self.request.organization, created_by=user
        )
        return instance

    def get_queryset(self):
        filter_kwargs = {"organization": self.request.organization}
        qs = self.queryset
        return qs.filter(**filter_kwargs)

    @extend_schema(responses=AddOnDetailSerializer)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        addon_data = AddOnDetailSerializer(instance).data
        return Response(addon_data, status=status.HTTP_201_CREATED)

    @extend_schema(
        parameters=None,
        request=AddFeatureToAddOnSerializer,
        responses=inline_serializer(
            "AddFeatureToAddOnResponse",
            fields={
                "success": serializers.BooleanField(),
                "message": serializers.CharField(),
            },
        ),
    )
    @action(detail=True, methods=["post"], url_path="features/add")
    def add_feature(self, request, *args, **kwargs):
        addon = self.get_object()
        serializer = AddFeatureToAddOnSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        feature = serializer.validated_data["feature_id"]
        if serializer.validated_data["all_versions"] is True:
            addon_versions = addon.versions.get_queryset()
        else:
            addon_versions = serializer.validated_data["version_ids"]
        for aov in addon_versions:
            aov.features.add(feature)
        return Response(
            {
                "success": True,
                "message": f"Added feature {feature.name} to {len(addon_versions)} versions of plan {addon.plan_name}",
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        parameters=None,
        request=None,
        responses=inline_serializer(
            "DeleteAddOnSerializer",
            fields={
                "success": serializers.BooleanField(),
                "message": serializers.CharField(),
            },
        ),
    )
    @action(detail=True, methods=["post"], url_path="delete")
    def delete(self, request, *args, **kwargs):
        organization = self.request.organization
        now = now_utc()
        addon = self.get_object()
        num_active_subscriptions = SubscriptionRecord.objects.active().filter(
            organization=organization,
            billing_plan__plan=addon,
        )
        if num_active_subscriptions > 0:
            raise InvalidOperation("Cannot delete plan with active subscriptions")
        versions = addon.versions.filter(deleted__isnull=True)
        num_versions = versions.count()
        versions.update(deleted=now)
        addon.deleted = now
        addon.save()
        return Response(
            {
                "success": True,
                "message": f"Deleted {num_versions} versions of addon {addon.plan_name}",
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(responses=AddOnDetailSerializer)
    def update(self, request, *args, **kwargs):
        plan = self.get_object()
        serializer = self.get_serializer(plan, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        if getattr(plan, "_prefetched_objects_cache", None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            plan._prefetched_objects_cache = {}

        return Response(
            AddOnDetailSerializer(plan, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )


class AddOnVersionViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    serializer_class = AddOnVersionDetailSerializer
    lookup_field = "version_id"
    http_method_names = [
        "post",
        "head",
        "patch",
    ]
    permission_classes_per_method = {
        "create": [IsAuthenticated & ValidOrganization],
        "partial_update": [IsAuthenticated & ValidOrganization],
    }
    queryset = PlanVersion.addon_versions.all()

    def get_object(self):
        string_uuid = self.kwargs[self.lookup_field]
        uuid = AddOnVersionUUIDField().to_internal_value(string_uuid)
        self.kwargs[self.lookup_field] = uuid
        return super().get_object()

    def get_serializer_class(self):
        if self.action == "partial_update":
            return AddOnVersionUpdateSerializer
        elif self.action == "create":
            return AddOnVersionCreateSerializer
        return AddOnVersionDetailSerializer

    def get_queryset(self):
        organization = self.request.organization
        qs = PlanVersion.plan_versions.filter(
            organization=organization,
        )
        return qs

    def get_serializer_context(self):
        context = super().get_serializer_context()
        organization = self.request.organization
        if self.request.user.is_authenticated:
            user = self.request.user
        else:
            user = None
        context.update({"organization": organization, "user": user})
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
                event=f"{self.action}_plan_version",
                properties={"organization": organization.organization_name},
            )
        return response

    @extend_schema(responses=AddOnVersionDetailSerializer)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        plan_version_data = AddOnVersionDetailSerializer(instance).data
        return Response(plan_version_data, status=status.HTTP_201_CREATED)

    @extend_schema(responses=AddOnVersionDetailSerializer)
    def update(self, request, *args, **kwargs):
        pv = self.get_object()
        serializer = self.get_serializer(pv, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        if getattr(pv, "_prefetched_objects_cache", None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            pv._prefetched_objects_cache = {}

        return Response(
            AddOnVersionDetailSerializer(
                pv, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_200_OK,
        )

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            user = self.request.user
        else:
            user = None
        instance = serializer.save(
            organization=self.request.organization, created_by=user
        )
        # if user:
        #     action.send(
        #         user,
        #         verb="created",
        #         action_object=instance,
        #         target=instance.plan,
        #     )
        return instance

    @extend_schema(
        parameters=None,
        request=None,
        responses=inline_serializer(
            "DeleteAddOnVersionSerializer",
            fields={
                "success": serializers.BooleanField(),
                "message": serializers.CharField(),
            },
        ),
    )
    @action(detail=True, methods=["post"], url_path="delete")
    def delete(self, request, *args, **kwargs):
        organization = self.request.organization
        now = now_utc()
        addon_version = self.get_object()
        num_active_subscriptions = SubscriptionRecord.objects.active().filter(
            organization=organization,
            billing_plan=addon_version,
        )
        if num_active_subscriptions > 0:
            raise InvalidOperation(
                "Cannot delete plan version with active subscriptions"
            )
        addon_version.deleted = now
        addon_version.save()
        return Response(
            {
                "success": True,
                "message": f"Deleted  plan version {str(addon_version)}",
            },
            status=status.HTTP_200_OK,
        )


class UsageAlertViewSet(viewsets.ModelViewSet):
    """
    ViewSet for viewing and editing UsageAlerts.
    """

    serializer_class = UsageAlertSerializer
    permission_classes = [IsAuthenticated & ValidOrganization]
    http_method_names = ["get", "post", "head", "delete"]
    queryset = UsageAlert.objects.all()
    lookup_field = "usage_alert_id"

    def get_object(self):
        string_uuid = self.kwargs[self.lookup_field]
        uuid = UsageAlertUUIDField().to_internal_value(string_uuid)
        self.kwargs[self.lookup_field] = uuid
        return super().get_object()

    def get_serializer_class(self):
        if self.action == "create":
            return UsageAlertCreateSerializer
        return UsageAlertSerializer

    def get_queryset(self):
        organization = self.request.organization
        return UsageAlert.objects.filter(organization=organization)

    def perform_create(self, serializer):
        serializer.save(organization=self.request.organization)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        organization = self.request.organization
        context.update({"organization": organization})
        return context
        context = super().get_serializer_context()
        organization = self.request.organization
        context.update({"organization": organization})
        return context
