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
class SlugRelatedLookupField(serializers.SlugRelatedField):
    def get_queryset(self):
        queryset = self.queryset
        request = self.context.get("request", None)
        organization = parse_organization(request)
        queryset.filter(organization=organization)
        return queryset


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

    customer_id = SlugRelatedLookupField(
        slug_field="customer_id",
        queryset=Customer.objects.all(),
        read_only=False,
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
            "event_name",
            "property_name",
            "aggregation_type",
            "billable_metric_name",
            "aggregation_type",
            "event_type",
            "stateful_aggregation_period",
        )

    def validate(self, data):
        if data["event_type"] == "stateful":
            if not data["stateful_aggregation_period"]:
                raise serializers.ValidationError(
                    "Stateful metric aggregation period is required for stateful aggregation type"
                )
            allowed_agg_types = ["max", "last"]
            if data["aggregation_type"] not in allowed_agg_types:
                raise serializers.ValidationError(
                    f"Stateful aggregation type must be one of {allowed_agg_types}, selected {data['aggregation_type']}"
                )
        elif data["event_type"] == "aggregation":
            allowed_agg_types = ["sum", "count", "unique", "max"]
            if data["aggregation_type"] not in allowed_agg_types:
                raise serializers.ValidationError(
                    f"Aggregation metric aggregation type must be one of {allowed_agg_types}, selected {data['aggregation_type']}"
                )
        return data


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
            "billable_metric_name",
            "free_metric_units",
            "cost_per_batch",
            "metric_units_per_batch",
            "max_metric_units",
        )

    billable_metric_name = SlugRelatedLookupField(
        slug_field="billable_metric_name",
        queryset=BillableMetric.objects.all(),
        read_only=False,
        source="billable_metric",
    )


class PlanComponentReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanComponent
        fields = (
            "billable_metric",
            "free_metric_units",
            "cost_per_batch",
            "metric_units_per_batch",
            "max_metric_units",
        )

    billable_metric = BillableMetricSerializer()


## BILLING PLAN
class BillingPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingPlan
        fields = (
            "currency",
            "interval",
            "flat_rate",
            "pay_in_advance",
            "billing_plan_id",
            "name",
            "description",
            "components",
            "features",
        )

    components = PlanComponentSerializer(many=True, allow_null=True, required=False)
    features = FeatureSerializer(many=True, allow_null=True, required=False)

    def create(self, validated_data):
        components_data = validated_data.pop("components", [])
        features_data = validated_data.pop("features", [])
        billing_plan = BillingPlan.objects.create(**validated_data)
        for component_data in components_data:
            pc, _ = PlanComponent.objects.get_or_create(**component_data)
            billing_plan.components.add(pc)
        for feature_data in features_data:
            f, _ = Feature.objects.get_or_create(**feature_data)
            billing_plan.features.add(f)
        billing_plan.save()
        return billing_plan


class BillingPlanUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingPlan
        fields = (
            "currency",
            "flat_rate",
            "pay_in_advance",
            "billing_plan_id",
            "name",
            "description",
            "components",
            "features",
        )

    components = PlanComponentSerializer(many=True, allow_null=True, required=False)
    features = FeatureSerializer(many=True, allow_null=True, required=False)

    def update(self, instance, validated_data):
        instance.currency = validated_data.get("currency", instance.currency)
        instance.flat_rate = validated_data.get("flat_rate", instance.content)
        instance.pay_in_advance = validated_data.get(
            "pay_in_advance", instance.pay_in_advance
        )
        instance.billing_plan_id = validated_data.get(
            "billing_plan_id", instance.billing_plan_id
        )
        instance.name = validated_data.get("name", instance.name)
        instance.description = validated_data.get("description", instance.description)
        # deal w many to many
        components_data = validated_data.get("components", [])
        features_data = validated_data.get("features", [])
        instance.components.clear()
        instance.features.clear()
        for component_data in components_data:
            pc, _ = PlanComponent.objects.get_or_create(**component_data)
            instance.components.add(pc)
        for feature_data in features_data:
            f, _ = Feature.objects.get_or_create(**feature_data)
            instance.features.add(f)
        instance.save()
        return instance


class BillingPlanReadSerializer(BillingPlanSerializer):
    class Meta(BillingPlanSerializer.Meta):
        fields = BillingPlanSerializer.Meta.fields + ("time_created",)

    components = PlanComponentReadSerializer(many=True)
    time_created = serializers.SerializerMethodField()

    def get_time_created(self, obj) -> datetime.date:
        return str(obj.time_created.date())


## SUBSCRIPTION


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
