from rest_framework import serializers


class GetCustomerAccessRequestSerializer(serializers.Serializer):
    customer_id = serializers.CharField(required=True)
    event_name = serializers.CharField(required=False)
    feature_name = serializers.CharField(required=False)
    event_limit_type = serializers.ChoiceField(
        choices=["free", "total"], required=False
    )

    def validate(self, data):
        if not data.get("event_name") and not data.get("feature_name"):
            raise serializers.ValidationError(
                "Must provide either event_name or feature_name"
            )
        if data.get("event_name") and data.get("feature_name"):
            raise serializers.ValidationError(
                "Cannot provide both event_name and feature_name"
            )
        if data.get("event_name") and not data.get("event_limit_type"):
            raise serializers.ValidationError(
                "Must provide event_limit_type when providing event_name"
            )
        return data


class CancelSubscriptionRequestSerializer(serializers.Serializer):
    subscription_id = serializers.CharField(required=True)
    bill_now = serializers.BooleanField(default=False)
    revoke_access = serializers.BooleanField(default=False)


class UpdateSubscriptionPlanVersionRequestSerializer(serializers.Serializer):
    subscription_id = serializers.CharField(required=True)
    new_version_id = serializers.CharField(required=True)
    update_behavior = serializers.ChoiceField(
        choices=["replace_immediately", "replace_on_renewal"]
    )


class MergeCustomersRequestSerializer(serializers.Serializer):
    customer1_id = serializers.CharField(required=True)
    customer2_id = serializers.CharField(required=True)


class PeriodComparisonRequestSerializer(serializers.Serializer):
    period_1_start_date = serializers.DateField()
    period_1_end_date = serializers.DateField()
    period_2_start_date = serializers.DateField()
    period_2_end_date = serializers.DateField()


class PeriodRequestSerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()


class CostAnalysisRequestSerializer(PeriodRequestSerializer):
    customer_id = serializers.CharField()


# PERIOD METRIC USAGE SERIALIZERS GO HERE
class PeriodMetricUsageRequestSerializer(PeriodRequestSerializer):
    top_n_customers = serializers.IntegerField(required=False)


class EventPreviewRequestSerializer(serializers.Serializer):
    page = serializers.IntegerField(required=True)


class DraftInvoiceRequestSerializer(serializers.Serializer):
    customer_id = serializers.CharField(required=True)
