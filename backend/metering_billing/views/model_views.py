import api.views as api_views
import lotus_python
import posthog
from actstream import action
from actstream.models import Action
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, OuterRef, Prefetch, Q
from django.db.utils import IntegrityError
from drf_spectacular.utils import extend_schema, inline_serializer
from metering_billing.auth import parse_organization
from metering_billing.exceptions import DuplicateMetric, DuplicateWebhookEndpoint
from metering_billing.models import (
    Backtest,
    Event,
    ExternalPlanLink,
    Feature,
    Metric,
    OrganizationSetting,
    Plan,
    PlanVersion,
    PricingUnit,
    Product,
    User,
    WebhookEndpoint,
)
from metering_billing.permissions import ValidOrganization
from metering_billing.serializers.backtest_serializers import (
    BacktestCreateSerializer,
    BacktestDetailSerializer,
    BacktestSummarySerializer,
)
from metering_billing.serializers.model_serializers import *
from metering_billing.tasks import run_backtest
from metering_billing.utils import now_utc
from metering_billing.utils.enums import (
    METRIC_STATUS,
    PAYMENT_PROVIDERS,
    PLAN_VERSION_STATUS,
    SUBSCRIPTION_STATUS,
)
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from svix.api import MessageIn, Svix

POSTHOG_PERSON = settings.POSTHOG_PERSON
SVIX_CONNECTOR = settings.SVIX_CONNECTOR


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
        except:
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
        context = super(APITokenViewSet, self).get_serializer_context()
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
        cache.set(api_key.prefix, api_key.organization.pk, timeout)
        headers = self.get_success_headers(serializer.data)
        return Response(
            {"api_key": serializer.data, "key": key},
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def perform_destroy(self, instance):
        cache.delete(instance.prefix)
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


class WebhookViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    API endpoint that allows alerts to be viewed or edited.
    """

    serializer_class = WebhookEndpointSerializer
    permission_classes = [IsAuthenticated & ValidOrganization]
    http_method_names = ["get", "post", "head", "delete", "patch"]
    lookup_field = "webhook_endpoint_id"
    permission_classes_per_method = {
        "create": [IsAuthenticated & ValidOrganization],
        "list": [IsAuthenticated & ValidOrganization],
        "retrieve": [IsAuthenticated & ValidOrganization],
        "destroy": [IsAuthenticated & ValidOrganization],
        "partial_update": [IsAuthenticated & ValidOrganization],
    }
    queryset = WebhookEndpoint.objects.all()

    def get_queryset(self):
        organization = self.request.organization
        return WebhookEndpoint.objects.filter(organization=organization)

    def get_serializer_context(self):
        context = super(WebhookViewSet, self).get_serializer_context()
        organization = self.request.organization
        context.update({"organization": organization})
        return context

    def perform_create(self, serializer):
        try:
            serializer.save(organization=self.request.organization)
        except ValueError as e:
            raise ServerError(e)
        except IntegrityError as e:
            raise DuplicateWebhookEndpoint("Webhook endpoint already exists")

    def perform_destroy(self, instance):
        if SVIX_CONNECTOR is not None:
            svix = SVIX_CONNECTOR
            svix.endpoint.delete(
                instance.organization.organization_id,
                instance.webhook_endpoint_id,
            )
        instance.delete()

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except:
                username = None
            organization = self.request.organization
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (
                    username if username else organization.company_name + " (API Key)"
                ),
                event=f"{self.action}_webhook",
                properties={"organization": organization.company_name},
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
        context = super(EventViewSet, self).get_serializer_context()
        organization = self.request.organization
        context.update({"organization": organization})
        return context


class UserViewSet(
    PermissionPolicyMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """
    A simple ViewSet for viewing and editing Users.
    """

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated & ValidOrganization]
    http_method_names = ["get", "post", "head"]

    def get_queryset(self):
        organization = self.request.organization
        return User.objects.filter(organization=organization)

    def get_serializer_context(self):
        context = super(UserViewSet, self).get_serializer_context()
        organization = self.request.organization
        context.update({"organization": organization})
        return context

    def perform_create(self, serializer):
        serializer.save(organization=self.request.organization)


class CustomerViewSet(api_views.CustomerViewSet):
    http_method_names = ["get", "post", "head", "patch"]

    def get_serializer_class(self):
        sc = super().get_serializer_class()
        if self.action == "partial_update":
            return CustomerUpdateSerializer
        return sc


class MetricViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Billable Metrics.
    """

    http_method_names = ["get", "post", "head", "patch"]
    lookup_field = "metric_id"
    permission_classes_per_method = {
        "create": [IsAuthenticated & ValidOrganization],
        "partial_update": [IsAuthenticated & ValidOrganization],
    }
    queryset = Metric.objects.all()

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
        return MetricSerializer

    def get_serializer_context(self):
        context = super(MetricViewSet, self).get_serializer_context()
        organization = self.request.organization
        context.update({"organization": organization})
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except:
                username = None
            organization = self.request.organization
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (
                    username if username else organization.company_name + " (API Key)"
                ),
                event=f"{self.action}_metric",
                properties={"organization": organization.company_name},
            )
        return response

    @extend_schema(responses=MetricSerializer)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        metric_data = MetricSerializer(instance).data
        return Response(metric_data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        try:
            instance = serializer.save(organization=self.request.organization)
            return instance
        except IntegrityError as e:
            cause = e.__cause__
            if "unique_org_metric_id" in str(cause):
                error_message = "Metric ID already exists for this organization. This usually happens if you try to specify an ID instead of letting the Lotus backend handle ID creation."
                raise DuplicateMetric(error_message)
            elif "unique_org_billable_metric_name" in str(cause):
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
    """
    A simple ViewSet for viewing and editing Features.
    """

    serializer_class = FeatureSerializer
    http_method_names = ["get", "post", "head"]
    permission_classes_per_method = {
        "create": [IsAuthenticated & ValidOrganization],
        "destroy": [IsAuthenticated & ValidOrganization],
    }
    queryset = Feature.objects.all()

    def get_queryset(self):
        organization = self.request.organization
        return Feature.objects.filter(organization=organization)

    def get_serializer_context(self):
        context = super(FeatureViewSet, self).get_serializer_context()
        organization = self.request.organization
        context.update({"organization": organization})
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except:
                username = None
            organization = self.request.organization
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (
                    username if username else organization.company_name + " (API Key)"
                ),
                event=f"{self.action}_feature",
                properties={"organization": organization.company_name},
            )
        return response

    def perform_create(self, serializer):
        serializer.save(organization=self.request.organization)


class PlanVersionViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing PlanVersions.
    """

    serializer_class = PlanVersionSerializer
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

    def get_serializer_class(self):
        if self.action == "partial_update":
            return PlanVersionUpdateSerializer
        elif self.action == "create":
            return PlanVersionCreateSerializer
        return PlanVersionSerializer

    def get_queryset(self):
        organization = self.request.organization
        qs = PlanVersion.objects.filter(
            organization=organization,
        )
        return qs

    def get_serializer_context(self):
        context = super(PlanVersionViewSet, self).get_serializer_context()
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
            except:
                username = None
            organization = self.request.organization
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (
                    username if username else organization.company_name + " (API Key)"
                ),
                event=f"{self.action}_plan_version",
                properties={"organization": organization.company_name},
            )
        return response

    @extend_schema(responses=PlanVersionSerializer)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        plan_version_data = PlanVersionSerializer(instance).data
        return Response(plan_version_data, status=status.HTTP_201_CREATED)

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

    def perform_update(self, serializer):
        instance = serializer.save()
        # if self.request.user.is_authenticated:
        #     user = self.request.user
        # else:
        #     user = None
        # if user:
        #     if instance.status == PLAN_VERSION_STATUS.ACTIVE:
        #         action.send(
        #             user,
        #             verb="activated",
        #             action_object=instance,
        #             target=instance.plan,
        #         )
        #     elif instance.status == PLAN_VERSION_STATUS.ARCHIVED:
        #         action.send(
        #             user,
        #             verb="archived",
        #             action_object=instance,
        #             target=instance.plan,
        #         )


class PlanViewSet(api_views.PlanViewSet):
    """
    A simple ViewSet for viewing and editing Products.
    """

    serializer_class = PlanSerializer
    lookup_field = "plan_id"
    http_method_names = ["get", "post", "patch", "head"]
    queryset = Plan.objects.all()
    permission_classes_per_method = {
        "create": [IsAuthenticated & ValidOrganization],
        "partial_update": [IsAuthenticated & ValidOrganization],
    }

    def get_queryset(self):
        organization = self.request.organization
        now = now_utc()
        qs = super(PlanViewSet, self).get_queryset()
        if self.action == "retrieve" or self.action == "list":
            qs = qs.prefetch_related(
                Prefetch(
                    "versions",
                    queryset=PlanVersion.objects.filter(
                        ~Q(status=PLAN_VERSION_STATUS.ARCHIVED),
                        organization=organization,
                    ).annotate(
                        active_subscriptions=Count(
                            "subscription_record",
                            filter=Q(
                                subscription_record__start_date__lte=now,
                                subscription_record__end_date__gte=now,
                            ),
                        )
                    ),
                )
            )
        return qs

    def get_serializer_class(self):
        if self.action == "partial_update":
            return PlanUpdateSerializer
        elif self.action == "create":
            return PlanCreateSerializer
        return PlanSerializer

    @extend_schema(responses=PlanSerializer)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        metric_data = PlanSerializer(instance).data
        return Response(metric_data, status=status.HTTP_201_CREATED)

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
        #     )
        return instance

    def perform_update(self, serializer):
        instance = serializer.save()


class SubscriptionViewSet(api_views.SubscriptionViewSet):
    pass


class InvoiceViewSet(api_views.InvoiceViewSet):
    pass


class BacktestViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Backtests.
    """

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
            except:
                username = None
            organization = self.request.organization
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (
                    username if username else organization.company_name + " (API Key)"
                ),
                event=f"{self.action}_backtest",
                properties={"organization": organization.company_name},
            )
        return response

    def get_serializer_context(self):
        context = super(BacktestViewSet, self).get_serializer_context()
        organization = self.request.organization
        context.update({"organization": organization})
        return context


class ProductViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Products.
    """

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
            except:
                username = None
            organization = self.request.organization
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (
                    username if username else organization.company_name + " (API Key)"
                ),
                event=f"{self.action}_product",
                properties={"organization": organization.company_name},
            )
        return response

    def get_serializer_context(self):
        context = super(ProductViewSet, self).get_serializer_context()
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
    """
    A simple ViewSet for viewing and editing ExternalPlanLink.
    """

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
            except:
                username = None
            organization = self.request.organization
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (
                    username if username else organization.company_name + " (API Key)"
                ),
                event=f"{self.action}_external_plan_link",
                properties={"organization": organization.company_name},
            )
        return response

    def perform_create(self, serializer):
        serializer.save(organization=self.request.organization)

    def get_serializer_context(self):
        context = super(ExternalPlanLinkViewSet, self).get_serializer_context()
        organization = self.request.organization
        context.update({"organization": organization})
        return context

    @extend_schema(
        parameters=[
            inline_serializer(
                name="SourceSerializer",
                fields={
                    "source": serializers.ChoiceField(choices=PAYMENT_PROVIDERS.choices)
                },
            ),
        ],
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request)


class OrganizationSettingViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing OrganizationSettings.
    """

    serializer_class = OrganizationSettingSerializer
    permission_classes = [IsAuthenticated & ValidOrganization]
    http_method_names = ["get", "head", "patch"]
    lookup_field = "setting_id"
    queryset = OrganizationSetting.objects.all()

    def get_queryset(self):
        filter_kwargs = {"organization": self.request.organization}
        setting_name = self.request.query_params.get("setting_name")
        if setting_name:
            filter_kwargs["setting_name"] = setting_name
        setting_group = self.request.query_params.get("setting_group")
        if setting_group:
            filter_kwargs["setting_group"] = setting_group
        return OrganizationSetting.objects.filter(**filter_kwargs)


class PricingUnitViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):
    """
    A simple ViewSet for viewing and editing PricingUnits.
    """

    serializer_class = PricingUnitSerializer
    permission_classes = [IsAuthenticated & ValidOrganization]
    http_method_names = ["get", "post", "head"]

    def get_queryset(self):
        organization = self.request.organization
        return PricingUnit.objects.filter(organization=organization)

    def perform_create(self, serializer):
        serializer.save(organization=self.request.organization)

    def get_serializer_context(self):
        context = super(PricingUnitViewSet, self).get_serializer_context()
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
    """
    A simple ViewSet for viewing and editing OrganizationSettings.
    """

    permission_classes = [IsAuthenticated & ValidOrganization]
    http_method_names = ["get", "patch", "head"]
    permission_classes_per_method = {
        "list": [IsAuthenticated & ValidOrganization],
        "partial_update": [IsAuthenticated & ValidOrganization],
    }
    lookup_field = "organization_id"
    queryset = Organization.objects.all()

    def get_queryset(self):
        organization = self.request.organization
        return Organization.objects.filter(pk=organization.pk)

    def get_object(self):
        queryset = self.get_queryset()
        obj = queryset.first()
        return obj

    def get_serializer_class(self):
        if self.action == "partial_update":
            return OrganizationUpdateSerializer
        return OrganizationSerializer

    def get_serializer_context(self):
        context = super(OrganizationViewSet, self).get_serializer_context()
        organization = self.request.organization
        user = self.request.user
        context.update({"organization": organization, "user": user})
        return context


class CustomerBalanceAdjustmentViewSet(api_views.CustomerBalanceAdjustmentViewSet):
    pass
