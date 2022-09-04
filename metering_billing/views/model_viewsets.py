from datetime import datetime

from metering_billing.models import (
    BillableMetric,
    BillingPlan,
    Customer,
    Invoice,
    PlanComponent,
    Subscription,
    User,
)
from metering_billing.permissions import HasUserAPIKey
from metering_billing.serializers import (
    BillableMetricSerializer,
    BillingPlanSerializer,
    CustomerSerializer,
    InvoiceSerializer,
    PlanComponentSerializer,
    SubscriptionSerializer,
    UserSerializer,
)
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from ..utils import parse_organization


class UserViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Users.
    """

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated | HasUserAPIKey]

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
        serializer.save(organization=parse_organization(self.request))


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
        serializer.save(organization=parse_organization(self.request))


class BillingPlanViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing BillingPlans.
    """

    serializer_class = BillingPlanSerializer
    permission_classes = [IsAuthenticated | HasUserAPIKey]

    def get_queryset(self):
        organization = parse_organization(self.request)
        return BillingPlan.objects.filter(organization=organization).prefetch_related(
            "components"
        )

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))


class PlanComponentViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Plan components.
    """

    serializer_class = PlanComponentSerializer
    permission_classes = [IsAuthenticated | HasUserAPIKey]

    def get_queryset(self):
        organization = parse_organization(self.request)
        return PlanComponent.objects.filter(organization=organization)

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))


class SubscriptionViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Subscriptions.
    """

    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated | HasUserAPIKey]

    def get_queryset(self):
        organization = parse_organization(self.request)
        return Subscription.objects.filter(organization=organization)

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))


class InvoiceViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Invoicess.
    """

    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated | HasUserAPIKey]

    def get_queryset(self):
        organization = parse_organization(self.request)
        return Invoice.objects.filter(organization=organization)

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))
