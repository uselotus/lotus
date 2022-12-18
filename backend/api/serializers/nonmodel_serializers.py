from api.serializers.model_serializers import SubscriptionCategoricalFilterSerializer
from rest_framework import serializers


class GetFeatureAccessSerializer(serializers.Serializer):
    feature = serializers.CharField(
        help_text="Name of the feature to check access for."
    )
    plan_id = serializers.CharField(
        help_text="The plan_id of the plan we are checking that has access to this feature."
    )
    subscription_filters = serializers.DictField(
        child=serializers.CharField(),
        help_text="The subscription filters that are applied to this plan's relationship with the customer. If your billing model does not have the ability multiple plans or subscriptions per customer, this is likely nto relevant for you.",
    )
    access = serializers.BooleanField(
        help_text="Whether or not the plan has access to this feature. If your customer can have multiple plans or subscriptions, then you must check the 'access' across all returned plans to determine if the customer can access this feature."
    )


class MetricDetailSerializer(serializers.Serializer):
    metric_name = serializers.CharField(help_text="The name of the metric.")
    metric_id = serializers.CharField(
        help_text="The metric_id of the metric. This metric_id can be found in the Lotus frontend if you haven't seen it before."
    )
    metric_usage = serializers.FloatField(
        help_text="The current usage of the metric. Keep in mind the current usage of the metric can be different from the billable usage of the metric."
    )
    metric_free_limit = serializers.FloatField(
        allow_null=True,
        help_text="If you specified a free tier of usage for this metric, this is the amount of usage that is free. Will be null if you did not specify a free tier for this metric.",
    )
    metric_total_limit = serializers.FloatField(
        allow_null=True,
        help_text="The total limit of the metric. Will be null if you did not specify a limit for this metric.",
    )


class GetEventAccessSerializer(serializers.Serializer):
    event_name = serializers.CharField(
        help_text="The name of the event you are checking access for."
    )
    plan_id = serializers.CharField(
        help_text="The plan_id of the plan we are checking that has access to this feature."
    )
    subscription_filters = serializers.DictField(
        child=serializers.CharField(),
        help_text="The subscription filters that are applied to this plan's relationship with the customer. If your billing model does not have the ability multiple plans or subscriptions per customer, this is likely nto relevant for you.",
    )
    has_event = serializers.BooleanField(
        help_text="Whether or not the plan has access to this event."
    )
    usage_per_metric = MetricDetailSerializer(
        many=True,
        help_text="The usage of each metric for this event. Since a plan can have multiple metrics that rely on the same event, this is a list of all the metrics that are used by this event. For example, you might have a metric both for the total number of transactions and the rate of transactions. If you are checking access for the 'transaction' event, this will return the usage of both the 'total_transactions' and 'transaction_rate' metrics.",
    )


class GetCustomerEventAccessRequestSerializer(serializers.Serializer):
    customer_id = serializers.CharField(
        help_text="The customer_id of the customer you want to check access."
    )
    event_name = serializers.CharField(
        help_text="The name of the event you are checking access for."
    )
    metric_id = serializers.CharField(
        required=False,
        help_text="The metric_id of the metric you are checking access for. If you don't specify this, we will return the access for all metrics that use this event.",
    )
    subscription_filters = serializers.DictField(
        child=serializers.CharField(),
        help_text="The subscription filters that are applied to this plan's relationship with the customer. If your billing model does not have the ability multiple plans or subscriptions per customer, this is likely nto relevant for you.",
    )


class GetCustomerFeatureAccessRequestSerializer(serializers.Serializer):
    customer_id = serializers.CharField(
        help_text="The customer_id of the customer you want to check access."
    )
    feature_name = serializers.CharField(
        help_text="Name of the feature to check access for."
    )
    subscription_filters = serializers.DictField(
        child=serializers.CharField(),
        help_text="The subscription filters that are applied to this plan's relationship with the customer. If your billing model does not have the ability multiple plans or subscriptions per customer, this is likely nto relevant for you.",
    )
