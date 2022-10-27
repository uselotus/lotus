import datetime

import posthog
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Count, Prefetch, Q
from django.db.utils import IntegrityError
from metering_billing.auth import parse_organization
from metering_billing.exceptions import DuplicateBillableMetric, DuplicateCustomerID
from metering_billing.models import (
    Alert,
    Backtest,
    BillableMetric,
    Customer,
    Event,
    Feature,
    Invoice,
    Plan,
    PlanVersion,
    Product,
    Subscription,
    User,
)
from metering_billing.permissions import HasUserAPIKey
from metering_billing.serializers.backtest_serializers import (
    BacktestCreateSerializer,
    BacktestDetailSerializer,
    BacktestSummarySerializer,
)
from metering_billing.serializers.model_serializers import (
    AlertSerializer,
    BillableMetricSerializer,
    CustomerSerializer,
    EventSerializer,
    FeatureSerializer,
    InvoiceSerializer,
    PlanDetailSerializer,
    PlanSerializer,
    PlanUpdateSerializer,
    PlanVersionSerializer,
    PlanVersionUpdateSerializer,
    ProductSerializer,
    SubscriptionSerializer,
    SubscriptionUpdateSerializer,
    UserSerializer,
)
from metering_billing.tasks import run_backtest
from metering_billing.utils import now_utc
from metering_billing.utils.enums import (
    INVOICE_STATUS,
    PLAN_STATUS,
    PLAN_VERSION_STATUS,
    SUBSCRIPTION_STATUS,
)
from rest_framework import mixins, status, viewsets
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

POSTHOG_PERSON = settings.POSTHOG_PERSON


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


class WebhookViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    API endpoint that allows alerts to be viewed or edited.
    """

    queryset = Alert.objects.filter(type="webhook")
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "delete"]

    def get_queryset(self):
        organization = parse_organization(self.request)
        return super().get_queryset().filter(organization=organization)

    def get_serializer_context(self):
        context = super(WebhookViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))


class CursorSetPagination(CursorPagination):
    page_size = 20
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
    permission_classes = [IsAuthenticated]
    http_method_names = [
        "get",
        "head",
    ]

    def get_queryset(self):
        now = now_utc()
        organization = parse_organization(self.request)
        return (
            super()
            .get_queryset()
            .filter(organization=organization, time_created__lt=now)
        )

    def get_serializer_context(self):
        context = super(EventViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context


class UserViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Users.
    """

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head"]

    def get_queryset(self):
        organization = parse_organization(self.request)
        return User.objects.filter(organization=organization)

    def get_serializer_context(self):
        context = super(UserViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))


class CustomerViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Customers.
    """

    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated | HasUserAPIKey]
    lookup_field = "customer_id"
    http_method_names = ["get", "post", "head", "delete"]
    permission_classes_per_method = {
        "list": [IsAuthenticated | HasUserAPIKey],
        "retrieve": [IsAuthenticated | HasUserAPIKey],
        "create": [IsAuthenticated | HasUserAPIKey],
        "destroy": [IsAuthenticated],
    }

    def get_queryset(self):
        organization = parse_organization(self.request)
        return Customer.objects.filter(organization=organization)

    def perform_create(self, serializer):
        try:
            serializer.save(organization=parse_organization(self.request))
        except IntegrityError as e:
            raise DuplicateCustomerID

    def get_serializer_context(self):
        context = super(CustomerViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            organization = parse_organization(self.request)
            posthog.capture(
                POSTHOG_PERSON if POSTHOG_PERSON else organization.company_name,
                event=f"{self.action}_customer",
                properties={},
            )
        return response


class BillableMetricViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Billable Metrics.
    """

    serializer_class = BillableMetricSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "delete"]

    def get_queryset(self):
        organization = parse_organization(self.request)
        return BillableMetric.objects.filter(organization=organization)

    def get_serializer_context(self):
        context = super(BillableMetricViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            organization = parse_organization(self.request)
            posthog.capture(
                POSTHOG_PERSON if POSTHOG_PERSON else organization.company_name,
                event=f"{self.action}_metric",
                properties={},
            )
        return response

    def perform_create(self, serializer):
        try:
            serializer.save(organization=parse_organization(self.request))
        except IntegrityError as e:
            raise DuplicateBillableMetric


class FeatureViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Features.
    """

    serializer_class = FeatureSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "delete"]
    permission_classes_per_method = {
        "list": [IsAuthenticated | HasUserAPIKey],
        "retrieve": [IsAuthenticated | HasUserAPIKey],
        "create": [IsAuthenticated | HasUserAPIKey],
        "destroy": [IsAuthenticated],
    }

    def get_queryset(self):
        organization = parse_organization(self.request)
        return Feature.objects.filter(organization=organization)

    def get_serializer_context(self):
        context = super(FeatureViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            organization = parse_organization(self.request)
            posthog.capture(
                POSTHOG_PERSON if POSTHOG_PERSON else organization.company_name,
                event=f"{self.action}_feature",
                properties={},
            )
        return response

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))


class PlanVersionViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing PlanVersions.
    """

    permission_classes = [IsAuthenticated | HasUserAPIKey]
    serializer_class = PlanVersionSerializer
    lookup_field = "version_id"
    http_method_names = [
        "post",
        "head",
        "patch",
    ]
    permission_classes_per_method = {
        "create": [IsAuthenticated],
        "partial_update": [IsAuthenticated],
    }

    def get_serializer_class(self):
        if self.action == "partial_update":
            return PlanVersionUpdateSerializer
        return PlanVersionSerializer

    def get_queryset(self):
        organization = parse_organization(self.request)
        qs = PlanVersion.objects.filter(
            organization=organization,
        )
        return qs

    def get_serializer_context(self):
        context = super(PlanVersionViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        try:
            user = self.request.user
        except:
            user = None
        context.update({"organization": organization, "user": user})
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            organization = parse_organization(self.request)
            posthog.capture(
                POSTHOG_PERSON if POSTHOG_PERSON else organization.company_name,
                event=f"{self.action}_plan_version",
                properties={},
            )
        return response

    def perform_create(self, serializer):
        try:
            user = self.request.user
        except:
            user = None
        serializer.save(organization=parse_organization(self.request), created_by=user)


class PlanViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Products.
    """

    serializer_class = PlanSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "plan_id"
    http_method_names = ["get", "post", "patch", "head"]
    queryset = Plan.objects.all()
    permission_classes_per_method = {
        "list": [IsAuthenticated | HasUserAPIKey],
        "retrieve": [IsAuthenticated | HasUserAPIKey],
        "create": [IsAuthenticated],
        "partial_update": [IsAuthenticated],
    }

    def get_queryset(self):
        organization = parse_organization(self.request)
        qs = Plan.objects.filter(organization=organization, status=PLAN_STATUS.ACTIVE)
        if self.action == "retrieve":
            qs = qs.prefetch_related(
                Prefetch(
                    "versions",
                    queryset=PlanVersion.objects.filter(
                        organization=organization,
                        status__in=[
                            PLAN_VERSION_STATUS.ACTIVE,
                            PLAN_VERSION_STATUS.GRANDFATHERED,
                            PLAN_VERSION_STATUS.RETIRING,
                            PLAN_VERSION_STATUS.INACTIVE,
                        ],
                    ).annotate(
                        active_subscriptions=Count(
                            "bp_subscriptions",
                            filter=Q(
                                bp_subscription__status=SUBSCRIPTION_STATUS.ACTIVE
                            ),
                        )
                    ),
                )
            )
        return qs

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            organization = parse_organization(self.request)
            posthog.capture(
                organization.company_name,
                event=f"{self.action}_plan",
                properties={},
            )
        return response

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PlanDetailSerializer
        elif self.action == "partial_update":
            return PlanUpdateSerializer
        return PlanSerializer

    def get_serializer_context(self):
        context = super(PlanViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        try:
            user = self.request.user
        except:
            user = None
        context.update({"organization": organization, "user": user})
        return context

    def perform_create(self, serializer):
        try:
            user = self.request.user
        except:
            user = None
        serializer.save(organization=parse_organization(self.request), created_by=user)


class SubscriptionViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Subscriptions.
    """

    permission_classes = [IsAuthenticated | HasUserAPIKey]
    http_method_names = ["get", "post", "head", "patch"]
    lookup_field = "subscription_id"
    permission_classes_per_method = {
        "list": [IsAuthenticated | HasUserAPIKey],
        "retrieve": [IsAuthenticated | HasUserAPIKey],
        "create": [IsAuthenticated | HasUserAPIKey],
        "partial_update": [IsAuthenticated],
    }

    def get_serializer_context(self):
        context = super(SubscriptionViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context

    def get_queryset(self):
        organization = parse_organization(self.request)
        return Subscription.objects.filter(organization=organization)

    def perform_create(self, serializer):
        if serializer.validated_data["start_date"] <= now_utc():
            serializer.validated_data["status"] = SUBSCRIPTION_STATUS.ACTIVE
        serializer.save(organization=parse_organization(self.request))

    def get_serializer_class(self):
        if self.action == "partial_update":
            return SubscriptionUpdateSerializer
        else:
            return SubscriptionSerializer

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            organization = parse_organization(self.request)
            posthog.capture(
                POSTHOG_PERSON if POSTHOG_PERSON else organization.company_name,
                event=f"{self.action}_subscription",
                properties={},
            )
        return response


class InvoiceViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Invoices.
    """

    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head"]
    permission_classes_per_method = {
        "list": [IsAuthenticated],
        "retrieve": [IsAuthenticated],
        "create": [IsAuthenticated],
        "destroy": [IsAuthenticated],
    }

    def get_queryset(self):
        organization = parse_organization(self.request)
        return Invoice.objects.filter(
            ~Q(payment_status=INVOICE_STATUS.DRAFT),
            organization=organization,
        )

    def get_serializer_context(self):
        context = super(InvoiceViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            organization = parse_organization(self.request)
            posthog.capture(
                POSTHOG_PERSON if POSTHOG_PERSON else organization.company_name,
                event=f"{self.action}_invoice",
                properties={},
            )
        return response


class AlertViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Alerts.
    """

    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated | HasUserAPIKey]
    http_method_names = ["get", "post", "head", "put", "delete"]

    def get_queryset(self):
        organization = parse_organization(self.request)
        return Alert.objects.filter(organization=organization)

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            organization = parse_organization(self.request)
            posthog.capture(
                organization.company_name,
                event=f"{self.action}_alert",
                properties={},
            )
        return response

    def get_serializer_context(self):
        context = super(AlertViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context


class BacktestViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Backtests.
    """

    permission_classes = [IsAuthenticated]
    lookup_field = "backtest_id"
    http_method_names = ["get", "post", "head", "delete"]
    permission_classes_per_method = {
        "list": [IsAuthenticated | HasUserAPIKey],
        "retrieve": [IsAuthenticated | HasUserAPIKey],
        "create": [IsAuthenticated | HasUserAPIKey],
        "destroy": [IsAuthenticated],
    }

    def get_serializer_class(self):
        if self.action == "list":
            return BacktestSummarySerializer
        elif self.action == "retrieve":
            return BacktestDetailSerializer
        else:
            return BacktestCreateSerializer

    def get_queryset(self):
        organization = parse_organization(self.request)
        return Backtest.objects.filter(organization=organization)

    def perform_create(self, serializer):
        backtest_obj = serializer.save(organization=parse_organization(self.request))
        bt_id = backtest_obj.backtest_id
        run_backtest.delay(bt_id)

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            organization = parse_organization(self.request)
            posthog.capture(
                POSTHOG_PERSON if POSTHOG_PERSON else organization.company_name,
                event=f"{self.action}_backtest",
                properties={},
            )
        return response

    def get_serializer_context(self):
        context = super(BacktestViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context


class ProductViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Products.
    """

    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "product_id"
    http_method_names = ["get", "post", "head", "delete"]

    def get_queryset(self):
        organization = parse_organization(self.request)
        return Product.objects.filter(organization=organization)

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            organization = parse_organization(self.request)
            posthog.capture(
                organization.company_name,
                event=f"{self.action}_product",
                properties={},
            )
        return response

    def get_serializer_context(self):
        context = super(ProductViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context
