from api.serializers.model_serializers import SubscriptionCategoricalFilterSerializer
from rest_framework import serializers


class GetFeatureAccessSerializer(serializers.Serializer):
    feature = serializers.CharField()
    plan_id = serializers.CharField()
    subscription_filters = serializers.DictField(child=serializers.CharField())
    access = serializers.BooleanField()


class MetricDetailSerializer(serializers.Serializer):
    metric_name = serializers.CharField()
    metric_id = serializers.CharField()
    metric_usage = serializers.FloatField()
    metric_free_limit = serializers.FloatField()
    metric_total_limit = serializers.FloatField()


class GetEventAccessSerializer(serializers.Serializer):
    event_name = serializers.CharField()
    plan_id = serializers.CharField()
    subscription_filters = serializers.DictField(child=serializers.CharField())
    has_event = serializers.BooleanField()
    usage_per_metric = MetricDetailSerializer(many=True)


class GetCustomerEventAccessRequestSerializer(serializers.Serializer):
    customer_id = serializers.CharField()
    event_name = serializers.CharField()
    metric_id = serializers.CharField(required=False)
    subscription_filters = serializers.ListField(
        child=SubscriptionCategoricalFilterSerializer(), required=False
    )


class GetCustomerFeatureAccessRequestSerializer(serializers.Serializer):
    customer_id = serializers.CharField()
    feature_name = serializers.CharField()
    subscription_filters = serializers.ListField(
        child=SubscriptionCategoricalFilterSerializer(), required=False
    )
