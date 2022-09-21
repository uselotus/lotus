import datetime
from decimal import Decimal

from django.db.models import Q
from metering_billing.auth_utils import parse_organization
from metering_billing.exceptions import OverlappingSubscription
from metering_billing.models import (
    Alert,
    APIToken,
    BillableMetric,
    BillingPlan,
    Customer,
    Event,
    Invoice,
    Organization,
    PlanComponent,
    Subscription,
    User,
)
from metering_billing.permissions import HasUserAPIKey
from rest_framework import serializers

## EXTRANEOUS SERIALIZERS


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = (
            "id",
            "company_name",
            "payment_plan",
            "stripe_id",
        )


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = "__all__"  # allowed because we never send back, just take in


class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = (
            "type",
            "webhook_url",
            "name",
        )


## USER
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("username", "password")


## CUSTOMER
class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = (
            "name",
            "customer_id",
            "balance",
        )


## BILLABLE METRIC
class BillableMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillableMetric
        fields = (
            "id",
            "event_name",
            "property_name",
            "aggregation_type",
            "carries_over",
            "metric_name",  # read-only b/c MethodField, ignored in deserialization
        )

    metric_name = serializers.SerializerMethodField()

    def get_metric_name(self, obj) -> str:
        return str(obj)


## PLAN COMPONENT
class PlanComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanComponent
        fields = (
            "billable_metric",
            "free_metric_quantity",
            "cost_per_metric",
            "metric_amount_per_cost",
            "max_amount",
        )


class PlanComponentReadSerializer(PlanComponentSerializer):
    class Meta(PlanComponentSerializer.Meta):
        fields = PlanComponentSerializer.Meta.fields + ("id",)

    billable_metric = BillableMetricSerializer()


## BILLING PLAN
class BillingPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingPlan
        fields = (
            "time_created",
            "currency",
            "interval",
            "flat_rate",
            "pay_in_advance",
            "billing_plan_id",
            "name",
            "description",
            "components",
        )

    components = PlanComponentSerializer(many=True)

    def create(self, validated_data):
        components_data = validated_data.pop("components")
        billing_plan = BillingPlan.objects.create(**validated_data)
        for component_data in components_data:
            pc, _ = PlanComponent.objects.get_or_create(**component_data)
            billing_plan.components.add(pc)
            billing_plan.save()
        return billing_plan


class BillingPlanReadSerializer(BillingPlanSerializer):
    class Meta(BillingPlanSerializer.Meta):
        fields = BillingPlanSerializer.Meta.fields + ("id",)

    components = PlanComponentReadSerializer(many=True)
    time_created = serializers.SerializerMethodField()

    def get_time_created(self, obj) -> datetime.date:
        return str(obj.time_created.date())


## SUBSCRIPTION
class SlugRelatedLookupField(serializers.SlugRelatedField):
    def get_queryset(self):
        queryset = self.queryset
        request = self.context.get("request", None)
        organization = parse_organization(request)
        queryset.filter(organization=organization)
        return queryset


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = (
            "customer",
            "billing_plan",
            "start_date",
            "status",
        )

    customer = SlugRelatedLookupField(
        slug_field="customer_id", queryset=Customer.objects.all(), read_only=False
    )
    billing_plan = SlugRelatedLookupField(
        slug_field="billing_plan_id",
        queryset=BillingPlan.objects.all(),
        read_only=False,
    )


class SubscriptionReadSerializer(SubscriptionSerializer):
    class Meta(SubscriptionSerializer.Meta):
        fields = SubscriptionSerializer.Meta.fields + ("id",)

    customer = CustomerSerializer()
    billing_plan = BillingPlanReadSerializer()


## INVOICE
class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = "__all__"
