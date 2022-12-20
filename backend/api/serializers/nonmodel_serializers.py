from api.serializers.model_serializers import SubscriptionCategoricalFilterSerializer
from metering_billing.models import Customer, Metric
from metering_billing.serializers.serializer_utils import (
    SlugRelatedFieldWithOrganizationPK,
)
from rest_framework import serializers


class GetFeatureAccessSerializer(serializers.Serializer):
    feature_name = serializers.CharField(
        help_text="Name of the feature to check access for."
    )
    plan_id = serializers.CharField(
        help_text="The plan_id of the plan we are checking that has access to this feature."
    )
    subscription_filters = SubscriptionCategoricalFilterSerializer(
        many=True,
        help_text="The subscription filters that are applied to this plan's relationship with the customer. If your billing model does not have the ability multiple plans or subscriptions per customer, this is likely not relevant for you.",
    )
    access = serializers.BooleanField(
        help_text="Whether or not the plan has access to this feature. If your customer can have multiple plans or subscriptions, then you must check the 'access' across all returned plans to determine if the customer can access this feature."
    )


class ComponentUsageSerializer(serializers.Serializer):
    event_name = serializers.CharField(
        help_text="The name of the event you are checking access for."
    )
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
    plan_id = serializers.CharField(
        help_text="The plan_id of the plan we are checking that has access to this feature."
    )
    subscription_filters = SubscriptionCategoricalFilterSerializer(
        many=True,
        help_text="The subscription filters that are applied to this plan's relationship with the customer. If your billing model does not have the ability multiple plans or subscriptions per customer, this is likely not relevant for you.",
    )
    usage_per_component = ComponentUsageSerializer(
        many=True,
        help_text="The usage of each component of the plan the customer is on. Only components that match the request will be included: If metric_id is provided, this will be a list of length 1. If event_name is provided, this will be a list of length 1 or more depending on how many components of the customer's plan use this event.",
    )


class GetCustomerEventAccessRequestSerializer(serializers.Serializer):
    customer_id = SlugRelatedFieldWithOrganizationPK(
        slug_field="customer_id",
        queryset=Customer.objects.all(),
        help_text="The customer_id of the customer you want to check access.",
    )
    event_name = serializers.CharField(
        help_text="The name of the event you are checking access for.",
        required=False,
        allow_null=True,
    )
    metric_id = SlugRelatedFieldWithOrganizationPK(
        slug_field="metric_id",
        queryset=Metric.objects.all(),
        required=False,
        allow_null=True,
        help_text="The metric_id of the metric you are checking access for. Please note that you must porovide exactly one of event_name and metric_id are mutually; a validation error will be thrown if both or none are provided.",
    )
    subscription_filters = SubscriptionCategoricalFilterSerializer(
        many=True,
        required=False,
        help_text="The subscription filters that are applied to this plan's relationship with the customer. If your billing model does not have the ability multiple plans or subscriptions per customer, this is likely not relevant for you. This must be passed in as a stringified JSON object.",
    )

    def validate(self, data):
        data = super().validate(data)
        data["metric"] = data.pop("metric_id", None)
        data["customer"] = data.pop("customer_id", None)
        if data.get("event_name") is not None and data.get("metric") is not None:
            raise serializers.ValidationError(
                "event_name and metric_id are mutually exclusive. Please only provide one."
            )
        if data.get("event_name") is None and data.get("metric") is None:
            raise serializers.ValidationError(
                "You must provide either an event_name or a metric_id."
            )

        return data


class GetCustomerFeatureAccessRequestSerializer(serializers.Serializer):
    customer_id = SlugRelatedFieldWithOrganizationPK(
        slug_field="customer_id",
        queryset=Customer.objects.all(),
        help_text="The customer_id of the customer you want to check access.",
    )
    feature_name = serializers.CharField(
        help_text="Name of the feature to check access for."
    )
    subscription_filters = SubscriptionCategoricalFilterSerializer(
        many=True,
        required=False,
        help_text="The subscription filters that are applied to this plan's relationship with the customer. If your billing model does not have the ability multiple plans or subscriptions per customer, this is likely not relevant for you. This must be passed in as a stringified JSON object.",
    )

    def validate(self, data):
        data = super().validate(data)
        data["customer"] = data.pop("customer_id", None)

        return data
