from django.db.models import Q
from rest_framework import serializers

from metering_billing.models import Backtest, BacktestSubstitution, PlanVersion
from metering_billing.serializers.model_serializers import PlanVersionDetailSerializer
from metering_billing.utils.enums import BACKTEST_KPI, PLAN_VERSION_STATUS

from .serializer_utils import (
    BacktestUUIDField,
    SlugRelatedFieldWithOrganization,
    TimezoneFieldMixin,
)


class BacktestSubstitutionMultiSerializer(serializers.Serializer):
    new_plan = SlugRelatedFieldWithOrganization(
        slug_field="version_id",
        queryset=PlanVersion.objects.filter(~Q(status=PLAN_VERSION_STATUS.ARCHIVED)),
        read_only=False,
    )
    original_plans = serializers.ListSerializer(
        child=SlugRelatedFieldWithOrganization(
            slug_field="version_id",
            queryset=PlanVersion.objects.all(),
            read_only=False,
        ),
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
    customer_id = serializers.CharField()
    customer_name = serializers.CharField()
    value = serializers.FloatField()


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

    backtest_results = AllSubstitutionResultsSerializer()
    backtest_substitutions = BacktestSubstitutionSerializer(many=True)
