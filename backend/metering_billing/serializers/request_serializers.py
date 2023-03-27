from rest_framework import serializers

from metering_billing.models import (
    Customer,
    PlanVersion,
    UnifiedCRMOrganizationIntegration,
)
from metering_billing.serializers.serializer_utils import (
    SlugRelatedFieldWithOrganization,
)


class SinglePeriodRequestSerializer(serializers.Serializer):
    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)


class PeriodComparisonRequestSerializer(serializers.Serializer):
    period_1_start_date = serializers.DateField()
    period_1_end_date = serializers.DateField()
    period_2_start_date = serializers.DateField()
    period_2_end_date = serializers.DateField()


class OptionalPeriodRequestSerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)


class URLResponseSerializer(serializers.Serializer):
    url = serializers.URLField()
    exists = serializers.BooleanField()


class PeriodRequestSerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()


class CostAnalysisRequestSerializer(PeriodRequestSerializer):
    customer_id = SlugRelatedFieldWithOrganization(
        slug_field="customer_id",
        queryset=Customer.objects.all(),
        required=True,
        source="customer",
    )


class PeriodMetricUsageRequestSerializer(PeriodRequestSerializer):
    top_n_customers = serializers.IntegerField(required=False)


class DraftInvoiceRequestSerializer(serializers.Serializer):
    include_next_period = serializers.BooleanField(default=True)


class TargetCustomersSerializer(serializers.Serializer):
    customer_ids = SlugRelatedFieldWithOrganization(
        slug_field="customer_id",
        queryset=Customer.objects.all(),
        required=True,
        many=True,
        source="customers",
    )


class SetReplaceWithSerializer(serializers.Serializer):
    replace_with = SlugRelatedFieldWithOrganization(
        slug_field="version_id",
        queryset=PlanVersion.plan_versions.all(),
        required=True,
        help_text="The plan version to replace the current version with.",
    )


class MakeReplaceWithSerializer(serializers.Serializer):
    versions_to_replace = SlugRelatedFieldWithOrganization(
        slug_field="version_id",
        queryset=PlanVersion.plan_versions.all(),
        required=True,
        many=True,
        help_text="The plan versions that will get replaced by the current version.",
    )


class PlansChangeActiveDatesForVersionNumberSerializer(serializers.Serializer):
    versions_to_edit = SlugRelatedFieldWithOrganization(
        slug_field="version_id",
        queryset=PlanVersion.plan_versions.all(),
        required=True,
        many=True,
        help_text="The plan versions that will get their active dates changed.",
    )


class PlansSetReplaceWithForVersionNumberSerializer(serializers.Serializer):
    replacement_version_number = serializers.IntegerField(
        required=True,
        help_text="The version number of the plan that will replace the current version.",
        min_value=1,
    )


class PlansSetTransitionToForVersionNumberSerializer(serializers.Serializer):
    transition_to_plan_id = SlugRelatedFieldWithOrganization(
        slug_field="plan_id",
        queryset=PlanVersion.plan_versions.all(),
        required=True,
        help_text="The plan that the current version will transition to.",
        source="transition_to_plan",
    )


class CRMSyncRequestSerializer(serializers.Serializer):
    crm_provider_names = serializers.MultipleChoiceField(
        choices=UnifiedCRMOrganizationIntegration.CRMProvider.labels, required=False
    )


class StripeMultiSubscriptionsSerializer(serializers.Serializer):
    customer_id = SlugRelatedFieldWithOrganization(
        slug_field="customer_id",
        queryset=Customer.objects.all(),
        required=True,
        source="customer",
    )
    stripe_subscription_ids = serializers.ListField(
        child=serializers.CharField(), required=True
    )


class EventSearchRequestSerializer(serializers.Serializer):
    customer_id = serializers.CharField(allow_blank=True, required=False)
    idempotency_id = serializers.CharField(allow_blank=True, required=False)
    c = serializers.CharField(allow_blank=True, required=False)
