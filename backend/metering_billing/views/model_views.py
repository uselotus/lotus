import lotus_python
import posthog
from actstream import action
from actstream.models import Action
from django.conf import settings
from django.db.models import Count, Prefetch, Q
from django.db.utils import IntegrityError
from drf_spectacular.utils import extend_schema, inline_serializer
from metering_billing.auth import parse_organization
from metering_billing.exceptions import DuplicateCustomerID, DuplicateMetric
from metering_billing.models import (
    Alert,
    Backtest,
    Customer,
    CustomerBalanceAdjustment,
    Event,
    ExternalPlanLink,
    Feature,
    Invoice,
    Metric,
    OrganizationSetting,
    Plan,
    PlanComponent,
    PlanVersion,
    PriceTier,
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
    ActionSerializer,
    AlertSerializer,
    CustomerDetailSerializer,
    CustomerSerializer,
    EventSerializer,
    ExternalPlanLinkSerializer,
    FeatureSerializer,
    InvoiceSerializer,
    InvoiceUpdateSerializer,
    MetricSerializer,
    OrganizationSettingSerializer,
    PlanDetailSerializer,
    PlanSerializer,
    PlanUpdateSerializer,
    PlanVersionSerializer,
    PlanVersionUpdateSerializer,
    ProductSerializer,
    SubscriptionDetailSerializer,
    SubscriptionSerializer,
    SubscriptionUpdateSerializer,
    UserSerializer,
)
from metering_billing.tasks import run_backtest
from metering_billing.utils import now_utc, now_utc_ts
from metering_billing.utils.enums import (
    INVOICE_STATUS,
    PAYMENT_PROVIDERS,
    PLAN_STATUS,
    PLAN_VERSION_STATUS,
    REPLACE_IMMEDIATELY_TYPE,
    SUBSCRIPTION_STATUS,
)
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

POSTHOG_PERSON = settings.POSTHOG_PERSON


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
        qs = Customer.objects.filter(organization=organization)
        if self.action == "retrieve":
            qs = qs.prefetch_related(
                Prefetch(
                    "customer_subscriptions",
                    queryset=Subscription.objects.filter(
                        organization=organization, status=SUBSCRIPTION_STATUS.ACTIVE
                    ),
                ),
                Prefetch(
                    "customer_subscriptions__billing_plan",
                    queryset=PlanVersion.objects.filter(organization=organization),
                    to_attr="billing_plans",
                ),
            )
        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return CustomerDetailSerializer
        return CustomerSerializer

    def perform_create(self, serializer):
        try:
            serializer.save(organization=parse_organization(self.request))
        except IntegrityError as e:
            raise DuplicateCustomerID

    def get_serializer_context(self):
        context = super(CustomerViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        if self.action == "retrieve":
            customer = self.get_object()
            total_amount_due = customer.get_outstanding_revenue()
            invoices = Invoice.objects.filter(
                ~Q(status=INVOICE_STATUS.DRAFT),
                organization=organization,
                customer=customer,
            )
            balance_adjustments = CustomerBalanceAdjustment.objects.filter(
                customer=customer,
            )
            context.update(
                {
                    "total_amount_due": total_amount_due,
                    "invoices": invoices,
                    "balance_adjustments": balance_adjustments,
                }
            )
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except:
                username = None
            organization = parse_organization(self.request)
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (
                    username if username else organization.company_name + " (API Key)"
                ),
                event=f"{self.action}_customer",
                properties={"organization": organization.company_name},
            )
        return response


class MetricViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Billable Metrics.
    """

    serializer_class = MetricSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "delete"]

    def get_queryset(self):
        organization = parse_organization(self.request)
        return Metric.objects.filter(organization=organization)

    def get_serializer_context(self):
        context = super(MetricViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except:
                username = None
            organization = parse_organization(self.request)
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

    def perform_create(self, serializer):
        try:
            instance = serializer.save(organization=parse_organization(self.request))
        except IntegrityError as e:
            raise DuplicateMetric
        try:
            user = self.request.user
        except:
            user = None
        if user:
            action.send(
                user,
                verb="created",
                action_object=instance,
            )


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
            try:
                username = self.request.user.username
            except:
                username = None
            organization = parse_organization(self.request)
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
            try:
                username = self.request.user.username
            except:
                username = None
            organization = parse_organization(self.request)
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

    def perform_create(self, serializer):
        try:
            user = self.request.user
        except:
            user = None
        instance = serializer.save(
            organization=parse_organization(self.request), created_by=user
        )
        if user:
            action.send(
                user,
                verb="created",
                action_object=instance,
                target=instance.plan,
            )

    def perform_update(self, serializer):
        instance = serializer.save()
        try:
            user = self.request.user
        except:
            user = None
        user = self.request.user
        if user:
            if instance.status == PLAN_VERSION_STATUS.ACTIVE:
                action.send(
                    user,
                    verb="activated",
                    action_object=instance,
                    target=instance.plan,
                )
            elif instance.status == PLAN_VERSION_STATUS.ARCHIVED:
                action.send(
                    user,
                    verb="archived",
                    action_object=instance,
                    target=instance.plan,
                )


class PlanViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
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
                        ~Q(status=PLAN_VERSION_STATUS.ARCHIVED),
                        organization=organization,
                    ).annotate(
                        active_subscriptions=Count(
                            "bp_subscription",
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
            try:
                username = self.request.user.username
            except:
                username = None
            organization = parse_organization(self.request)
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (
                    username if username else organization.company_name + " (API Key)"
                ),
                event=f"{self.action}_plan",
                properties={"organization": organization.company_name},
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
        instance = serializer.save(
            organization=parse_organization(self.request), created_by=user
        )
        if user:
            action.send(
                user,
                verb="created",
                action_object=instance,
            )

    def perform_update(self, serializer):
        instance = serializer.save()
        try:
            user = self.request.user
        except:
            user = None
        user = self.request.user
        if user:
            if instance.status == PLAN_STATUS.ARCHIVED:
                action.send(
                    user,
                    verb="archived",
                    action_object=instance,
                )


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
        "partial_update": [IsAuthenticated | HasUserAPIKey],
    }

    def get_serializer_context(self):
        context = super(SubscriptionViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context

    def get_queryset(self):
        organization = parse_organization(self.request)
        qs = (
            Subscription.objects.filter(
                organization=organization, status=SUBSCRIPTION_STATUS.ACTIVE
            )
            .select_related("customer")
            .select_related("billing_plan")
        )
        if self.action == "retrieve":
            qs = qs.prefetch_related(
                Prefetch(
                    "billing_plan__plan_components",
                    queryset=PlanComponent.objects.all(),
                )
            ).prefetch_related(
                Prefetch(
                    "billing_plan__plan_components__tiers",
                    queryset=PriceTier.objects.all(),
                )
            )
        return qs

    def perform_create(self, serializer):
        if serializer.validated_data["start_date"] <= now_utc():
            serializer.validated_data["status"] = SUBSCRIPTION_STATUS.ACTIVE
        instance = serializer.save(organization=parse_organization(self.request))
        try:
            user = self.request.user
            action.send(
                user,
                verb="subscribed",
                action_object=instance.customer,
                target=instance.billing_plan,
            )
        except:
            pass

    def get_serializer_class(self):
        if self.action == "partial_update":
            return SubscriptionUpdateSerializer
        elif self.action == "retrieve":
            return SubscriptionDetailSerializer
        else:
            return SubscriptionSerializer

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            try:
                username = self.request.user.username
            except:
                username = None
            organization = parse_organization(self.request)
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (
                    username if username else organization.company_name + " (API Key)"
                ),
                event=f"{self.action}_subscription",
                properties={"organization": organization.company_name},
            )
        return response

    def perform_update(self, serializer):
        instance = serializer.save()
        try:
            user = self.request.user
        except:
            user = None
        user = self.request.user
        if user:
            if instance.status == SUBSCRIPTION_STATUS.ENDED:
                action.send(
                    user,
                    verb="canceled",
                    action_object=instance.billing_plan,
                    target=instance.customer,
                )
            elif (
                serializer.validated_data.get("replace_immediately_type")
                == REPLACE_IMMEDIATELY_TYPE.CHANGE_SUBSCRIPTION_PLAN
            ):
                action.send(
                    user,
                    verb="switched to",
                    action_object=instance.billing_plan,
                    target=instance.customer,
                )


class InvoiceViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Invoices.
    """

    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "head"]
    lookup_field = "invoice_id"
    permission_classes_per_method = {
        "list": [IsAuthenticated],
        "retrieve": [IsAuthenticated],
        "partial_update": [IsAuthenticated],
    }

    def get_queryset(self):
        organization = parse_organization(self.request)
        return Invoice.objects.filter(
            ~Q(payment_status=INVOICE_STATUS.DRAFT),
            organization=organization,
        )

    def get_serializer_class(self):
        if self.action == "partial_update":
            return InvoiceUpdateSerializer
        return InvoiceSerializer

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
            try:
                username = self.request.user.username
            except:
                username = None
            organization = parse_organization(self.request)
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (
                    username if username else organization.company_name + " (API Key)"
                ),
                event=f"{self.action}_invoice",
                properties={"organization": organization.company_name},
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
            try:
                username = self.request.user.username
            except:
                username = None
            organization = parse_organization(self.request)
            posthog.capture(
                POSTHOG_PERSON
                if POSTHOG_PERSON
                else (
                    username if username else organization.company_name + " (API Key)"
                ),
                event=f"{self.action}_alert",
                properties={"organization": organization.company_name},
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
            try:
                username = self.request.user.username
            except:
                username = None
            organization = parse_organization(self.request)
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
            try:
                username = self.request.user.username
            except:
                username = None
            organization = parse_organization(self.request)
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
        organization = parse_organization(self.request)
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
    permission_classes = [IsAuthenticated]
    http_method_names = [
        "get",
        "head",
    ]

    def get_queryset(self):
        organization = parse_organization(self.request)
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
    permission_classes = [IsAuthenticated]
    lookup_field = "external_plan_id"
    http_method_names = ["post", "head", "delete"]

    def get_queryset(self):
        filter_kwargs = {"organization": parse_organization(self.request)}
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
            organization = parse_organization(self.request)
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
        serializer.save(organization=parse_organization(self.request))

    def get_serializer_context(self):
        context = super(ExternalPlanLinkViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
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
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "patch"]
    lookup_field = "setting_id"

    def get_queryset(self):
        filter_kwargs = {"organization": parse_organization(self.request)}
        setting_name = self.request.query_params.get("setting_name")
        if setting_name:
            filter_kwargs["setting_name"] = setting_name
        setting_group = self.request.query_params.get("setting_group")
        if setting_group:
            filter_kwargs["setting_group"] = setting_group
        return OrganizationSetting.objects.filter(**filter_kwargs)

    @extend_schema(
        parameters=[
            inline_serializer(
                name="SettingFilterSerializer",
                fields={
                    "setting_name": serializers.CharField(required=False),
                    "setting_group": serializers.CharField(required=False),
                },
            ),
        ],
    )
    def list(self, request):
        return super().list(request)
