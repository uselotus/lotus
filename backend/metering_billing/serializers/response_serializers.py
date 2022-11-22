from rest_framework import serializers

from .model_serializers import (MetricSerializer,
                                SubscriptionCustomerSummarySerializer)


class PeriodSubscriptionsResponseSerializer(serializers.Serializer):
    period_1_total_subscriptions = serializers.IntegerField()
    period_1_new_subscriptions = serializers.IntegerField()
    period_2_total_subscriptions = serializers.IntegerField()
    period_2_new_subscriptions = serializers.IntegerField()


class DayMetricUsageSerializer(serializers.Serializer):
    date = serializers.DateField()
    customer_usages = serializers.DictField(
        child=serializers.DecimalField(decimal_places=10, max_digits=20)
    )


class PeriodSingleMetricUsageSerializer(serializers.Serializer):
    data = DayMetricUsageSerializer(many=True)
    total_usage = serializers.DecimalField(decimal_places=10, max_digits=20)


class PeriodMetricUsageResponseSerializer(serializers.Serializer):
    metrics = serializers.DictField(child=PeriodSingleMetricUsageSerializer())


class CustomerRevenueSerializer(serializers.Serializer):
    subscriptions = serializers.ListField(child=serializers.CharField())
    total_amount_due = serializers.DecimalField(decimal_places=10, max_digits=20)
    customer_name = serializers.CharField()
    customer_id = serializers.CharField()


class CustomerRevenueSummaryResponseSerializer(serializers.Serializer):
    customers = CustomerRevenueSerializer(many=True)


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


class SubscriptionUsageResponseSerializer(serializers.Serializer):
    usage_amount_due = serializers.DecimalField(decimal_places=10, max_digits=20)
    flat_amount_due = serializers.DecimalField(decimal_places=10, max_digits=20)
    total_amount_due = serializers.DecimalField(decimal_places=10, max_digits=20)


class SingleMetricCostSerializer(serializers.Serializer):
    metric = MetricSerializer()
    cost = serializers.DecimalField(decimal_places=10, max_digits=20)


class SingleDayCostAnalysisSerializer(serializers.Serializer):
    date = serializers.DateField()
    cost_data = serializers.ListField(child=SingleMetricCostSerializer())
    revenue = serializers.DecimalField(decimal_places=10, max_digits=20)


class CostAnalysisSerializer(serializers.Serializer):
    per_day = serializers.ListField(child=SingleDayCostAnalysisSerializer())
    total_cost = serializers.DecimalField(decimal_places=10, max_digits=20)
    total_revenue = serializers.DecimalField(decimal_places=10, max_digits=20)
    margin = serializers.DecimalField(decimal_places=10, max_digits=20)
