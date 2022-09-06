import datetime
from decimal import Decimal

from rest_framework import serializers

from metering_billing.models import (
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


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = (
            "id",
            "company_name",
            "payment_plan",
            "stripe_id",
        )


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("username", "password")


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = (
            "name",
            "customer_id",
            "balance",
        )
        lookup_field = "customer_id"


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = "__all__"  # allowed because we never send back, just take in


class BillableMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillableMetric
        fields = (
            "id",
            "event_name",
            "property_name",
            "aggregation_type",
            "metric_name",
        )

    metric_name = serializers.SerializerMethodField()

    def get_metric_name(self, obj) -> str:
        return str(obj)


class PlanComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanComponent
        fields = (
            "id",
            "billable_metric",
            "free_metric_quantity",
            "cost_per_metric",
            "metric_amount_per_cost",
        )

    billable_metric = BillableMetricSerializer()

class PlanComponentShallowSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanComponent
        fields = (
            "id",
            "billable_metric",
            "free_metric_quantity",
            "cost_per_metric",
            "metric_amount_per_cost",
        )


class BillingPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingPlan
        fields = (
            "time_created",
            "currency",
            "interval",
            "flat_rate",
            "pay_in_advance",
            "name",
            "description",
            "components",
        )
        
    components = PlanComponentShallowSerializer(many=True)


class BillingPlanReadSerializer(BillingPlanSerializer):
    class Meta:
        model = BillingPlan
        fields = (
            "id",
            "time_created",
            "currency",
            "interval",
            "flat_rate",
            "pay_in_advance",
            "name",
            "description",
            "components",
        )

    components = PlanComponentSerializer(many=True)
    time_created = serializers.SerializerMethodField()

    def get_time_created(self, obj) -> datetime.date:
        return str(obj.time_created.date())


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = (
            "id",
            "customer",
            "billing_plan",
            "start_date",
            "end_date",
            "status",
        )

    customer = CustomerSerializer()
    billing_plan = BillingPlanSerializer()


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = (
            "id",
            "cost_due",
            "issue_date",
            "customer",
            "subscription",
            "status",
            "line_items",
        )

    customer = CustomerSerializer()
    subscription = SubscriptionSerializer()


class CustomerNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ("name",)


class CustomerIDSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ("customer_id",)


class BillingPlanNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingPlan
        fields = ("name",)


class PeriodRequestSerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()


class PeriodComparisonRequestSerializer(serializers.Serializer):
    period_1_start_date = serializers.DateField()
    period_1_end_date = serializers.DateField()
    period_2_start_date = serializers.DateField()
    period_2_end_date = serializers.DateField()


# CUSTOMER USAGE AND REVENUE SERIALIZERS GO HERE
class SubscriptionUsageSerializer(serializers.Serializer):
    class Meta:
        model = Subscription
        fields = ("id", "start_date", "end_date", "status", "billing_plan")

    billing_plan = BillingPlanSerializer()
    usage_revenue_due = serializers.DecimalField(decimal_places=10, max_digits=20)
    flat_revenue_due = serializers.DecimalField(decimal_places=10, max_digits=20)
    total_revenue_due = serializers.DecimalField(decimal_places=10, max_digits=20)


class CustomerRevenueSerializer(serializers.Serializer):
    subscriptions = serializers.ListField(child=serializers.CharField())
    total_revenue_due = serializers.DecimalField(decimal_places=10, max_digits=20)
    customer_name = serializers.CharField()
    customer_id = serializers.CharField()


class CustomerRevenueSummarySerializer(serializers.Serializer):
    customers = CustomerRevenueSerializer(many=True)


# PERIOD SUBSCRIPTION SERIALIZERS GO HERE
class PeriodSubscriptionsResponseSerializer(serializers.Serializer):
    period_1_total_subscriptions = serializers.IntegerField()
    period_1_new_subscriptions = serializers.IntegerField()
    period_2_total_subscriptions = serializers.IntegerField()
    period_2_new_subscriptions = serializers.IntegerField()


# PERIOD METRIC USAGE SERIALIZERS GO HERE
class PeriodMetricUsageRequestSerializer(PeriodRequestSerializer):
    top_n_customers = serializers.IntegerField(required=False)


class DayMetricUsageSerializer(serializers.Serializer):
    date = serializers.DateField()
    customer_usages = serializers.DictField(
        child=serializers.DecimalField(decimal_places=10, max_digits=20)
    )


class PeriodSingleMetricUsageSerializer(serializers.Serializer):
    data = DayMetricUsageSerializer(many=True)
    total_usage = serializers.DecimalField(decimal_places=10, max_digits=20)
    top_n_customers = CustomerNameSerializer(required=False, many=True)
    top_n_customers_usage = serializers.DecimalField(
        decimal_places=10, max_digits=20, required=False
    )


class PeriodMetricUsageResponseSerializer(serializers.Serializer):
    metrics = serializers.DictField(child=PeriodSingleMetricUsageSerializer())


# PERIOD METRIC REVENUE SERIALIZERS GO HERE
class DayMetricRevenueSerializer(serializers.Serializer):
    date = serializers.DateField()
    metric_revenue = serializers.DecimalField(decimal_places=10, max_digits=20)


class PeriodSingleMetricRevenueSerializer(serializers.Serializer):
    metric = serializers.CharField()
    data = DayMetricRevenueSerializer(many=True)
    total_revenue = serializers.DecimalField(decimal_places=10, max_digits=20)


class PeriodMetricRevenueResponseSerializer(serializers.Serializer):
    daily_usage_revenue_period_1 = PeriodSingleMetricRevenueSerializer(many=True)
    total_revenue_period_1 = serializers.DecimalField(decimal_places=10, max_digits=20)
    daily_usage_revenue_period_2 = PeriodSingleMetricRevenueSerializer(many=True)
    total_revenue_period_2 = serializers.DecimalField(decimal_places=10, max_digits=20)
