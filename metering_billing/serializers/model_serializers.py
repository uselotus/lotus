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
    Feature,
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
        fields = (
            "event_name",
            "properties",
            "time_created",
            "idempotency_id",
            "customer_id",
        )

    customer_id = serializers.SlugRelatedField(
        read_only=True,
        slug_field="customer_id",
        source="customer",
    )


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
            "billable_metric_name",
        )


## FEATURE
class FeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feature
        fields = (
            "feature_name",
            "feature_description",
        )


## PLAN COMPONENT
class PlanComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanComponent
        fields = (
            "billable_metric",
            "free_metric_quantity",
            "cost_per_batch",
            "metric_units_per_batch",
            "max_metric_units",
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
            "customer_id",
            "billing_plan_id",
            "start_date",
            "end_date",
            "status",
            "auto_renew",
            "is_new",
            "subscription_uid",
        )

    customer_id = SlugRelatedLookupField(
        slug_field="customer_id",
        queryset=Customer.objects.all(),
        read_only=False,
        source="customer",
    )
    billing_plan_id = SlugRelatedLookupField(
        slug_field="billing_plan_id",
        queryset=BillingPlan.objects.all(),
        read_only=False,
        source="billing_plan",
    )
    end_date = serializers.DateField(required=False)
    status = serializers.CharField(required=False)
    auto_renew = serializers.BooleanField(required=False)
    is_new = serializers.BooleanField(required=False)
    subscription_uid = serializers.CharField(required=False)


class SubscriptionReadSerializer(SubscriptionSerializer):
    class Meta:
        model = Subscription
        fields = (
            "customer",
            "billing_plan",
            "start_date",
            "end_date",
            "status",
        )

    customer = CustomerSerializer()
    billing_plan = BillingPlanReadSerializer()


## INVOICE
class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = "__all__"
