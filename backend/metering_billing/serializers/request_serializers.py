from rest_framework import serializers

from metering_billing.models import Customer, PlanVersion
from metering_billing.serializers.serializer_utils import (
    SlugRelatedFieldWithOrganization,
)
from metering_billing.utils.enums import (
    ORGANIZATION_SETTING_GROUPS,
    ORGANIZATION_SETTING_NAMES,
)


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
    customer_id = serializers.CharField()


class PeriodMetricUsageRequestSerializer(PeriodRequestSerializer):
    top_n_customers = serializers.IntegerField(required=False)


class DraftInvoiceRequestSerializer(serializers.Serializer):
    customer_id = SlugRelatedFieldWithOrganization(
        slug_field="customer_id",
        queryset=Customer.objects.all(),
        required=True,
    )
    include_next_period = serializers.BooleanField(default=True)

    def validate(self, data):
        super().validate(data)
        data["customer"] = data.pop("customer_id")
        return data


class OrganizationSettingFilterSerializer(serializers.Serializer):
    setting_name = serializers.MultipleChoiceField(
        required=False,
        help_text="Filters organization_settings by setting_name. Defaults to returning all settings.",
        choices=ORGANIZATION_SETTING_NAMES.choices,
    )
    setting_group = serializers.ChoiceField(
        required=False,
        help_text="Filters organization_settings to a single setting_group. Defaults to returning all settings.",
        choices=ORGANIZATION_SETTING_GROUPS.choices,
    )


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
