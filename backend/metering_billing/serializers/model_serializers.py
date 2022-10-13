import datetime

from django.db.models import Q
from metering_billing.auth_utils import parse_organization
from metering_billing.billable_metrics import METRIC_HANDLER_MAP
from metering_billing.exceptions import OverlappingSubscription
from metering_billing.models import (
    Alert,
    Backtest,
    BacktestSubstitution,
    BillableMetric,
    BillingPlan,
    CategoricalFilter,
    Customer,
    Event,
    Feature,
    Invoice,
    NumericFilter,
    Organization,
    PlanComponent,
    Subscription,
    User,
)
from metering_billing.utils import BACKTEST_KPI_TYPES, PLAN_STATUS, SUB_STATUS_TYPES
from rest_framework import serializers


## EXTRANEOUS SERIALIZERS
class SlugRelatedLookupField(serializers.SlugRelatedField):
    def get_queryset(self):
        queryset = self.queryset
        org = self.context.get("organization", None)
        queryset.filter(organization=org)
        return queryset


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = (
            "id",
            "company_name",
            "payment_plan",
            "payment_provider_ids",
        )


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = (
            "event_name",
            "properties",
            "time_created",
            "idempotency_id",
            "customer_id",
        )

    customer_id = SlugRelatedLookupField(
        slug_field="customer_id",
        queryset=Customer.objects.all(),
        read_only=False,
        source="customer",
    )


class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = (
            "type",
            "webhook_url",
            "name",
        )


## USER
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("username", "password")


## CUSTOMER
class FilterActiveSubscriptionSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        data = data.filter(status=SUB_STATUS_TYPES.ACTIVE)
        return super(FilterActiveSubscriptionSerializer, self).to_representation(data)


class SubscriptionCustomerSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ("billing_plan_name", "end_date", "auto_renew")
        list_serializer_class = FilterActiveSubscriptionSerializer

    billing_plan_name = serializers.CharField(source="billing_plan.name")


class CustomerSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = (
            "customer_name",
            "customer_id",
            "subscriptions",
        )

    subscriptions = SubscriptionCustomerSummarySerializer(read_only=True, many=True)
    customer_name = serializers.CharField(source="name")


class SubscriptionCustomerDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = (
            "billing_plan_name",
            "subscription_id",
            "start_date",
            "end_date",
            "auto_renew",
            "status",
        )
        list_serializer_class = FilterActiveSubscriptionSerializer

    billing_plan_name = serializers.CharField(source="billing_plan.name")


class CustomerDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = (
            "customer_id",
            "email",
            "balance",
            "customer_name",
            "invoices",
            "total_revenue_due",
            "subscriptions",
        )

    customer_name = serializers.CharField(source="name")
    subscriptions = SubscriptionCustomerDetailSerializer(read_only=True, many=True)
    invoices = serializers.SerializerMethodField()
    total_revenue_due = serializers.SerializerMethodField()

    def get_invoices(self, obj) -> list:
        timeline = self.context.get("invoices")
        timeline = InvoiceSerializer(timeline, many=True).data
        return timeline

    def get_total_revenue_due(self, obj) -> float:
        total_revenue_due = float(self.context.get("total_revenue_due"))
        return total_revenue_due


class CustomerWithRevenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ("customer_id", "total_revenue_due")

    total_revenue_due = serializers.SerializerMethodField()

    def get_total_revenue_due(self, obj) -> float:
        total_revenue_due = float(self.context.get("total_revenue_due"))
        return total_revenue_due


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = (
            "customer_name",
            "customer_id",
            "balance",
        )

    customer_name = serializers.CharField(source="name")


## BILLABLE METRIC
class CategoricalFilterSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoricalFilter
        fields = ("property_name", "operator", "comparison_value")


class NumericFilterSerializer(serializers.ModelSerializer):
    class Meta:
        model = NumericFilter
        fields = ("property_name", "operator", "comparison_value")


class BillableMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillableMetric
        fields = (
            "event_name",
            "property_name",
            "aggregation_type",
            "metric_type",
            "billable_metric_name",
            "numeric_filters",
            "categorical_filters",
            "properties",
        )

    numeric_filters = NumericFilterSerializer(
        many=True, allow_null=True, required=False
    )
    categorical_filters = CategoricalFilterSerializer(
        many=True, allow_null=True, required=False
    )
    properties = serializers.JSONField(allow_null=True, required=False)

    def custom_name(self, validated_data) -> str:
        name = validated_data.get("billable_metric_name", None)
        if name in [None, "", " "]:
            name = f"[{validated_data['metric_type'][:4]}]"
            name += " " + validated_data["aggregation_type"] + " of"
            if validated_data["property_name"] not in ["", " ", None]:
                name += " " + validated_data["property_name"] + " of"
            name += " " + validated_data["event_name"]
            validated_data["billable_metric_name"] = name[:200]
        return name

    def create(self, validated_data):
        # edit custom name and pop filters + properties
        validated_data["billable_metric_name"] = self.custom_name(validated_data)
        num_filter_data = validated_data.pop("numeric_filters", [])
        cat_filter_data = validated_data.pop("categorical_filters", [])

        properties = validated_data.pop("properties", {})

        properties = METRIC_HANDLER_MAP[
            validated_data["metric_type"]
        ].validate_properties(properties)

        bm = BillableMetric.objects.create(**validated_data)

        # get filters
        for num_filter in num_filter_data:
            try:
                nf, _ = NumericFilter.objects.get_or_create(**num_filter)
            except NumericFilter.MultipleObjectsReturned:
                nf = NumericFilter.objects.filter(**num_filter).first()
            bm.numeric_filters.add(nf)
        for cat_filter in cat_filter_data:
            try:
                cf, _ = CategoricalFilter.objects.get_or_create(**cat_filter)
            except CategoricalFilter.MultipleObjectsReturned:
                cf = CategoricalFilter.objects.filter(**cat_filter).first()
            bm.categorical_filters.add(cf)
        bm.properties = properties
        bm.save()

        return bm


## FEATURE
class FeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feature
        fields = (
            "feature_name",
            "feature_description",
        )


## PLAN COMPONENT
class PlanComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanComponent
        fields = (
            "id",
            "billable_metric_name",
            "billable_metric",
            "free_metric_units",
            "cost_per_batch",
            "metric_units_per_batch",
            "max_metric_units",
        )
        read_only_fields = ('id', 'billable_metric')

    # READ-ONLY
    billable_metric = BillableMetricSerializer()

    # WRITE-ONLY
    billable_metric_name = serializers.SlugRelatedField(
        slug_field="billable_metric_name",
        write_only=True,
        source="billable_metric",
        queryset=BillableMetric.objects.all(),
    )

    def get_fields(self, *args, **kwargs):
        fields = super().get_fields(*args, **kwargs)
        bmqs = fields["billable_metric_name"].queryset
        fields["billable_metric_name"].queryset = bmqs.filter(
            organization=self.context["organization"]
        )
        return fields

    def validate(self, data):
        # fmu, cpb, and mupb must all be none or all be not none
        together = [
            data.get("free_metric_units"),
            data.get("cost_per_batch"),
            data.get("metric_units_per_batch"),
        ]
        if not (all(together) or not any(together)):
            raise serializers.ValidationError(
                "Must specify exactly all or none of free_metric_units, cost_per_batch, metric_units_per_batch. Currently, free_metric_units: {}, cost_per_batch: {}, metric_units_per_batch: {}".format(
                    *together
                )
            )
        # cant have zero or negative units per batch
        if (
            data.get("metric_units_per_batch") is not None
            and data.get("metric_units_per_batch") <= 0
        ):
            raise serializers.ValidationError(
                "metric_units_per_batch must be greater than 0"
            )
        # free units can't be greater than max units
        if (
            data.get("free_metric_units") is not None
            and data.get("max_metric_units") is not None
            and data["free_metric_units"] > data["max_metric_units"]
        ):
            raise serializers.ValidationError(
                "Free metric units cannot be greater than max metric units."
            )
        return super().validate(data)

    def create(self, validated_data):
        billable_metric = validated_data.pop("billable_metric_name")
        pc = PlanComponent.objects.create(
            billable_metric=billable_metric, **validated_data
        )
        return pc



## BILLING PLAN
class BillingPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingPlan
        fields = (
            "interval",
            "flat_rate",
            "pay_in_advance",
            "billing_plan_id",
            "name",
            "description",
            "components",
            "features",
            "status",
        )
        read_only_fields = ('time_created', 'active_subscriptions')
    
    components = PlanComponentSerializer(many=True, allow_null=True, required=False)
    features = FeatureSerializer(many=True, allow_null=True, required=False)

    # READ-ONLY
    time_created = serializers.SerializerMethodField()
    active_subscriptions = serializers.IntegerField()

    def get_time_created(self, obj) -> datetime.date:
        return str(obj.time_created.date())

    def create(self, validated_data):
        components_data = validated_data.pop("components", [])
        features_data = validated_data.pop("features", [])
        billing_plan = BillingPlan.objects.create(**validated_data)
        org = billing_plan.organization
        for component_data in components_data:
            try:
                pc, _ = PlanComponent.objects.get_or_create(**component_data)
            except PlanComponent.MultipleObjectsReturned:
                pc = PlanComponent.objects.filter(**component_data).first()
            billing_plan.components.add(pc)
        for feature_data in features_data:
            feature_data["organization"] = org
            try:
                f, _ = Feature.objects.get_or_create(**feature_data)
            except Feature.MultipleObjectsReturned:
                f = Feature.objects.filter(**feature_data).first()
            billing_plan.features.add(f)
        billing_plan.save()
        return billing_plan


## SUBSCRIPTION


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = (
            "customer_id",
            "billing_plan_id",
            "start_date",
            "end_date",
            "status",
            "auto_renew",
            "is_new",
            "subscription_id",
        )

    customer_id = serializers.SlugRelatedField(
        slug_field="customer_id",
        read_only=False,
        source="customer",
        queryset=Customer.objects.all(),
    )
    billing_plan_id = serializers.SlugRelatedField(
        slug_field="billing_plan_id",
        read_only=False,
        source="billing_plan",
        queryset=BillingPlan.objects.all(),
    )
    end_date = serializers.DateField(required=False)
    status = serializers.CharField(required=False)
    auto_renew = serializers.BooleanField(required=False)
    is_new = serializers.BooleanField(required=False)
    subscription_id = serializers.CharField(required=False)

    def get_fields(self, *args, **kwargs):
        fields = super().get_fields(*args, **kwargs)
        cqs = fields["customer_id"].queryset
        fields["customer_id"].queryset = cqs.filter(
            organization=self.context["organization"]
        )
        bpqs = fields["billing_plan_id"].queryset
        fields["billing_plan_id"].queryset = bpqs.filter(
            organization=self.context["organization"]
        )
        return fields

    def validate(self, data):
        # check no existing subs
        sd = data["start_date"]
        ed = data["billing_plan"].calculate_end_date(sd)
        num_existing_subs = Subscription.objects.filter(
            Q(start_date__range=(sd, ed)) | Q(end_date__range=(sd, ed)),
            customer__customer_id=data["customer"].customer_id,
            billing_plan__billing_plan_id=data["billing_plan"].billing_plan_id,
        ).count()
        if num_existing_subs > 0:
            raise serializers.ValidationError(
                f"Customer already has an active subscription to this plan"
            )

        # check that customer and billing_plan currencies match
        customer_currency = data["customer"].balance.currency
        billing_plan_currency = data["billing_plan"].flat_rate.currency
        if customer_currency != billing_plan_currency:
            raise serializers.ValidationError(
                f"Customer currency {customer_currency} does not match billing plan currency {billing_plan_currency}"
            )
        return data


class SubscriptionReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = (
            "customer",
            "billing_plan",
            "start_date",
            "end_date",
            "status",
        )

    customer = CustomerSerializer()
    billing_plan = BillingPlanSerializer()


## INVOICE
class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = (
            "cost_due",
            "cost_due_currency",
            "issue_date",
            "payment_status",
            "cust_connected_to_payment_provider",
            "org_connected_to_cust_payment_provider",
            "external_payment_obj_id",
            "line_items",
            "organization",
            "customer",
            "subscription",
        )

    cost_due = serializers.DecimalField(
        max_digits=10, decimal_places=2, source="cost_due.amount"
    )
    cost_due_currency = serializers.CharField(source="cost_due.currency")


class DraftInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = (
            "cost_due",
            "cost_due_currency",
            "cust_connected_to_payment_provider",
            "org_connected_to_cust_payment_provider",
            "line_items",
            "organization",
            "customer",
            "subscription",
        )

    cost_due = serializers.DecimalField(
        max_digits=10, decimal_places=2, source="cost_due.amount"
    )
    cost_due_currency = serializers.CharField(source="cost_due.currency")


class BacktestSubstitutionMultiSerializer(serializers.Serializer):
    new_plan = SlugRelatedLookupField(
        slug_field="billing_plan_id",
        queryset=BillingPlan.objects.filter(
            Q(status=PLAN_STATUS.ACTIVE) | Q(status=PLAN_STATUS.EXPERIMENTAL)
        ),
        read_only=False,
    )
    old_plans = serializers.ListSerializer(
        child=SlugRelatedLookupField(
            slug_field="billing_plan_id",
            queryset=BillingPlan.objects.filter(
                Q(status=PLAN_STATUS.ACTIVE) | Q(status=PLAN_STATUS.INACTIVE)
            ),
            read_only=False,
        ),
    )


class BacktestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Backtest
        fields = ("start_date", "end_date", "substitutions", "kpis", "backtest_name")

    kpis = serializers.ListSerializer(
        child=serializers.ChoiceField(choices=[x.value for x in BACKTEST_KPI_TYPES]),
        required=True,
    )
    substitutions = serializers.ListSerializer(
        child=BacktestSubstitutionMultiSerializer(), required=True, write_only=True
    )

    def create(self, validated_data):
        substitutions = validated_data.pop("substitutions")
        backtest_obj = Backtest.objects.create(**validated_data)
        for substitution_set in substitutions:
            new_plan_obj = substitution_set.pop("new_plan")
            old_plans = substitution_set.pop("old_plans")
            for old_plan_obj in old_plans:
                BacktestSubstitution.objects.create(
                    new_plan=new_plan_obj, old_plan=old_plan_obj, backtest=backtest_obj
                )
        return backtest_obj


class BacktestSummarySerializer(serializers.ModelSerializer):
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


class BacktestSubstitutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = BacktestSubstitution
        fields = ("new_plan", "old_plan")

    new_plan = BillingPlanSerializer()
    old_plan = BillingPlanSerializer()


class BacktestDetailSerializer(BacktestSummarySerializer):
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
            "backtest_substitutions",
            "backtest_results",
        )

    # backtest_substitutions = serializers.SerializerMethodField()

    # def get_backtest_substitutions(self, obj):
    #     return BacktestSubstitutionSerializer(obj.backtest_substitutions.all(), many=True).data
