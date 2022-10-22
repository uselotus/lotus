import datetime

from django.db.models import Q
from metering_billing.billable_metrics import METRIC_HANDLER_MAP
from metering_billing.models import (
    Alert,
    Backtest,
    BacktestSubstitution,
    BillableMetric,
    CategoricalFilter,
    Customer,
    Event,
    Feature,
    Invoice,
    NumericFilter,
    Organization,
    Plan,
    PlanComponent,
    PlanVersion,
    Product,
    Subscription,
    User,
)
from metering_billing.utils import calculate_end_date
from metering_billing.utils.enums import (
    BACKTEST_KPI,
    MAKE_PLAN_VERSION_ACTIVE_TYPE,
    PLAN_STATUS,
    PLAN_VERSION_STATUS,
    REPLACE_IMMEDIATELY_TYPE,
    SUBSCRIPTION_STATUS,
)
from numpy import require
from rest_framework import serializers

from .serializer_utils import SlugRelatedFieldWithOrganization


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
            "customer",
        )

    customer_id = SlugRelatedFieldWithOrganization(
        slug_field="customer_id",
        queryset=Customer.objects.all(),
        write_only=True,
        source="customer",
    )
    customer = serializers.SerializerMethodField()

    def get_customer(self, obj) -> str:
        return obj.customer.customer_id


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
        data = [x for x in data if x.status == SUBSCRIPTION_STATUS.ACTIVE]
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
            "billable_metric_name",
            "billable_metric",
            "free_metric_units",
            "cost_per_batch",
            "metric_units_per_batch",
            "max_metric_units",
        )
        read_only_fields = ["billable_metric"]

    # READ-ONLY
    billable_metric = BillableMetricSerializer(read_only=True)

    # WRITE-ONLY
    billable_metric_name = serializers.SlugRelatedField(
        slug_field="billable_metric_name",
        write_only=True,
        source="billable_metric",
        queryset=BillableMetric.objects.all(),
    )

    # both
    free_metric_units = serializers.FloatField(allow_null=True, default=0)
    cost_per_batch = serializers.FloatField(allow_null=True, default=0)
    metric_units_per_batch = serializers.FloatField(allow_null=True, default=1)

    def get_fields(self, *args, **kwargs):
        fields = super().get_fields(*args, **kwargs)
        bmqs = fields["billable_metric_name"].queryset
        fields["billable_metric_name"].queryset = bmqs.filter(
            organization=self.context["organization"]
        )
        return fields

    def validate(self, data):
        # fmu, cpb, and mupb must all be none or all be not none
        fmu = data.get("free_metric_units", None)
        cpb = data.get("cost_per_batch", None)
        mupb = data.get("metric_units_per_batch", None)
        together = [
            fmu is not None,
            cpb is not None,
            mupb is not None,
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


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ("name", "description", "product_id", "status")


class PlanVersionUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanVersion
        fields = (
            "description",
            "status",
            "make_active_type",
            "replace_immediately_type",
        )

    make_active_type = serializers.ChoiceField(
        choices=MAKE_PLAN_VERSION_ACTIVE_TYPE.choices,
        required=False,
    )
    replace_immediately_type = serializers.ChoiceField(
        choices=REPLACE_IMMEDIATELY_TYPE.choices, required=False
    )
    status = serializers.ChoiceField(
        choices=[PLAN_VERSION_STATUS.ACTIVE, PLAN_VERSION_STATUS.ARCHIVED],
        required=False,
    )

    def validate(self, data):
        data = super().validate(data)
        if (
            data.get("status") == PLAN_VERSION_STATUS.ARCHIVED
            and self.instance.num_active_subs() > 0
        ):
            raise serializers.ValidationError(
                "Can't archive a plan with active subscriptions."
            )
        if (
            data.get("status") == PLAN_VERSION_STATUS.ACTIVE
            and data.get("make_active_type")
            == MAKE_PLAN_VERSION_ACTIVE_TYPE.REPLACE_IMMEDIATELY
            and not data.get("immediate_active_type")
        ):
            raise serializers.ValidationError(
                f"immediate_active_type must be specified when make_active_type is {MAKE_PLAN_VERSION_ACTIVE_TYPE.REPLACE_IMMEDIATELY}"
            )
        return data

    def update(self, instance, validated_data):
        instance.description = validated_data.get("description", instance.description)
        instance.status = validated_data.get("status", instance.status)
        if validated_data.get("status") == PLAN_VERSION_STATUS.ACTIVE:
            parent_plan = instance.plan
            parent_plan.make_version_active(
                instance,
                validated_data.get("make_active_type"),
                validated_data.get("replace_immediately_type"),
            )
        instance.save()
        return instance


class PlanVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanVersion
        fields = (
            "description",
            "version",
            "plan_id",
            "flat_fee_billing_type",
            "usage_billing_type",
            "status",
            "replace_plan_version_id",
            "flat_rate",
            "components",
            "features",
            "created_on",
            "created_by",
            "active_subscriptions",
            "version_id",
            "make_active_type",
            "replace_immediately_type",
        )
        read_only_fields = (
            "active_subscriptions",
            "version_id",
        )

    components = PlanComponentSerializer(many=True, allow_null=True, required=False)
    features = FeatureSerializer(many=True, allow_null=True, required=False)
    status = serializers.ChoiceField(
        choices=[PLAN_VERSION_STATUS.ACTIVE, PLAN_VERSION_STATUS.INACTIVE]
    )
    make_active_type = serializers.ChoiceField(
        choices=MAKE_PLAN_VERSION_ACTIVE_TYPE.choices,
        required=False,
    )
    replace_immediately_type = serializers.ChoiceField(
        choices=REPLACE_IMMEDIATELY_TYPE.choices, required=False
    )

    # WRITE ONLY
    plan_id = SlugRelatedFieldWithOrganization(
        slug_field="plan_id",
        queryset=Plan.objects.all(),
        write_only=True,
        source="plan",
        required=False,
    )
    replace_plan_version_id = SlugRelatedFieldWithOrganization(
        slug_field="plan_id",
        queryset=PlanVersion.objects.all(),
        write_only=True,
        source="replace_with",
        required=False,
    )
    version = serializers.IntegerField(read_only=True)

    # READ-ONLY
    active_subscriptions = serializers.IntegerField(read_only=True)
    created_by = serializers.SerializerMethodField(read_only=True)

    def get_created_by(self, obj) -> str:
        if obj.created_by:
            return obj.created_by.username
        else:
            return None

    def create(self, validated_data):
        components_data = validated_data.pop("components", [])
        features_data = validated_data.pop("features", [])
        make_active_type = validated_data.pop("make_active_type", None)
        replace_immediately_type = validated_data.pop("replace_immediately_type", None)
        validated_data["version"] = len(validated_data["plan"].versions.all()) + 1
        billing_plan = PlanVersion.objects.create(**validated_data)
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
        billing_plan.plan.add_new_version(
            billing_plan,
            make_active_type,
            replace_immediately_type,
        )
        return billing_plan


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = (
            "plan_name",
            "plan_duration",
            "display_version",
            "initial_version",
            "product_id",
            "status",
            "plan_id",
            "created_on",
            "created_by",
        )
        read_only_fields = ("created_on", "created_by", "display_version")
        extra_kwargs = {
            "parent_product": {"write_only": True},
            "status": {"write_only": True},
        }

    product_id = SlugRelatedFieldWithOrganization(
        slug_field="product_id",
        queryset=Product.objects.all(),
        read_only=False,
        source="parent_product",
    )

    # WRITE ONLY
    initial_version = PlanVersionSerializer(write_only=True)

    # READ ONLY
    created_by = serializers.SerializerMethodField(read_only=True)
    display_version = PlanVersionSerializer(read_only=True)

    def get_created_by(self, obj) -> str:
        return obj.created_by.username

    def validate(self, data):
        # we'll feed the version data into the serializer later, checking now breaks it
        plan_version = data.pop("initial_version")
        super().validate(data)
        data["initial_version"] = plan_version
        return data

    def create(self, validated_data):
        display_version_data = validated_data.pop("initial_version")
        plan = Plan.objects.create(**validated_data)
        display_version_data["plan_id"] = plan.plan_id
        serializer = PlanVersionSerializer(data=display_version_data)
        serializer.is_valid(raise_exception=True)
        plan_version = serializer.save(
            organization=validated_data["organization"],
            created_by=validated_data["created_by"],
        )
        plan.display_version = plan_version
        plan.save()
        return plan


class PlanUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = (
            "plan_name",
            "status",
        )

    status = serializers.ChoiceField(choices=[PLAN_STATUS.ACTIVE, PLAN_STATUS.INACTIVE])

    def validate(self, data):
        data = super().validate(data)
        if data.get("status") == PLAN_STATUS.INACTIVE:
            versions_count = self.instance.active_subs_by_version()
            cnt = sum([version.active_subscriptions for version in versions_count])
            if cnt > 0:
                raise serializers.ValidationError(
                    "Cannot make a plan with active subscriptions inactive"
                )
        return data

    def update(self, instance, validated_data):
        instance.plan_name = validated_data.get("plan_name", instance.plan_name)
        instance.status = validated_data.get("status", instance.status)
        instance.save()
        return instance


class PlanDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = (
            "plan_name",
            "plan_duration",
            "versions",
            "product_id",
            "status",
            "plan_id",
            "created_on",
            "created_by",
        )

    versions = PlanVersionSerializer(many=True)
    created_by = serializers.SerializerMethodField(read_only=True)
    product_id = SlugRelatedFieldWithOrganization(
        slug_field="product_id",
        read_only=True,
        source="parent_product",
    )

    def get_created_by(self, obj) -> str:
        return obj.created_by.username


## SUBSCRIPTION
class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = (
            "customer_id",
            "version_id",
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
    version_id = serializers.SlugRelatedField(
        slug_field="version_id",
        read_only=False,
        source="billing_plan",
        queryset=PlanVersion.objects.all(),
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
        bpqs = fields["version_id"].queryset
        fields["version_id"].queryset = bpqs.filter(
            organization=self.context["organization"]
        )
        return fields

    def validate(self, data):
        # check no existing subs
        sd = data["start_date"]
        ed = calculate_end_date(data["billing_plan"].plan.plan_duration, sd)
        num_existing_subs = Subscription.objects.filter(
            Q(start_date__range=(sd, ed)) | Q(end_date__range=(sd, ed)),
            customer__customer_id=data["customer"].customer_id,
            billing_plan__version_id=data["billing_plan"].version_id,
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
    billing_plan = PlanVersionSerializer()
