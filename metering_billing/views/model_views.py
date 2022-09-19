from datetime import datetime
from msilib.schema import Error

from django.db import IntegrityError
from metering_billing.exceptions import DuplicateCustomerID
from metering_billing.models import (
    BillableMetric,
    BillingPlan,
    Customer,
    Invoice,
    PlanComponent,
    Subscription,
    User,
    Alert,
)
from metering_billing.permissions import HasUserAPIKey
from metering_billing.serializers.model_serializers import (
    BillableMetricSerializer,
    BillingPlanReadSerializer,
    BillingPlanSerializer,
    CustomerSerializer,
    InvoiceSerializer,
    PlanComponentReadSerializer,
    PlanComponentSerializer,
    SubscriptionReadSerializer,
    SubscriptionSerializer,
    UserSerializer,
    AlertSerializer,
)
from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticated

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
            serializer.save(organization=parse_organization(self.request))
        except IntegrityError as e:
            raise DuplicateCustomerID


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


class BillingPlanViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing BillingPlans.
    """

    permission_classes = [IsAuthenticated | HasUserAPIKey]
    lookup_field = "billing_plan_id"

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return BillingPlanReadSerializer
        else:
            return BillingPlanSerializer

    def get_queryset(self):
        organization = parse_organization(self.request)
        return BillingPlan.objects.filter(organization=organization).prefetch_related(
            "components"
        )

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))


class SubscriptionViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Subscriptions.
    """

    permission_classes = [IsAuthenticated | HasUserAPIKey]

    def get_queryset(self):
        organization = parse_organization(self.request)
        return Subscription.objects.filter(organization=organization)

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return SubscriptionReadSerializer
        else:
            return SubscriptionSerializer


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
