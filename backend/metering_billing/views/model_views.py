# import lotus_python
import logging

import posthog
import sentry_sdk
from actstream.models import Action
from api.serializers.webhook_serializers import (
    CustomerCreatedSerializer,
    InvoiceCreatedSerializer,
    InvoicePaidSerializer,
    InvoicePastDueSerializer,
    UsageAlertTriggeredSerializer,
    SubscriptionCancelledSerializer,
    SubscriptionCreatedSerializer,
    SubscriptionRenewedSerializer,
)
from django.conf import settings
from django.core.cache import cache
from django.db.utils import IntegrityError
from drf_spectacular.utils import OpenApiCallback, extend_schema, inline_serializer
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

import api.views as api_views

from metering_billing.exceptions import (
    DuplicateMetric,
    DuplicateWebhookEndpoint,
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
    AddOnSerializer,
    APITokenSerializer,
    CustomerSerializer,
    CustomerSummarySerializer,
    CustomerUpdateSerializer,
    CustomerWithRevenueSerializer,
    EventSerializer,
    ExternalPlanLinkSerializer,
    FeatureCreateSerializer,
    FeatureSerializer,
    InvoiceSerializer,
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
    PlanVersionUpdateSerializer,
    PricingUnitSerializer,
    ProductSerializer,
    UsageAlertCreateSerializer,
    UsageAlertSerializer,
    UserSerializer,
    WebhookEndpointSerializer,
)
from metering_billing.serializers.request_serializers import (
    OrganizationSettingFilterSerializer,
)
from metering_billing.serializers.serializer_utils import (
    AddonUUIDField,
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
                WEBHOOK_TRIGGER_EVENTS.CUSTOMER_CREATED.value,
                "{$request.body#/webhook_url}",
                extend_schema(
                    description="Customer created webhook",
                    responses={200: CustomerCreatedSerializer},
                ),
            ),
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
                WEBHOOK_TRIGGER_EVENTS.SUBSCRIPTION_CANCELLED.value,
                "{$request.body#/webhook_url}",
                extend_schema(
                    description="Subscription cancelled webhook",
                    responses={200: SubscriptionCancelledSerializer},
                ),
            ),
            OpenApiCallback(
                WEBHOOK_TRIGGER_EVENTS.INVOICE_PAST_DUE.value,
                "{$request.body#/webhook_url}",
                extend_schema(
                    description="Usage alert triggered webhook",
                    responses={200: InvoicePastDueSerializer},
                ),
            ),
            OpenApiCallback(
                WEBHOOK_TRIGGER_EVENTS.SUBSCRIPTION_CREATED.value,
                "{$request.body#/webhook_url}",
                extend_schema(
                    description="Subscription created webhook",
                    responses={200: SubscriptionCreatedSerializer},
                ),
            ),
            OpenApiCallback(
                WEBHOOK_TRIGGER_EVENTS.SUBSCRIPTION_RENEWED.value,
                "{$request.body#/webhook_url}",
                extend_schema(
                    description="Subscription renewed webhook",
                    responses={200: SubscriptionRenewedSerializer},
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
    serializer_class = EventSerializer
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
            CustomerSerializer(customer, context=self.get_serializer_context()).data,
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
    serializer_class = FeatureSerializer
    http_method_names = ["get", "post", "head"]
    permission_classes_per_method = {
        "create": [IsAuthenticated & ValidOrganization],
        "destroy": [IsAuthenticated & ValidOrganization],
    }
    queryset = Feature.objects.all()

    def get_serializer_class(self):
        if self.action == "create":
            return FeatureCreateSerializer
        return FeatureSerializer

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

    @extend_schema(responses=FeatureSerializer)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        feature_data = FeatureSerializer(instance).data
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
    queryset = PlanVersion.objects.all()

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
        qs = PlanVersion.objects.filter(
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
            uuid = AddonUUIDField().to_internal_value(string_uuid)
        self.kwargs[self.lookup_field] = uuid
        return super().get_object()

    def get_queryset(self):
        qs = super().get_queryset()
        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

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


class SubscriptionViewSet(api_views.SubscriptionViewSet):
    pass


class InvoiceViewSet(api_views.InvoiceViewSet):
    http_method_names = ["get", "patch", "head", "post"]

    def get_serializer_class(self):
        if self.action == "send":
            return InvoiceSerializer
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
    serializer_class = PricingUnitSerializer
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
    http_method_names = ["get", "head", "post"]
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
        uuid = AddonUUIDField().to_internal_value(string_uuid)
        self.kwargs[self.lookup_url_kwarg] = uuid
        return super().get_object()

    def get_serializer_class(self):
        if self.action == "create":
            return AddOnCreateSerializer
        return AddOnSerializer

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

    @extend_schema(responses=AddOnSerializer)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        addon_data = AddOnSerializer(instance).data
        return Response(addon_data, status=status.HTTP_201_CREATED)


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
        return context
        return context
        return context
        return context
        return context
        return context
        return context
        return context
        return context
        return context
        return context
        return context
