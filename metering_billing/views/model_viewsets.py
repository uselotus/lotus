from datetime import datetime

from django.db import IntegrityError
from metering_billing import serializers
from metering_billing.exceptions import DuplicateCustomerID
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
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from ..utils import parse_organization


class UserViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing Users.
    """

    serializer_class = serializers.UserSerializer
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

    serializer_class = serializers.CustomerSerializer
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

    serializer_class = serializers.BillableMetricSerializer
    permission_classes = [IsAuthenticated | HasUserAPIKey]

    def get_queryset(self):
        organization = parse_organization(self.request)
        return BillableMetric.objects.filter(organization=organization)

    def perform_create(self, serializer):
        try:
            serializer.save(organization=parse_organization(self.request))
        except IntegrityError as e:
            raise DuplicateCustomerID


class BillingPlanViewSet(viewsets.ModelViewSet):
    """
    A simple ViewSet for viewing and editing BillingPlans.
    """

    permission_classes = [IsAuthenticated | HasUserAPIKey]

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return serializers.BillingPlanReadSerializer
        else:
            return serializers.BillingPlanSerializer

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

    serializer_class = serializers.PlanComponentSerializer
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

    serializer_class = serializers.SubscriptionSerializer
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

    serializer_class = serializers.InvoiceSerializer
    permission_classes = [IsAuthenticated | HasUserAPIKey]

    def get_queryset(self):
        organization = parse_organization(self.request)
        return Invoice.objects.filter(organization=organization)

    def perform_create(self, serializer):
        serializer.save(organization=parse_organization(self.request))
