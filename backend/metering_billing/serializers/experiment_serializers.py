from rest_framework import serializers

from api.serializers.model_serializers import (
    LightweightCustomerSerializer,
    LightweightMetricSerializer,
    LightweightPlanVersionSerializer,
)
from metering_billing.models import (
    Analysis,
    Backtest,
    BacktestSubstitution,
    PlanVersion,
)
from metering_billing.serializers.model_serializers import PlanVersionDetailSerializer
from metering_billing.utils.enums import ANALYSIS_KPI, BACKTEST_KPI

from .serializer_utils import (
    AnalysisUUIDField,
    BacktestUUIDField,
    SlugRelatedFieldWithOrganization,
    TimezoneFieldMixin,
)


class BacktestSubstitutionMultiSerializer(serializers.Serializer):
    new_plan = SlugRelatedFieldWithOrganization(
        slug_field="version_id",
        queryset=PlanVersion.plan_versions.active(),
        read_only=False,
    )
    original_plans = SlugRelatedFieldWithOrganization(
        slug_field="version_id",
        queryset=PlanVersion.plan_versions.all(),
        read_only=False,
        many=True,
    )


class BacktestCreateSerializer(TimezoneFieldMixin, serializers.ModelSerializer):
    class Meta:
        model = Backtest
        fields = ("start_date", "end_date", "substitutions", "kpis", "backtest_name")

    kpis = serializers.ListSerializer(
        child=serializers.ChoiceField(choices=BACKTEST_KPI.choices),
        required=True,
    )
    substitutions = serializers.ListSerializer(
        child=BacktestSubstitutionMultiSerializer(),
        required=True,
        write_only=True,
        allow_empty=False,
    )

    def create(self, validated_data):
        substitutions = validated_data.pop("substitutions")
        backtest_obj = Backtest.objects.create(**validated_data)
        for substitution_set in substitutions:
            new_plan_obj = substitution_set.pop("new_plan")
            original_plans = substitution_set.pop("original_plans")
            for original_plan_obj in original_plans:
                BacktestSubstitution.objects.create(
                    new_plan=new_plan_obj,
                    original_plan=original_plan_obj,
                    backtest=backtest_obj,
                )
        return backtest_obj


class BacktestSummarySerializer(TimezoneFieldMixin, serializers.ModelSerializer):
    class Meta:
        model = Backtest
        fields = (
            "backtest_name",
            "start_date",
            "end_date",
            "time_created",
            "kpis",
            "status",
            "backtest_id",
        )

    backtest_id = BacktestUUIDField()


class BacktestSubstitutionSerializer(TimezoneFieldMixin, serializers.ModelSerializer):
    class Meta:
        model = BacktestSubstitution
        fields = ("new_plan", "original_plan")

    new_plan = PlanVersionDetailSerializer()
    original_plan = PlanVersionDetailSerializer()


class PlanRepresentationSerializer(serializers.Serializer):
    plan_name = serializers.CharField()
    plan_id = serializers.CharField()
    plan_revenue = serializers.FloatField()


class RevenueDateSerializer(serializers.Serializer):
    date = serializers.DateField()
    original_plan_revenue = serializers.FloatField()
    new_plan_revenue = serializers.FloatField()


class MetricRevenueSerializer(serializers.Serializer):
    metric_name = serializers.CharField()
    original_plan_revenue = serializers.FloatField()
    new_plan_revenue = serializers.FloatField()


class SingleCustomerValueSerializer(serializers.Serializer):
    customer = LightweightCustomerSerializer()
    value = serializers.DecimalField(
        max_digits=20, decimal_places=10, coerce_to_string=True
    )


class TopCustomersSerializer(serializers.Serializer):
    original_plan_revenue = serializers.ListField(child=SingleCustomerValueSerializer())
    new_plan_revenue = serializers.ListField(child=SingleCustomerValueSerializer())
    biggest_pct_increase = serializers.ListField(child=SingleCustomerValueSerializer())
    biggest_pct_decrease = serializers.ListField(child=SingleCustomerValueSerializer())


class SingleSubstitutionResultsSerializer(serializers.Serializer):
    cumulative_revenue = serializers.ListField(child=RevenueDateSerializer())
    revenue_by_metric = serializers.ListField(child=MetricRevenueSerializer())
    top_customers = TopCustomersSerializer()


class SingleSubstitutionSerializer(serializers.Serializer):
    substitution_name = serializers.CharField()
    original_plan = PlanRepresentationSerializer()
    new_plan = PlanRepresentationSerializer()
    pct_revenue_change = serializers.FloatField(allow_null=True)
    results = SingleSubstitutionResultsSerializer()


class AllSubstitutionResultsSerializer(serializers.Serializer):
    substitution_results = serializers.ListField(
        child=SingleSubstitutionSerializer(), required=False
    )
    original_plans_revenue = serializers.FloatField(required=False)
    new_plans_revenue = serializers.FloatField(required=False)
    pct_revenue_change = serializers.FloatField(required=False, allow_null=True)


class BacktestDetailSerializer(BacktestSummarySerializer):
    class Meta(BacktestSummarySerializer.Meta):
        fields = tuple(
            set(BacktestSummarySerializer.Meta.fields)
            | {"backtest_substitutions", "backtest_results"}
        )

    backtest_results = AllSubstitutionResultsSerializer()
    backtest_substitutions = BacktestSubstitutionSerializer(many=True)


class AnalysisSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Analysis
        fields = (
            "analysis_name",
            "start_date",
            "end_date",
            "time_created",
            "kpis",
            "status",
            "analysis_id",
        )

    analysis_id = AnalysisUUIDField()


class SingleKPISerializer(serializers.Serializer):
    kpi = serializers.ChoiceField(choices=ANALYSIS_KPI.choices)
    value = serializers.DecimalField(
        max_digits=20, decimal_places=10, coerce_to_string=True
    )


class SinglePlanAnalysisSerializer(serializers.Serializer):
    plan = LightweightPlanVersionSerializer()
    kpis = SingleKPISerializer(many=True)


class PerPlanPerDaySerializer(serializers.Serializer):
    plan = LightweightPlanVersionSerializer()
    revenue = serializers.DecimalField(
        max_digits=20, decimal_places=10, coerce_to_string=True
    )


class RevenuePerDaySerializer(serializers.Serializer):
    date = serializers.DateField()
    revenue_per_plan = PerPlanPerDaySerializer(many=True)


class RevenueByMetricSerializer(serializers.Serializer):
    metric = LightweightMetricSerializer()
    revenue = serializers.DecimalField(
        max_digits=20, decimal_places=10, coerce_to_string=True
    )


class RevenueByPlanMetricSerializer(serializers.Serializer):
    plan = LightweightPlanVersionSerializer()
    by_metric = RevenueByMetricSerializer(many=True)


class TopCustomersPerPlanAnalysisSerializer(serializers.Serializer):
    top_customers_by_revenue = serializers.ListField(
        child=SingleCustomerValueSerializer(), max_length=10
    )
    top_customers_by_average_revenue = serializers.ListField(
        child=SingleCustomerValueSerializer(), max_length=10
    )
    plan = LightweightPlanVersionSerializer()


class AnalysisResultsSerializer(serializers.Serializer):
    analysis_summary = SinglePlanAnalysisSerializer(many=True)
    revenue_per_day_graph = RevenuePerDaySerializer(many=True)
    revenue_by_metric_graph = RevenueByPlanMetricSerializer(many=True)
    top_customers_by_plan = TopCustomersPerPlanAnalysisSerializer(many=True)


class AnalysisDetailSerializer(AnalysisSummarySerializer):
    class Meta(AnalysisSummarySerializer.Meta):
        fields = tuple(
            set(AnalysisSummarySerializer.Meta.fields) | {"analysis_results"}
        )

    analysis_results = AnalysisResultsSerializer()


# end
