from actstream.models import Action
from django.db.models import Q
from metering_billing.billable_metrics import METRIC_HANDLER_MAP
from metering_billing.models import (
    Alert,
    BillableMetric,
    CategoricalFilter,
    Customer,
    Event,
    ExternalPlanLink,
    Feature,
    Invoice,
    NumericFilter,
    Organization,
    OrganizationInviteToken,
    OrganizationSetting,
    Plan,
    PlanComponent,
    PlanVersion,
    PriceAdjustment,
    Product,
    Subscription,
    User,
)
from metering_billing.payment_providers import PAYMENT_PROVIDER_MAP
from metering_billing.utils import calculate_end_date, now_utc
from metering_billing.utils.enums import (
    MAKE_PLAN_VERSION_ACTIVE_TYPE,
    PLAN_STATUS,
    PLAN_VERSION_STATUS,
    REPLACE_IMMEDIATELY_TYPE,
    SUBSCRIPTION_STATUS,
)
from rest_framework import serializers

from .serializer_utils import SlugRelatedFieldWithOrganization


class OrganizationUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("username", "email", "role", "status")

    role = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    def get_role(self, obj) -> str:
        return "Admin"

    def get_status(self, obj) -> str:
        return "Active"


class OrganizationInvitedUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("email", "role", "status")

    role = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    def get_role(self, obj) -> str:
        return "Admin"

    def get_status(self, obj) -> str:
        return "Invited"


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = (
            "company_name",
            "payment_plan",
            "payment_provider_ids",
            "users",
        )

    users = serializers.SerializerMethodField()

    def get_users(self, obj) -> OrganizationUserSerializer(many=True):
        users = User.objects.filter(organization=obj)
        users_data = list(OrganizationUserSerializer(users, many=True).data)
        now = now_utc()
        invited_users = OrganizationInviteToken.objects.filter(
            organization=obj, expire_at__gt=now
        )
        invited_users_data = OrganizationInvitedUserSerializer(
            invited_users, many=True
        ).data
        invited_users_data = [{**x, "username": ""} for x in invited_users_data]
        return users_data + invited_users_data


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
        fields = ("billing_plan_name", "plan_version", "end_date", "auto_renew")
        list_serializer_class = FilterActiveSubscriptionSerializer

    billing_plan_name = serializers.CharField(source="billing_plan.plan.plan_name")
    plan_version = serializers.CharField(source="billing_plan.version")


class CustomerSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = (
            "customer_name",
            "customer_id",
            "subscriptions",
        )

    subscriptions = SubscriptionCustomerSummarySerializer(read_only=True, many=True)


class SubscriptionCustomerDetailSerializer(SubscriptionCustomerSummarySerializer):
    class Meta(SubscriptionCustomerSummarySerializer.Meta):
        model = Subscription
        fields = SubscriptionCustomerSummarySerializer.Meta.fields + (
            "subscription_id",
            "start_date",
            "end_date",
            "auto_renew",
            "status",
        )


class CustomerWithRevenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ("customer_id", "total_amount_due")

    total_amount_due = serializers.SerializerMethodField()

    def get_total_amount_due(self, obj) -> float:
        total_amount_due = float(self.context.get("total_amount_due"))
        return total_amount_due


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = (
            "customer_name",
            "customer_id",
        )

    def create(self, validated_data):
        customer = Customer.objects.create(**validated_data)
        org = customer.organization
        for connector in PAYMENT_PROVIDER_MAP.values():
            if connector.organization_connected(org):
                connector.create_customer(customer)
        return customer


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


class ExternalPlanLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExternalPlanLink
        fields = ("plan_id", "source", "external_plan_id")

    plan_id = SlugRelatedFieldWithOrganization(
        slug_field="plan_id",
        source="plan",
        queryset=Plan.objects.all(),
        write_only=True,
    )

    def validate(self, data):
        super().validate(data)
        query = ExternalPlanLink.objects.filter(
            organization=self.context["organization"],
            source=data["source"],
            external_plan_id=data["external_plan_id"],
        )
        if query.exists():
            plan_name = data["plan"].plan_name
            raise serializers.ValidationError(
                f"This external plan link already exists in plan {plan_name}"
            )
        return data


class InitialExternalPlanLinkSerializer(ExternalPlanLinkSerializer):
    class Meta(ExternalPlanLinkSerializer.Meta):
        model = ExternalPlanLink
        fields = tuple(
            set(ExternalPlanLinkSerializer.Meta.fields)
            - set(
                [
                    "plan_id",
                ]
            )
        )


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
            "invoice_id",
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


class CustomerDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = (
            "customer_id",
            "email",
            "customer_name",
            "invoices",
            "total_amount_due",
            "subscriptions",
        )

    subscriptions = SubscriptionCustomerDetailSerializer(read_only=True, many=True)
    invoices = serializers.SerializerMethodField()
    total_amount_due = serializers.SerializerMethodField()

    def get_invoices(self, obj) -> InvoiceSerializer(many=True):
        timeline = self.context.get("invoices")
        timeline = InvoiceSerializer(timeline, many=True).data
        return timeline

    def get_total_amount_due(self, obj) -> float:
        total_amount_due = float(self.context.get("total_amount_due"))
        return total_amount_due


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


class PriceAdjustmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceAdjustment
        fields = (
            "price_adjustment_name",
            "price_adjustment_description",
            "price_adjustment_type",
            "price_adjustment_amount",
        )

    price_adjustment_name = serializers.CharField(default="")


class PlanVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanVersion
        fields = (
            "description",
            "plan_id",
            "flat_fee_billing_type",
            "replace_plan_version_id",
            "flat_rate",
            "components",
            "features",
            "price_adjustment",
            # write only
            "make_active",
            "make_active_type",
            "replace_immediately_type",
            # read-only
            "version",
            "version_id",
            "active_subscriptions",
            "created_by",
            "created_on",
            "status",
        )
        read_only_fields = (
            "version",
            "version_id",
            "active_subscriptions",
            "created_by",
            "created_on",
            "status",
        )
        extra_kwargs = {
            "make_active_type": {"write_only": True},
            "replace_immediately_type": {"write_only": True},
        }

    components = PlanComponentSerializer(many=True, allow_null=True, required=False)
    features = FeatureSerializer(many=True, allow_null=True, required=False)
    price_adjustment = PriceAdjustmentSerializer(required=False)
    plan_id = SlugRelatedFieldWithOrganization(
        slug_field="plan_id",
        queryset=Plan.objects.all(),
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

    # WRITE ONLY
    make_active = serializers.BooleanField(write_only=True)
    make_active_type = serializers.ChoiceField(
        choices=MAKE_PLAN_VERSION_ACTIVE_TYPE.choices, required=False, write_only=True
    )
    replace_immediately_type = serializers.ChoiceField(
        choices=REPLACE_IMMEDIATELY_TYPE.choices, required=False, write_only=True
    )

    # READ-ONLY
    active_subscriptions = serializers.IntegerField(read_only=True)
    created_by = serializers.SerializerMethodField(read_only=True)

    def get_created_by(self, obj) -> str:
        if obj.created_by != None:
            return obj.created_by.username
        else:
            return None

    def validate(self, data):
        data = super().validate(data)
        if data.get("make_active") and not data.get("make_active_type"):
            raise serializers.ValidationError(
                "make_active_type must be specified when make_active is True"
            )
        if data.get(
            "make_active_type"
        ) == MAKE_PLAN_VERSION_ACTIVE_TYPE.REPLACE_IMMEDIATELY and not data.get(
            "replace_immediately_type"
        ):
            raise serializers.ValidationError(
                f"replace_immediately_type must be specified when make_active_type is {MAKE_PLAN_VERSION_ACTIVE_TYPE.REPLACE_IMMEDIATELY}"
            )
        return data

    def create(self, validated_data):
        # exctract downstream components
        components_data = validated_data.pop("components", [])
        features_data = validated_data.pop("features", [])
        price_adjustment_data = validated_data.pop("price_adjustment", None)
        make_active = validated_data.pop("make_active", False)
        make_active_type = validated_data.pop("make_active_type", None)
        replace_immediately_type = validated_data.pop("replace_immediately_type", None)
        # create planVersion initially
        validated_data["version"] = len(validated_data["plan"].versions.all()) + 1
        if "status" not in validated_data:
            validated_data["status"] = (
                PLAN_VERSION_STATUS.ACTIVE
                if make_active
                else PLAN_VERSION_STATUS.INACTIVE
            )
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
        if price_adjustment_data:
            price_adjustment_data["organization"] = org
            try:
                pa, _ = PriceAdjustment.objects.get_or_create(**price_adjustment_data)
            except PriceAdjustment.MultipleObjectsReturned:
                pa = PriceAdjustment.objects.filter(**price_adjustment_data).first()
            billing_plan.price_adjustment = pa
        billing_plan.save()
        if make_active:
            billing_plan.plan.make_version_active(
                billing_plan, make_active_type, replace_immediately_type
            )
        return billing_plan


class InitialPlanVersionSerializer(PlanVersionSerializer):
    class Meta(PlanVersionSerializer.Meta):
        model = PlanVersion
        fields = tuple(
            set(PlanVersionSerializer.Meta.fields)
            - set(
                [
                    "plan_id",
                    "replace_plan_version_id",
                    "make_active",
                    "make_active_type",
                    "replace_immediately_type",
                ]
            )
        )


class PlanNameAndIDSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = (
            "plan_name",
            "plan_id",
        )


class CustomerNameAndIDSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = (
            "customer_name",
            "customer_id",
        )


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = (
            "plan_name",
            "plan_duration",
            "product_id",
            "plan_id",
            "status",
            # write only
            "initial_external_links",
            "initial_version",
            "parent_plan_id",
            "target_customer_id",
            # read-only
            "external_links",
            "parent_plan",
            "target_customer",
            "created_on",
            "created_by",
            "display_version",
            "num_versions",
            "active_subscriptions",
        )
        read_only_fields = (
            "parent_plan",
            "target_customer",
            "created_on",
            "created_by",
            "display_version",
        )
        extra_kwargs = {
            "initial_version": {"write_only": True},
            "parent_plan_id": {"write_only": True},
            "target_customer_id": {"write_only": True},
        }

    product_id = SlugRelatedFieldWithOrganization(
        slug_field="product_id",
        queryset=Product.objects.all(),
        read_only=False,
        source="parent_product",
        required=False,
        allow_null=True,
    )

    # WRITE ONLY
    initial_version = InitialPlanVersionSerializer(write_only=True)
    parent_plan_id = SlugRelatedFieldWithOrganization(
        slug_field="plan_id",
        queryset=Plan.objects.all(),
        write_only=True,
        source="parent_plan",
        required=False,
    )
    target_customer_id = SlugRelatedFieldWithOrganization(
        slug_field="customer_id",
        queryset=Customer.objects.all(),
        write_only=True,
        source="target_customer",
        required=False,
    )
    initial_external_links = InitialExternalPlanLinkSerializer(
        many=True, required=False, write_only=True
    )

    # READ ONLY
    parent_plan = PlanNameAndIDSerializer(read_only=True)
    target_customer = CustomerNameAndIDSerializer(read_only=True)
    created_by = serializers.SerializerMethodField(read_only=True)
    display_version = PlanVersionSerializer(read_only=True)
    num_versions = serializers.SerializerMethodField(read_only=True)
    active_subscriptions = serializers.SerializerMethodField(read_only=True)
    external_links = ExternalPlanLinkSerializer(many=True, read_only=True)

    def get_created_by(self, obj) -> str:
        if obj.created_by:
            return obj.created_by.username
        else:
            return None

    def get_num_versions(self, obj) -> int:
        return len(obj.version_numbers())

    def get_active_subscriptions(self, obj) -> int:
        return sum(x.active_subscriptions for x in obj.active_subs_by_version())

    def validate(self, data):
        # we'll feed the version data into the serializer later, checking now breaks it
        plan_version = data.pop("initial_version")
        external_links = data.get("external_links")
        if external_links:
            data.pop("external_links")
        super().validate(data)
        target_cust_null = data.get("target_customer") is None
        parent_plan_null = data.get("parent_plan") is None
        if any([target_cust_null, parent_plan_null]) and not all(
            [target_cust_null, parent_plan_null]
        ):
            raise serializers.ValidationError(
                "either both or none of target_customer and parent_plan must be set"
            )
        data["initial_version"] = plan_version
        if external_links:
            data["external_links"] = external_links
        return data

    def create(self, validated_data):
        display_version_data = validated_data.pop("initial_version")
        external_links = validated_data.get("external_links")
        if external_links:
            validated_data.pop("external_links")
        plan = Plan.objects.create(**validated_data)
        display_version_data["status"] = PLAN_VERSION_STATUS.ACTIVE
        display_version_data["plan"] = plan
        display_version_data["organization"] = validated_data["organization"]
        display_version_data["created_by"] = validated_data["created_by"]
        plan_version = InitialPlanVersionSerializer().create(display_version_data)
        if external_links:
            for link_data in external_links:
                link_data["plan"] = plan
                link_data["organization"] = validated_data["organization"]
                ExternalPlanLinkSerializer().validate(link_data)
                InitialPlanVersionSerializer().create(link_data)
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

    status = serializers.ChoiceField(choices=[PLAN_STATUS.ACTIVE, PLAN_STATUS.ARCHIVED])

    def validate(self, data):
        data = super().validate(data)
        if data.get("status") == PLAN_STATUS.ARCHIVED:
            versions_count = self.instance.active_subs_by_version()
            cnt = sum([version.active_subscriptions for version in versions_count])
            if cnt > 0:
                raise serializers.ValidationError(
                    "Cannot archive a plan with active subscriptions"
                )
        return data

    def update(self, instance, validated_data):
        instance.plan_name = validated_data.get("plan_name", instance.plan_name)
        instance.status = validated_data.get("status", instance.status)
        instance.save()
        return instance


class PlanDetailSerializer(PlanSerializer):
    class Meta(PlanSerializer.Meta):
        model = Plan
        fields = tuple(
            set(PlanSerializer.Meta.fields).union(set(["versions"]))
            - set(
                [
                    "display_version",
                    "initial_version",
                    "parent_plan_id",
                    "target_customer_id",
                ]
            )
        )

    versions = serializers.SerializerMethodField()

    def get_versions(self, obj) -> PlanVersionSerializer(many=True):
        return PlanVersionSerializer(obj.versions.all(), many=True).data


## SUBSCRIPTION
class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = (
            "customer_id",
            "customer",
            "plan_id",
            "billing_plan",
            "start_date",
            "end_date",
            "status",
            "auto_renew",
            "is_new",
            "subscription_id",
        )
        read_only_fields = ("customer", "billing_plan")

    start_date = serializers.DateTimeField()
    end_date = serializers.DateTimeField(required=False)
    auto_renew = serializers.BooleanField(required=False)
    is_new = serializers.BooleanField(required=False)
    subscription_id = serializers.CharField(required=False)

    # WRITE ONLY
    customer_id = SlugRelatedFieldWithOrganization(
        slug_field="customer_id",
        read_only=False,
        source="customer",
        queryset=Customer.objects.all(),
        write_only=True,
    )
    plan_id = SlugRelatedFieldWithOrganization(
        slug_field="plan_id",
        read_only=False,
        source="billing_plan.plan",
        queryset=Plan.objects.all(),
        write_only=True,
    )

    # READ ONLY
    customer = CustomerSerializer(read_only=True)
    billing_plan = PlanVersionSerializer(read_only=True)

    def validate(self, data):
        # extract the plan version from the plan
        data["billing_plan"] = data["billing_plan"]["plan"].display_version
        # check no existing subs
        sd = data["start_date"]
        ed = calculate_end_date(data["billing_plan"].plan.plan_duration, sd)
        num_existing_subs = Subscription.objects.filter(
            Q(start_date__range=(sd, ed)) | Q(end_date__range=(sd, ed)),
            customer__customer_id=data["customer"].customer_id,
            billing_plan__version_id=data["billing_plan"].version_id,
            status=SUBSCRIPTION_STATUS.ACTIVE,
        ).count()
        if num_existing_subs > 0:
            raise serializers.ValidationError(
                f"Customer already has an active subscription to this plan"
            )

        # # check that customer and billing_plan currencies match
        # customer_currency = data["customer"].balance.currency
        # billing_plan_currency = data["billing_plan"].flat_rate.currency
        # if customer_currency != billing_plan_currency:
        #     raise serializers.ValidationError(
        #         f"Customer currency {customer_currency} does not match billing plan currency {billing_plan_currency}"
        #     )

        # check that if the plan is designed for a specific customer, that the customer is that customer
        tc = data["billing_plan"].plan.target_customer
        if tc is not None and tc != data["customer"]:
            raise serializers.ValidationError(
                f"This plan is for a customer with customer_id {tc.customer_id}, not {data['customer'].customer_id}"
            )
        return data


class SubscriptionUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ("plan_id", "status", "auto_renew", "replace_immediately_type")

    plan_id = SlugRelatedFieldWithOrganization(
        slug_field="plan_id",
        read_only=False,
        source="billing_plan.plan",
        queryset=Plan.objects.all(),
        write_only=True,
        required=False,
    )
    status = serializers.ChoiceField(
        choices=[SUBSCRIPTION_STATUS.ENDED], required=False
    )
    auto_renew = serializers.BooleanField(required=False)
    replace_immediately_type = serializers.ChoiceField(
        choices=REPLACE_IMMEDIATELY_TYPE.choices, write_only=True
    )

    def validate(self, data):
        data = super().validate(data)
        # extract the plan version from the plan
        if data.get("billing_plan"):
            data["billing_plan"] = data["billing_plan"]["plan"].display_version
        if data.get("status") and data.get("billing_plan"):
            raise serializers.ValidationError(
                "Can only change one of status and plan version"
            )
        if (data.get("status") or data.get("billing_plan")) and not data.get(
            "replace_immediately_type"
        ):
            raise serializers.ValidationError(
                "To specify status or plan_id change, must specify replace_immediately_type"
            )
        if (
            data.get("status")
            and data.get("replace_immediately_type")
            == REPLACE_IMMEDIATELY_TYPE.CHANGE_SUBSCRIPTION_PLAN
        ):
            raise serializers.ValidationError(
                "Cannot use CHANGE_SUBSCRIPTION_PLAN replace type with ending a subscription"
            )
        return data

    def update(self, instance, validated_data):
        instance.auto_renew = validated_data.get("auto_renew", instance.auto_renew)
        new_bp = validated_data.get("billing_plan")
        if (
            validated_data.get("replace_immediately_type")
            == REPLACE_IMMEDIATELY_TYPE.CHANGE_SUBSCRIPTION_PLAN
        ):
            instance.switch_subscription_bp(new_bp)
        elif validated_data.get("status") or new_bp:
            instance.end_subscription_now(
                bill=validated_data.get("replace_immediately_type")
                == REPLACE_IMMEDIATELY_TYPE.END_CURRENT_SUBSCRIPTION_AND_BILL
            )
            if new_bp is not None:
                Subscription.objects.create(
                    billing_plan=new_bp,
                    organization=instance.organization,
                    customer=instance.customer,
                    start_date=instance.end_date,
                    status=SUBSCRIPTION_STATUS.ACTIVE,
                    auto_renew=True,
                    is_new=False,
                )
        instance.save()
        return instance


class ExperimentalToActiveRequestSerializer(serializers.Serializer):
    version_id = SlugRelatedFieldWithOrganization(
        queryset=PlanVersion.objects.filter(plan__status=PLAN_STATUS.EXPERIMENTAL),
        slug_field="version_id",
        read_only=False,
    )


class SubscriptionActionSerializer(SubscriptionSerializer):
    class Meta(SubscriptionSerializer.Meta):
        model = Subscription
        fields = SubscriptionSerializer.Meta.fields + ("string_repr", "object_type")

    string_repr = serializers.SerializerMethodField()
    object_type = serializers.SerializerMethodField()

    def get_string_repr(self, obj):
        return obj.subscription_id

    def get_object_type(self, obj):
        return "Subscription"


class UserActionSerializer(OrganizationUserSerializer):
    class Meta(OrganizationUserSerializer.Meta):
        model = User
        fields = OrganizationUserSerializer.Meta.fields + ("string_repr",)

    string_repr = serializers.SerializerMethodField()

    def get_string_repr(self, obj):
        return obj.username


class PlanVersionActionSerializer(PlanVersionSerializer):
    class Meta(PlanVersionSerializer.Meta):
        model = PlanVersion
        fields = PlanVersionSerializer.Meta.fields + ("string_repr", "object_type")

    string_repr = serializers.SerializerMethodField()
    object_type = serializers.SerializerMethodField()

    def get_string_repr(self, obj):
        return obj.plan.plan_name + " v" + str(obj.version)

    def get_object_type(self, obj):
        return "Plan Version"


class PlanActionSerializer(PlanSerializer):
    class Meta(PlanSerializer.Meta):
        model = Plan
        fields = PlanSerializer.Meta.fields + ("string_repr", "object_type")

    string_repr = serializers.SerializerMethodField()
    object_type = serializers.SerializerMethodField()

    def get_string_repr(self, obj):
        return obj.plan_name

    def get_object_type(self, obj):
        return "Plan"


class BillableMetricActionSerializer(BillableMetricSerializer):
    class Meta(BillableMetricSerializer.Meta):
        model = BillableMetric
        fields = BillableMetricSerializer.Meta.fields + ("string_repr", "object_type")

    string_repr = serializers.SerializerMethodField()
    object_type = serializers.SerializerMethodField()

    def get_string_repr(self, obj):
        return obj.billable_metric_name

    def get_object_type(self, obj):
        return "Metric"


class CustomerActionSerializer(CustomerSerializer):
    class Meta(CustomerSerializer.Meta):
        model = Customer
        fields = CustomerSerializer.Meta.fields + ("string_repr", "object_type")

    string_repr = serializers.SerializerMethodField()
    object_type = serializers.SerializerMethodField()

    def get_string_repr(self, obj):
        return obj.customer_name

    def get_object_type(self, obj):
        return "Customer"


GFK_MODEL_SERIALIZER_MAPPING = {
    User: UserActionSerializer,
    PlanVersion: PlanVersionActionSerializer,
    Plan: PlanActionSerializer,
    Subscription: SubscriptionActionSerializer,
    BillableMetric: BillableMetricActionSerializer,
    Customer: CustomerActionSerializer,
}


class ActivityGenericRelatedField(serializers.Field):
    """
    DRF Serializer field that serializers GenericForeignKey fields on the :class:`~activity.models.Action`
    of known model types to their respective ActionSerializer implementation.
    """

    def to_representation(self, value):
        serializer_cls = GFK_MODEL_SERIALIZER_MAPPING.get(type(value), None)
        return (
            serializer_cls(value, context=self.context).data
            if serializer_cls
            else str(value)
        )


class ActionSerializer(serializers.ModelSerializer):
    """
    DRF serializer for :class:`~activity.models.Action`.
    """

    actor = ActivityGenericRelatedField(read_only=True)
    action_object = ActivityGenericRelatedField(read_only=True)
    target = ActivityGenericRelatedField(read_only=True)

    class Meta:
        model = Action
        fields = (
            "id",
            "actor",
            "verb",
            "action_object",
            "target",
            "public",
            "description",
            "timestamp",
        )


class OrganizationSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationSetting
        fields = ("setting_id", "setting_name", "setting_value", "setting_group")
        read_only_fields = ("setting_id", "setting_name", "setting_group")

    def update(self, instance, validated_data):
        instance.setting_value = validated_data.get(
            "setting_value", instance.setting_value
        )
        instance.save()
        return instance
