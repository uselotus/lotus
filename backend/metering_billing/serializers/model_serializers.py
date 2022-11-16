from datetime import timedelta
from decimal import Decimal
from typing import Union

from actstream.models import Action
from django.db.models import Q
from metering_billing.billable_metrics import METRIC_HANDLER_MAP
from metering_billing.exceptions import DuplicateBillableMetric
from metering_billing.models import (
    Alert,
    BillableMetric,
    CategoricalFilter,
    Customer,
    CustomerBalanceAdjustment,
    Event,
    ExternalPlanLink,
    Feature,
    Invoice,
    InvoiceLineItem,
    NumericFilter,
    Organization,
    OrganizationInviteToken,
    OrganizationSetting,
    Plan,
    PlanComponent,
    PlanVersion,
    PriceAdjustment,
    PriceTier,
    Product,
    Subscription,
    User,
)
from metering_billing.payment_providers import PAYMENT_PROVIDER_MAP
from metering_billing.utils import calculate_end_date, now_utc
from metering_billing.utils.enums import (
    BATCH_ROUNDING_TYPE,
    EVENT_TYPE,
    FLAT_FEE_BILLING_TYPE,
    INVOICE_STATUS,
    MAKE_PLAN_VERSION_ACTIVE_TYPE,
    METRIC_GRANULARITY,
    PAYMENT_PROVIDERS,
    PLAN_STATUS,
    PLAN_VERSION_STATUS,
    PRICE_TIER_TYPE,
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
            # "customer_id",
            "customer",
        )

    # customer_id = SlugRelatedFieldWithOrganization(
    #     slug_field="customer_id",
    #     queryset=Customer.objects.all(),
    #     write_only=True,
    #     source="customer",
    # )
    customer = serializers.SerializerMethodField()

    def get_customer(self, obj) -> str:
        return obj.customer_id


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
            "email",
            "payment_provider",
            "payment_provider_id",
            "properties",
        )
        read_only_fields = ("properties",)
        extra_kwargs = {
            "customer_id": {"required": True},
            "email": {"required": True},
        }

    payment_provider_id = serializers.CharField(
        required=False, allow_null=True, write_only=True
    )
    email = serializers.EmailField(required=True)

    def validate(self, data):
        super().validate(data)
        payment_provider = data.get("payment_provider", None)
        payment_provider_id = data.get("payment_provider_id", None)
        if payment_provider or payment_provider_id:
            if not PAYMENT_PROVIDER_MAP[payment_provider].organization_connected(
                self.context["organization"]
            ):
                raise serializers.ValidationError(
                    "Specified payment provider not connected to organization"
                )
            if payment_provider and not payment_provider_id:
                raise serializers.ValidationError(
                    "Payment provider ID required when payment provider is specified"
                )
            if payment_provider_id and not payment_provider:
                raise serializers.ValidationError(
                    "Payment provider required when payment provider ID is specified"
                )

        return data

    def create(self, validated_data):
        pp_id = validated_data.pop("payment_provider_id", None)
        customer = Customer.objects.create(**validated_data)
        if pp_id:
            customer_properties = customer.properties
            customer_properties[validated_data["payment_provider"]] = {}
            customer_properties[validated_data["payment_provider"]]["id"] = pp_id
            customer.properties = customer_properties
            customer.save()
        else:
            if "payment_provider" in validated_data:
                PAYMENT_PROVIDER_MAP[
                    validated_data["payment_provider"]
                ].create_customer(customer)
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
            "usage_aggregation_type",
            "billable_aggregation_type",
            "granularity",
            "event_type",
            "metric_type",
            "billable_metric_name",
            "numeric_filters",
            "categorical_filters",
            "properties",
        )
        extra_kwargs = {
            "metric_type": {"required": True},
            "usage_aggregation_type": {"required": True},
            "event_name": {"required": True},
        }

    numeric_filters = NumericFilterSerializer(
        many=True, allow_null=True, required=False
    )
    categorical_filters = CategoricalFilterSerializer(
        many=True, allow_null=True, required=False
    )
    granularity = serializers.ChoiceField(
        choices=METRIC_GRANULARITY.choices,
        required=False,
    )
    event_type = serializers.ChoiceField(
        choices=EVENT_TYPE.choices,
        required=False,
    )
    properties = serializers.JSONField(allow_null=True, required=False)

    def validate(self, data):
        super().validate(data)
        metric_type = data["metric_type"]
        data = METRIC_HANDLER_MAP[metric_type].validate_data(data)
        return data

    def custom_name(self, validated_data) -> str:
        name = validated_data.get("billable_metric_name", None)
        if name in [None, "", " "]:
            name = f"[{validated_data['metric_type'][:4]}]"
            name += " " + validated_data["usage_aggregation_type"] + " of"
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

        bm, created = BillableMetric.objects.get_or_create(**validated_data)
        if not created:
            raise DuplicateBillableMetric

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


class PriceTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceTier
        fields = (
            "type",
            "range_start",
            "range_end",
            "cost_per_batch",
            "metric_units_per_batch",
            "batch_rounding_type",
        )

    def validate(self, data):
        data = super().validate(data)
        rs = data.get("range_start", None)
        assert rs is not None and rs >= Decimal(0), "range_start must be >= 0"
        assert data.get("range_end", float("inf")) > data.get("range_start")
        if data.get("type") == PRICE_TIER_TYPE.FLAT:
            assert data.get("cost_per_batch")
            data["metric_units_per_batch"] = None
            data["batch_rounding_type"] = None
        elif data.get("type") == PRICE_TIER_TYPE.FREE:
            data["cost_per_batch"] = None
            data["metric_units_per_batch"] = None
            data["batch_rounding_type"] = None
        elif data.get("type") == PRICE_TIER_TYPE.PER_UNIT:
            assert data.get("metric_units_per_batch")
            assert data.get("cost_per_batch")
            data["batch_rounding_type"] = BATCH_ROUNDING_TYPE.NO_ROUNDING
            assert data.get("batch_rounding_type")
        else:
            raise serializers.ValidationError("Invalid price tier type")
        return data

    def create(self, validated_data):
        return PriceTier.objects.create(**validated_data)


## PLAN COMPONENT
class PlanComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanComponent
        fields = ("billable_metric_name", "billable_metric", "tiers")
        read_only_fields = ["billable_metric"]

    # READ-ONLY
    billable_metric = BillableMetricSerializer(read_only=True)

    # WRITE-ONLY
    billable_metric_name = SlugRelatedFieldWithOrganization(
        slug_field="billable_metric_name",
        write_only=True,
        source="billable_metric",
        queryset=BillableMetric.objects.all(),
    )

    # both
    tiers = PriceTierSerializer(many=True)

    def validate(self, data):
        data = super().validate(data)
        tiers = data.get("tiers")
        assert len(tiers) > 0, "Must have at least one price tier"
        tiers_sorted = sorted(tiers, key=lambda x: x["range_start"])
        assert tiers_sorted[0]["range_start"] == 0, "First tier must start at 0"
        assert all(
            x["range_end"] for x in tiers_sorted[:-1]
        ), "All tiers must have an end, last one is the only one allowed to have open end"
        for i, tier in enumerate(tiers_sorted[:-1]):
            assert (
                tier["range_end"] == tiers_sorted[i + 1]["range_start"]
            ), "All tiers must be contiguous"
        return data

    def create(self, validated_data):
        tiers = validated_data.pop("tiers")
        pc = PlanComponent.objects.create(**validated_data)
        for tier in tiers:
            tier = PriceTierSerializer().create(tier)
            assert type(tier) == PriceTier
            tier.plan_component = pc
            tier.save()
        return pc


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
            "transition_to_plan_id",
            "transition_to_plan_version_id",
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
    transition_to_plan_id = SlugRelatedFieldWithOrganization(
        slug_field="plan_id",
        queryset=Plan.objects.all(),
        write_only=True,
        required=False,
    )
    transition_to_plan_version_id = SlugRelatedFieldWithOrganization(
        slug_field="version_id",
        queryset=PlanVersion.objects.all(),
        write_only=True,
        required=False,
    )

    def validate(self, data):
        transition_to_plan_id = data.get("transition_to_plan_id")
        transition_to_plan_version_id = data.get("transition_to_plan_version_id")
        assert not (
            transition_to_plan_id and transition_to_plan_version_id
        ), "Can't specify both transition_to_plan_id and transition_to_plan_version_id"
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
        transition_to_plan = validated_data.get("transition_to_plan_id", None)
        transition_to_plan_version = validated_data.get(
            "transition_to_plan_version_id", None
        )
        if transition_to_plan:
            instance.transition_to = transition_to_plan.display_version
        elif transition_to_plan_version:
            instance.transition_to = transition_to_plan_version
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
            "flat_rate",
            "components",
            "features",
            "price_adjustment",
            "usage_billing_frequency",
            # write only
            "make_active",
            "make_active_type",
            "replace_immediately_type",
            "transition_to_plan_id",
            # "transition_to_plan_version_id",
            # read-only
            "version",
            "version_id",
            "active_subscriptions",
            "created_by",
            "created_on",
            "status",
            "replace_with",
            "transition_to",
        )
        read_only_fields = (
            "version",
            "version_id",
            "active_subscriptions",
            "created_by",
            "created_on",
            "status",
            "replace_with",
            "transition_to",
        )
        extra_kwargs = {
            "make_active_type": {"write_only": True},
            "replace_immediately_type": {"write_only": True},
        }

    components = PlanComponentSerializer(many=True, allow_null=True, required=False, source="plan_components")
    features = FeatureSerializer(many=True, allow_null=True, required=False)
    price_adjustment = PriceAdjustmentSerializer(required=False)
    plan_id = SlugRelatedFieldWithOrganization(
        slug_field="plan_id",
        queryset=Plan.objects.all(),
        source="plan",
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
    transition_to_plan_id = SlugRelatedFieldWithOrganization(
        slug_field="plan_id",
        queryset=Plan.objects.all(),
        write_only=True,
        required=False,
    )
    # transition_to_plan_version_id = SlugRelatedFieldWithOrganization(
    #     slug_field="version_id",
    #     queryset=PlanVersion.objects.all(),
    #     write_only=True,
    #     required=False,
    # )

    # READ-ONLY
    active_subscriptions = serializers.IntegerField(read_only=True)
    created_by = serializers.SerializerMethodField(read_only=True)
    replace_with = serializers.SerializerMethodField(read_only=True)
    transition_to = serializers.SerializerMethodField(read_only=True)

    def get_created_by(self, obj) -> str:
        if obj.created_by != None:
            return obj.created_by.username
        else:
            return None

    def get_replace_with(self, obj) -> Union[int, None]:
        if obj.replace_with != None:
            return obj.replace_with.version
        else:
            return None

    def get_transition_to(self, obj) -> Union[str, None]:
        if obj.transition_to != None:
            return str(obj.transition_to.display_version)
        else:
            return None

    def validate(self, data):
        # transition_to_plan_id = data.get("transition_to_plan_id")
        # transition_to_plan_version_id = data.get("transition_to_plan_version_id")
        # assert not (
        #     transition_to_plan_id and transition_to_plan_version_id
        # ), "Can't specify both transition_to_plan_id and transition_to_plan_version_id"
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
        components_data = validated_data.pop("components", [])
        if len(components_data) > 0:
            components = PlanComponentSerializer(many=True).create(components_data)
            assert type(components[0]) == PlanComponent
        else:
            components = []
        features_data = validated_data.pop("features", [])
        price_adjustment_data = validated_data.pop("price_adjustment", None)
        make_active = validated_data.pop("make_active", False)
        make_active_type = validated_data.pop("make_active_type", None)
        replace_immediately_type = validated_data.pop("replace_immediately_type", None)
        transition_to_plan = validated_data.get("transition_to_plan_id", None)
        # transition_to_plan_version = validated_data.get(
        #     "transition_to_plan_version_id", None
        # )
        # create planVersion initially
        validated_data["version"] = len(validated_data["plan"].versions.all()) + 1
        if "status" not in validated_data:
            validated_data["status"] = (
                PLAN_VERSION_STATUS.ACTIVE
                if make_active
                else PLAN_VERSION_STATUS.INACTIVE
            )
        billing_plan = PlanVersion.objects.create(**validated_data)
        if transition_to_plan:
            billing_plan.transition_to = transition_to_plan.display_version
        # elif transition_to_plan_version:
        #     billing_plan.transition_to = transition_to_plan_version
        org = billing_plan.organization
        for component in components:
            component.plan_version = billing_plan
            component.save()
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
        initial_external_links = data.get("initial_external_links")
        if initial_external_links:
            data.pop("initial_external_links")
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
        if initial_external_links:
            data["initial_external_links"] = initial_external_links
        return data

    def create(self, validated_data):
        display_version_data = validated_data.pop("initial_version")
        initial_external_links = validated_data.get("initial_external_links")
        if initial_external_links:
            validated_data.pop("initial_external_links")
        plan = Plan.objects.create(**validated_data)
        display_version_data["status"] = PLAN_VERSION_STATUS.ACTIVE
        display_version_data["plan"] = plan
        display_version_data["organization"] = validated_data["organization"]
        display_version_data["created_by"] = validated_data["created_by"]
        plan_version = InitialPlanVersionSerializer().create(display_version_data)
        if initial_external_links:
            for link_data in initial_external_links:
                link_data["plan"] = plan
                link_data["organization"] = validated_data["organization"]
                ExternalPlanLinkSerializer(
                    context={"organization": validated_data["organization"]}
                ).validate(link_data)
                ExternalPlanLinkSerializer().create(link_data)
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
            "scheduled_end_date",
            "status",
            "auto_renew",
            "is_new",
            "subscription_id",
        )
        read_only_fields = (
            "customer",
            "billing_plan",
            "scheduled_end_date",
        )

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
        # check that if the plan is designed for a specific customer, that the customer is that customer
        tc = data["billing_plan"].plan.target_customer
        if tc is not None and tc != data["customer"]:
            raise serializers.ValidationError(
                f"This plan is for a customer with customer_id {tc.customer_id}, not {data['customer'].customer_id}"
            )
        return data

    def create(self, validated_data):
        sub = super().create(validated_data)
        # new subscription means we need to create an invoice if its pay in advance
        billing_plan_name = sub.billing_plan.plan.plan_name
        billing_plan_version = sub.billing_plan.version
        if sub.billing_plan.flat_fee_billing_type == FLAT_FEE_BILLING_TYPE.IN_ADVANCE:
            invoice = Invoice.objects.create(
                cost_due=sub.billing_plan.flat_rate,
                issue_date=now_utc(),
                payment_status=INVOICE_STATUS.UNPAID,
                line_items=[
                    {
                        "name": f"{billing_plan_name} v{billing_plan_version} Flat Fee",
                        "start_date": str(sub.start_date),
                        "end_date": str(sub.end_date),
                        "quantity": 1,
                        "subtotal": float(sub.billing_plan.flat_rate.amount),
                        "type": "In Advance",
                    }
                ],
                organization=sub.organization,
                customer=sub.customer,
                subscription=sub,
            )
            invoice.cust_connected_to_payment_provider = False
            invoice.org_connected_to_cust_payment_provider = False
            for pp in sub.customer.integrations.keys():
                if pp in PAYMENT_PROVIDER_MAP and PAYMENT_PROVIDER_MAP[pp].working():
                    pp_connector = PAYMENT_PROVIDER_MAP[pp]
                    customer_conn = pp_connector.customer_connected(sub.customer)
                    org_conn = pp_connector.organization_connected(sub.organization)
                    if customer_conn:
                        invoice.cust_connected_to_payment_provider = True
                    if customer_conn and org_conn:
                        invoice.external_payment_obj_id = (
                            pp_connector.create_payment_object(invoice)
                        )
                        invoice.external_payment_obj_type = pp
                        invoice.org_connected_to_cust_payment_provider = True
                        break
            invoice.save()
        return sub


class SubscriptionInvoiceSerializer(SubscriptionSerializer):
    class Meta:
        model = Customer
        fields = ("customer_name",)

    class Meta(SubscriptionSerializer.Meta):
        model = Subscription
        fields = fields = tuple(
            set(SubscriptionSerializer.Meta.fields)
            - set(
                [
                    "customer_id",
                    "plan_id",
                    "billing_plan",
                    "auto_renew",
                ]
            )
        )


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
            replace_type = validated_data.get("replace_immediately_type")
            prorate = True if new_bp else False
            bill_usage = (
                replace_type
                == REPLACE_IMMEDIATELY_TYPE.END_CURRENT_SUBSCRIPTION_AND_BILL
            )
            instance.end_subscription_now(prorate=prorate, bill_usage=bill_usage)
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


class InvoiceUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = ("payment_status",)

    payment_status = serializers.ChoiceField(
        choices=[INVOICE_STATUS.PAID, INVOICE_STATUS.UNPAID], required=True
    )

    def validate(self, data):
        data = super().validate(data)
        if self.instance.external_payment_obj_id is not None:
            raise serializers.ValidationError(
                f"Can't manually update connected invoices. This invoice is connected to {self.instance.external_payment_obj_type}"
            )
        return data

    def update(self, instance, validated_data):
        instance.payment_status = validated_data.get(
            "payment_status", instance.payment_status
        )
        instance.save()
        return instance


## INVOICE
class InvoiceLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLineItem
        fields = (
            "name",
            "start_date",
            "end_date",
            "quantity",
            "subtotal",
            "billing_type",
            "invoice_id",
            "plan_version_id",
        )

    invoice_id = serializers.CharField(source="invoice.invoice_id", read_only=True)
    plan_version_id = serializers.CharField(
        source="associated_plan_version.plan_version_id", read_only=True
    )


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
            "external_payment_obj_type",
            "line_items",
            "customer",
            "subscription",
        )

    cost_due = serializers.DecimalField(
        max_digits=10, decimal_places=2, source="cost_due.amount"
    )
    cost_due_currency = serializers.CharField(source="cost_due.currency")
    customer = CustomerSerializer(read_only=True)
    subscription = SubscriptionSerializer(read_only=True)
    line_items = InvoiceLineItemSerializer(
        many=True, read_only=True, source="inv_line_items"
    )


class CustomerBalanceAdjustmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerBalanceAdjustment
        fields = (
            "customer",
            "amount",
            "amount_currency",
            "description",
            "created",
            "effective_at",
            "expires_at",
        )


class DraftInvoiceSerializer(InvoiceSerializer):
    class Meta(InvoiceSerializer.Meta):
        model = Invoice
        fields = (
            "cost_due",
            "cost_due_currency",
            "cust_connected_to_payment_provider",
            "org_connected_to_cust_payment_provider",
            "line_items",
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
            "balance_adjustments",
            "invoices",
            "total_amount_due",
            "subscriptions",
        )

    subscriptions = SubscriptionCustomerDetailSerializer(read_only=True, many=True)
    invoices = serializers.SerializerMethodField()
    balance_adjustments = serializers.SerializerMethodField()
    total_amount_due = serializers.SerializerMethodField()

    def get_invoices(self, obj) -> InvoiceSerializer(many=True):
        timeline = self.context.get("invoices")
        timeline = InvoiceSerializer(timeline, many=True).data
        return timeline

    def get_balance_adjustments(
        self, obj
    ) -> CustomerBalanceAdjustmentSerializer(many=True):
        timeline = self.context.get("balance_adjustments")
        timeline = CustomerBalanceAdjustmentSerializer(timeline, many=True).data
        return timeline

    def get_total_amount_due(self, obj) -> float:
        total_amount_due = float(self.context.get("total_amount_due"))
        return total_amount_due
