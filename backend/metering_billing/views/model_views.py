from datetime import datetime

import posthog
from django.db import IntegrityError
from django.db.models import Count, Q
from lotus.settings import POSTHOG_PERSON
from metering_billing.billable_metrics import METRIC_HANDLER_MAP
from metering_billing.exceptions import DuplicateCustomerID
from metering_billing.models import (
    Alert,
    Backtest,
    BillableMetric,
    BillingPlan,
    Customer,
    Feature,
    Invoice,
    PlanComponent,
    Subscription,
    User,
)
from metering_billing.permissions import HasUserAPIKey
from metering_billing.serializers.model_serializers import (
    AlertSerializer,
    BacktestCreateSerializer,
    BacktestDetailSerializer,
    BacktestSummarySerializer,
    BillableMetricSerializer,
    BillingPlanReadSerializer,
    BillingPlanSerializer,
    CustomerSerializer,
    FeatureSerializer,
    InvoiceSerializer,
    PlanComponentReadSerializer,
    PlanComponentSerializer,
    SubscriptionReadSerializer,
    SubscriptionSerializer,
    UserSerializer,
)
from metering_billing.tasks import run_backtest
from metering_billing.utils import INVOICE_STATUS_TYPES, SUB_STATUS_TYPES
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..auth_utils import parse_organization


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
            serializer.save()
        except IntegrityError as e:
            raise DuplicateCustomerID

    def get_serializer_context(self):
        context = super(CustomerViewSet, self).get_serializer_context()
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
        serializer.save(organization=parse_organization(self.request))


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


class PlanComponentViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Plan components.
    """

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "delete"]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return PlanComponentReadSerializer
        else:
            return PlanComponentSerializer

    def get_queryset(self):
        return PlanComponent.objects.all()

    def get_serializer_context(self):
        context = super(PlanComponentViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            organization = parse_organization(self.request)
            posthog.capture(
                POSTHOG_PERSON if POSTHOG_PERSON else organization.company_name,
                event=f"{self.action}_component",
                properties={},
            )
        return response

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))


class BillingPlanViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing BillingPlans.
    """

    permission_classes = [IsAuthenticated | HasUserAPIKey]
    lookup_field = "billing_plan_id"
    http_method_names = [
        "get",
        "post",
        "head",
        "delete",
    ]  # update happens in UpdateBillingPlanView
    permission_classes_per_method = {
        "list": [IsAuthenticated | HasUserAPIKey],
        "retrieve": [IsAuthenticated | HasUserAPIKey],
        "create": [IsAuthenticated],
        "destroy": [IsAuthenticated],
    }

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return BillingPlanReadSerializer
        else:
            return BillingPlanSerializer

    def get_queryset(self):
        organization = parse_organization(self.request)
        qs = (
            BillingPlan.objects.filter(organization=organization)
            .prefetch_related(
                "components",
            )
            .annotate(
                active_subscriptions=Count(
                    "current_billing_plan__pk",
                    filter=Q(current_billing_plan__status=SUB_STATUS_TYPES.ACTIVE),
                )
            )
        )
        return qs

    def get_serializer_context(self):
        context = super(BillingPlanViewSet, self).get_serializer_context()
        organization = parse_organization(self.request)
        context.update({"organization": organization})
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            organization = parse_organization(self.request)
            posthog.capture(
                POSTHOG_PERSON if POSTHOG_PERSON else organization.company_name,
                event=f"{self.action}_plan",
                properties={},
            )
        return response

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        num_sub_plan = Subscription.objects.filter(
            billing_plan=obj, status=SUB_STATUS_TYPES.ACTIVE
        ).count()
        if num_sub_plan > 0:
            return Response(
                data={
                    "message": "Billing Plan has associated active subscriptions. Cannot delete."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        self.perform_destroy(obj)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))


class SubscriptionViewSet(PermissionPolicyMixin, viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Subscriptions.
    """

    permission_classes = [IsAuthenticated | HasUserAPIKey]
    http_method_names = [
        "get",
        "post",
        "head",
    ]
    # update happens in UpdateSubscriptionBillingPlanView
    # delete happens in CancelSubscriptionView
    permission_classes_per_method = {
        "list": [IsAuthenticated | HasUserAPIKey],
        "retrieve": [IsAuthenticated | HasUserAPIKey],
        "create": [IsAuthenticated | HasUserAPIKey],
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
        if serializer.validated_data["start_date"] <= datetime.now().date():
            serializer.validated_data["status"] = SUB_STATUS_TYPES.ACTIVE
        serializer.save(organization=parse_organization(self.request))

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return SubscriptionReadSerializer
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
            ~Q(payment_status=INVOICE_STATUS_TYPES.DRAFT),
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
