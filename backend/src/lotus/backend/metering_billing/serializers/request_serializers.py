from lotus.backend.metering_billing.models import Customer
from lotus.backend.metering_billing.serializers.serializer_utils import (
    SlugRelatedFieldWithOrganization,
)
from lotus.backend.metering_billing.utils.enums import (
    ORGANIZATION_SETTING_GROUPS,
    ORGANIZATION_SETTING_NAMES,
)
from rest_framework import serializers


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
