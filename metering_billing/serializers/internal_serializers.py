from metering_billing.models import BillingPlan, Customer, Subscription
from rest_framework import serializers

from .model_serializers import EventSerializer

## CUSTOM SERIALIZERS


class GetCustomerAccessRequestSerializer(serializers.Serializer):
    customer_id = serializers.CharField(required=True)
    billable_metric_name = serializers.CharField(required=False)
    feature_name = serializers.CharField(required=False)

    def validate(self, data):
        if not data.get("billable_metric_name") and not data.get("feature_name"):
            raise serializers.ValidationError(
                "Must provide either billable_metric_name or feature_name"
            )
        if data.get("billable_metric_name") and data.get("feature_name"):
            raise serializers.ValidationError(
                "Cannot provide both billable_metric_name and feature_name"
            )
        return data


class CancelSubscriptionRequestSerializer(serializers.Serializer):
    bill_now = serializers.BooleanField(default=True)
    revoke_access = serializers.BooleanField(default=False)
    subscription_uid = serializers.CharField(required=True)


class RegistrationDetailSerializer(serializers.Serializer):
    company_name = serializers.CharField()
    industry = serializers.CharField()
    email = serializers.CharField()
    password = serializers.CharField()
    username = serializers.CharField()


class RegistrationSerializer(serializers.Serializer):
    register = RegistrationDetailSerializer()


class EventPreviewSerializer(serializers.Serializer):
    events = EventSerializer(many=True)
    total_pages = serializers.IntegerField(required=True)


class EventPreviewRequestSerializer(serializers.Serializer):
    page = serializers.IntegerField(required=True)


class DraftInvoiceRequestSerializer(serializers.Serializer):
    customer_id = serializers.CharField(required=True)


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
