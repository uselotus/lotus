from datetime import datetime

import posthog
from django.db import IntegrityError
from django.db.models import Count, Q
from metering_billing.exceptions import DuplicateCustomerID
from metering_billing.models import (
    Alert,
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
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..auth_utils import parse_organization


class AlertViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows alerts to be viewed or edited.
    """

    queryset = Alert.objects.all()
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        organization = parse_organization(self.request)
        return super().get_queryset().filter(organization=organization)

    def perform_create(self, serializer):
        organization = parse_organization(self.request)
        serializer.save(organization=organization)


class UserViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Users.
    """

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        organization = parse_organization(self.request)
        return User.objects.filter(organization=organization)

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))


class CustomerViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Customers.
    """

    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated | HasUserAPIKey]
    lookup_field = "customer_id"

    def get_queryset(self):
        organization = parse_organization(self.request)
        return Customer.objects.filter(organization=organization)

    def perform_create(self, serializer):
        try:
            organization = parse_organization(self.request)
            serializer.save(organization=organization)
        except IntegrityError as e:
            raise DuplicateCustomerID

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            organization = parse_organization(self.request)
            posthog.capture(
                organization.company_name,
                event=f"{self.action}_customer",
                properties={},
            )
        return response


class BillableMetricViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Billable Metrics.
    """

    serializer_class = BillableMetricSerializer
    permission_classes = [IsAuthenticated | HasUserAPIKey]

    def get_queryset(self):
        organization = parse_organization(self.request)
        return BillableMetric.objects.filter(organization=organization)

    def perform_create(self, serializer):
        try:
            serializer.save(organization=parse_organization(self.request))
        except IntegrityError as e:
            raise DuplicateCustomerID

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            organization = parse_organization(self.request)
            posthog.capture(
                organization.company_name,
                event=f"{self.action}_metric",
                properties={},
            )
        return response


class FeatureViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Features.
    """

    serializer_class = FeatureSerializer
    permission_classes = [IsAuthenticated | HasUserAPIKey]

    def get_queryset(self):
        return Feature.objects.all()

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            organization = parse_organization(self.request)
            posthog.capture(
                organization.company_name,
                event=f"{self.action}_feature",
                properties={},
            )
        return response


class PlanComponentViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Plan components.
    """

    permission_classes = [IsAuthenticated | HasUserAPIKey]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return PlanComponentReadSerializer
        else:
            return PlanComponentSerializer

    def get_queryset(self):
        return PlanComponent.objects.all()

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            organization = parse_organization(self.request)
            posthog.capture(
                organization.company_name,
                event=f"{self.action}_component",
                properties={},
            )
        return response


class BillingPlanViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing BillingPlans.
    """

    permission_classes = [IsAuthenticated | HasUserAPIKey]
    lookup_field = "billing_plan_id"
    http_method_names = ["get", "post", "head", "delete"]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return BillingPlanReadSerializer
        else:
            return BillingPlanSerializer

    def get_queryset(self):
        organization = parse_organization(self.request)
        return (
            BillingPlan.objects.filter(organization=organization)
            .prefetch_related(
                "components",
            )
            .annotate(
                active_subscriptions=Count(
                    "current_billing_plan__pk", filter=Q(current_billing_plan__status="active")
                )
            )
        )

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))

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

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        num_sub_plan = Subscription.objects.filter(
            billing_plan=obj, status="active"
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


class SubscriptionViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Subscriptions.
    """

    permission_classes = [IsAuthenticated | HasUserAPIKey]
    http_method_names = ["get", "post", "head"]

    def get_queryset(self):
        organization = parse_organization(self.request)
        return Subscription.objects.filter(organization=organization)

    def perform_create(self, serializer):
        if serializer.validated_data["start_date"] <= datetime.now().date():
            serializer.validated_data["status"] = "active"
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
                organization.company_name,
                event=f"{self.action}_subscription",
                properties={},
            )
        return response


class InvoiceViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Invoices.
    """

    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated | HasUserAPIKey]

    def get_queryset(self):
        organization = parse_organization(self.request)
        return Invoice.objects.filter(organization=organization)

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if status.is_success(response.status_code):
            organization = parse_organization(self.request)
            posthog.capture(
                organization.company_name,
                event=f"{self.action}_invoice",
                properties={},
            )
        return response
