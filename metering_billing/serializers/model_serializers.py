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
            "payment_provider_ids",
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
class FilterActiveSubscriptionSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        data = data.filter(status="active")
        return super(FilterActiveSubscriptionSerializer, self).to_representation(data)


class SubscriptionCustomerSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ("billing_plan_name", "end_date", "auto_renew")
        list_serializer_class = FilterActiveSubscriptionSerializer

    billing_plan_name = serializers.CharField(source="billing_plan.name")


class CustomerSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = (
            "customer_name",
            "customer_id",
            "subscriptions",
        )

    subscriptions = SubscriptionCustomerSummarySerializer(
        read_only=True, many=True, source="subscription_set"
    )
    customer_name = serializers.CharField(source="name")


class SubscriptionCustomerDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = (
            "billing_plan_name",
            "subscription_id",
            "start_date",
            "end_date",
            "auto_renew",
            "status",
        )
        list_serializer_class = FilterActiveSubscriptionSerializer

    billing_plan_name = serializers.CharField(source="billing_plan.name")


class CustomerDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = (
            "customer_id",
            "email",
            "balance",
            "billing_address",
            "customer_name",
            "invoices",
            "total_revenue_due",
            "subscriptions",
        )

    customer_name = serializers.CharField(source="name")
    subscriptions = SubscriptionCustomerDetailSerializer(
        read_only=True, many=True, source="subscription_set"
    )
    invoices = serializers.SerializerMethodField()
    total_revenue_due = serializers.SerializerMethodField()

    def get_invoices(self, obj) -> list:
        timeline = self.context.get("invoices")
        timeline = InvoiceSerializer(timeline, many=True).data
        return timeline

    def get_total_revenue_due(self, obj) -> float:
        total_revenue_due = float(self.context.get("total_revenue_due"))
        return total_revenue_due


class CustomerWithRevenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ("customer_id", "total_revenue_due")

    total_revenue_due = serializers.SerializerMethodField()

    def get_total_revenue_due(self, obj) -> float:
        total_revenue_due = float(self.context.get("total_revenue_due"))
        return total_revenue_due


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = (
            "customer_name",
            "customer_id",
            "balance",
        )

    customer_name = serializers.CharField(source="name")


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
        org = billing_plan.organization
        for component_data in components_data:
            pc, _ = PlanComponent.objects.get_or_create(**component_data)
            billing_plan.components.add(pc)
        for feature_data in features_data:
            feature_data["organization"] = org
            f, _ = Feature.objects.get_or_create(**feature_data)
            billing_plan.features.add(f)
        billing_plan.save()
        return billing_plan


class BillingPlanReadSerializer(BillingPlanSerializer):
    class Meta(BillingPlanSerializer.Meta):
        fields = BillingPlanSerializer.Meta.fields + (
            "time_created",
            "active_subscriptions",
        )

    components = PlanComponentReadSerializer(many=True)
    time_created = serializers.SerializerMethodField()
    active_subscriptions = serializers.IntegerField()

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
            "subscription_id",
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
    subscription_id = serializers.CharField(required=False)


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
        fields = (
            "cost_due",
            "cost_due_currency",
            "issue_date",
            "payment_status",
            "cust_connected_to_payment_provider",
            "org_connected_to_cust_payment_provider",
            "external_payment_obj_id",
            "line_items",
            "organization",
            "customer",
            "subscription",
        )

    cost_due = serializers.DecimalField(
        max_digits=10, decimal_places=2, source="cost_due.amount"
    )
    cost_due_currency = serializers.CharField(source="cost_due.currency")


class DraftInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = (
            "cost_due",
            "cost_due_currency",
            "cust_connected_to_payment_provider",
            "org_connected_to_cust_payment_provider",
            "line_items",
            "organization",
            "customer",
            "subscription",
        )

    cost_due = serializers.DecimalField(
        max_digits=10, decimal_places=2, source="cost_due.amount"
    )
    cost_due_currency = serializers.CharField(source="cost_due.currency")
