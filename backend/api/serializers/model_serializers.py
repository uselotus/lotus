from typing import Union

from django.conf import settings
from django.db.models import Q
from metering_billing.billable_metrics import METRIC_HANDLER_MAP
from metering_billing.exceptions import ServerError
from metering_billing.models import *
from metering_billing.payment_providers import PAYMENT_PROVIDER_MAP
from metering_billing.serializers.serializer_utils import (
    SlugRelatedFieldWithOrganization,
    SlugRelatedFieldWithOrganizationOrNull,
)
from metering_billing.utils.enums import *
from rest_framework import serializers

SVIX_CONNECTOR = settings.SVIX_CONNECTOR


class PricingUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = PricingUnit
        fields = ("code", "name", "symbol")


class SubscriptionCustomerSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionRecord
        fields = ("billing_plan_name", "plan_version", "end_date", "auto_renew")

    billing_plan_name = serializers.CharField(source="billing_plan.plan.plan_name")
    plan_version = serializers.CharField(source="billing_plan.version")


class SubscriptionCustomerDetailSerializer(SubscriptionCustomerSummarySerializer):
    class Meta(SubscriptionCustomerSummarySerializer.Meta):
        model = SubscriptionRecord
        fields = SubscriptionCustomerSummarySerializer.Meta.fields + ("start_date",)


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
            "integrations",
            "default_currency_code",
        )
        extra_kwargs = {
            "customer_id": {"required": True},
            "email": {"required": True},
        }

    payment_provider = serializers.ChoiceField(
        choices=PAYMENT_PROVIDERS.choices,
        required=False,
    )
    payment_provider_id = serializers.CharField(
        required=False,
        allow_null=True,
        write_only=True,
        help_text="The customer ID in the payment provider",
    )
    email = serializers.EmailField(
        required=True,
        help_text="The primary email address of the customer, must be the same as the email address used to create the customer in the payment provider",
    )
    default_currency_code = SlugRelatedFieldWithOrganizationOrNull(
        slug_field="code",
        queryset=PricingUnit.objects.all(),
        required=False,
        source="default_currency",
        write_only=True,
        help_text="The currency code this customer will be invoiced in. Codes are 3 letters, e.g. 'USD'.",
    )

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


class CategoricalFilterSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoricalFilter
        fields = ("property_name", "operator", "comparison_value")

    comparison_value = serializers.ListField(child=serializers.CharField())


class SubscriptionCategoricalFilterSerializer(CategoricalFilterSerializer):
    class Meta(CategoricalFilterSerializer.Meta):
        model = CategoricalFilter
        fields = ("value", "property_name")

    value = serializers.CharField()
    property_name = serializers.CharField(
        help_text="The string name of the property to filter on. Example: 'product_id'"
    )

    def create(self, validated_data):
        comparison_value = validated_data.pop("value")
        comparison_value = [comparison_value]
        validated_data["comparison_value"] = comparison_value
        return CategoricalFilter.objects.create(
            **validated_data, operator=CATEGORICAL_FILTER_OPERATORS.ISIN
        )

    def to_representation(self, instance):
        data = {
            "property_name": instance.property_name,
            "value": instance.comparison_value[0],
        }
        return data


class NumericFilterSerializer(serializers.ModelSerializer):
    class Meta:
        model = NumericFilter
        fields = ("property_name", "operator", "comparison_value")


class MetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = Metric
        fields = (
            "metric_id",
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
            "is_cost_metric",
        )
        extra_kwargs = {
            "metric_type": {"required": True},
            "usage_aggregation_type": {"required": True},
            "event_name": {"required": True},
            "metric_id": {"read_only": True},
            "billable_metric_name": {"required": True},
        }

    numeric_filters = NumericFilterSerializer(
        many=True, allow_null=True, required=False, read_only=False
    )
    categorical_filters = CategoricalFilterSerializer(
        many=True, allow_null=True, required=False, read_only=False
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

    def create(self, validated_data):
        # edit custom name and pop filters + properties
        num_filter_data = validated_data.pop("numeric_filters", [])
        cat_filter_data = validated_data.pop("categorical_filters", [])

        bm = Metric.objects.create(**validated_data)

        # get filters
        for num_filter in num_filter_data:
            try:
                nf, _ = NumericFilter.objects.get_or_create(
                    **num_filter, organization=bm.organization
                )
            except NumericFilter.MultipleObjectsReturned:
                nf = NumericFilter.objects.filter(
                    **num_filter, organization=bm.organization
                ).first()
            bm.numeric_filters.add(nf)
        for cat_filter in cat_filter_data:
            try:
                cf, _ = CategoricalFilter.objects.get_or_create(
                    **cat_filter, organization=bm.organization
                )
            except CategoricalFilter.MultipleObjectsReturned:
                cf = CategoricalFilter.objects.filter(
                    **cat_filter, organization=bm.organization
                ).first()
            bm.categorical_filters.add(cf)
        bm.save()

        return bm


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


class PlanComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanComponent
        fields = (
            "billable_metric",
            "tiers",
            "separate_by",
            "proration_granularity",
            "pricing_unit",
        )
        read_only_fields = ["billable_metric", "pricing_unit"]

    separate_by = serializers.ListField(child=serializers.CharField(), required=False)
    proration_granularity = serializers.ChoiceField(
        choices=METRIC_GRANULARITY.choices,
        required=False,
        default=METRIC_GRANULARITY.TOTAL,
    )

    # READ-ONLY
    billable_metric = MetricSerializer(read_only=True)
    pricing_unit = PricingUnitSerializer(read_only=True)

    tiers = PriceTierSerializer(many=True)


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
            "day_anchor",
            "month_anchor",
            # read-only
            "version",
            "version_id",
            "active_subscriptions",
            "created_by",
            "created_on",
            "status",
            "replace_with",
            "transition_to",
            "plan_name",
            "currency",
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
            "plan_name",
            "currency",
        )

    components = PlanComponentSerializer(
        many=True, allow_null=True, required=False, source="plan_components"
    )
    features = FeatureSerializer(many=True, allow_null=True, required=False)
    price_adjustment = PriceAdjustmentSerializer(required=False)
    plan_id = SlugRelatedFieldWithOrganization(
        slug_field="plan_id",
        queryset=Plan.objects.all(),
        source="plan",
        required=False,
    )

    # READ-ONLY
    active_subscriptions = serializers.IntegerField(read_only=True)
    created_by = serializers.SerializerMethodField(read_only=True)
    replace_with = serializers.SerializerMethodField(read_only=True)
    transition_to = serializers.SerializerMethodField(read_only=True)
    plan_name = serializers.CharField(read_only=True, source="plan.plan_name")
    currency = PricingUnitSerializer(read_only=True, source="pricing_unit")

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


class PlanNameAndIDSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = (
            "plan_name",
            "plan_id",
        )


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


class ShortCustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = (
            "customer_name",
            "email",
            "customer_id",
        )


class InitialExternalPlanLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExternalPlanLink
        fields = ("source", "external_plan_id")


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = (
            "plan_name",
            "plan_duration",
            "product_id",
            "plan_id",
            "status",
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

    # READ ONLY
    parent_plan = PlanNameAndIDSerializer(read_only=True, required=False)
    target_customer = ShortCustomerSerializer(read_only=True, required=False)
    created_by = serializers.SerializerMethodField(read_only=True)
    display_version = PlanVersionSerializer(read_only=True)
    num_versions = serializers.SerializerMethodField(read_only=True)
    active_subscriptions = serializers.SerializerMethodField(read_only=True)
    external_links = InitialExternalPlanLinkSerializer(many=True, read_only=True)

    def get_created_by(self, obj) -> str:
        if obj.created_by:
            return obj.created_by.username
        else:
            return None

    def get_num_versions(self, obj) -> int:
        return len(obj.version_numbers())

    def get_active_subscriptions(self, obj) -> int:
        return sum(x.active_subscriptions for x in obj.active_subs_by_version())


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
        return PlanVersionSerializer(
            obj.versions.all().order_by("version"), many=True
        ).data


class SubscriptionRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionRecord
        fields = (
            "start_date",
            "end_date",
            "auto_renew",
            "is_new",
            "subscription_filters",
            "customer_id",
            "plan_id",
            "customer",
            "billing_plan",
        )

    start_date = serializers.DateTimeField(
        help_text="The date the subscription starts. This should be a string in YYYY-MM-DD format of the date in UTC time."
    )
    end_date = serializers.DateTimeField(
        required=False,
        help_text="The date the subscription ends. This should be a string in YYYY-MM-DD format of the date in UTC time. If you don’t set it (recommended), we will use the information in the billing plan to automatically calculate this.",
    )
    auto_renew = serializers.BooleanField(
        required=False,
        help_text="Should the subscription automatically renew? defaults to true",
    )
    is_new = serializers.BooleanField(required=False)
    subscription_filters = SubscriptionCategoricalFilterSerializer(
        many=True,
        required=False,
        help_text="Add filter key, value pairs that define which events will be applied to this plan subscription",
    )

    # WRITE ONLY
    customer_id = SlugRelatedFieldWithOrganization(
        slug_field="customer_id",
        read_only=False,
        source="customer",
        queryset=Customer.objects.all(),
        write_only=True,
        help_text="The id provided when creating the customer",
    )
    plan_id = SlugRelatedFieldWithOrganization(
        slug_field="plan_id",
        read_only=False,
        source="billing_plan.plan",
        queryset=Plan.objects.all(),
        write_only=True,
        help_text="The Lotus plan_id, found in the billing plan object",
    )
    # READ-ONLY
    customer = ShortCustomerSerializer(read_only=True)
    billing_plan = PlanNameAndIDSerializer(read_only=True, source="billing_plan.plan")

    def validate(self, data):
        # extract the plan version from the plan
        data["billing_plan"] = data["billing_plan"]["plan"].display_version
        # check that if the plan is designed for a specific customer, that the customer is that customer
        tc = data["billing_plan"].plan.target_customer
        if tc is not None and tc != data["customer"]:
            raise serializers.ValidationError(
                f"This plan is for a customer with customer_id {tc.customer_id}, not {data['customer'].customer_id}"
            )
        return data

    def create(self, validated_data):
        # try:
        filters = validated_data.pop("subscription_filters", [])
        now = now_utc()
        sub_record = super().create(validated_data)
        for filter_data in filters:
            sub_cat_filter_dict = {
                "property_name": filter_data["property_name"],
                "operator": CATEGORICAL_FILTER_OPERATORS.ISIN,
                "comparison_value": [filter_data["value"]],
            }
            try:
                cf, _ = CategoricalFilter.objects.get_or_create(**sub_cat_filter_dict)
            except CategoricalFilter.MultipleObjectsReturned:
                cf = CategoricalFilter.objects.filter(**sub_cat_filter_dict).first()
            sub_record.filters.add(cf)
        sub_record.save()
        # new subscription means we need to create an invoice if its pay in advance
        if (
            sub_record.billing_plan.flat_fee_billing_type
            == FLAT_FEE_BILLING_TYPE.IN_ADVANCE
        ):
            (
                sub,
                sub_records,
            ) = sub_record.customer.get_subscription_and_records()
            sub_records.filter(pk=sub_record.pk).update(
                flat_fee_behavior=FLAT_FEE_BEHAVIOR.CHARGE_FULL,
                invoice_usage_charges=False,
            )
            generate_invoice(
                sub,
                sub_records.filter(pk=sub_record.pk),
            )
            sub_record.invoice_usage_charges = True
            sub_record.flat_fee_behavior = FLAT_FEE_BEHAVIOR.PRORATE
            sub_record.save()
        return sub_record


class SubscriptionRecordDetailSerializer(SubscriptionRecordSerializer):
    class Meta(SubscriptionRecordSerializer.Meta):
        model = SubscriptionRecord
        fields = tuple(
            set(SubscriptionRecordSerializer.Meta.fields).union(set(["plan_detail"]))
        )

    plan_detail = PlanVersionSerializer(source="billing_plan", read_only=True)
    subscription_filters = SubscriptionCategoricalFilterSerializer(
        source="filters", many=True, read_only=True
    )


class LightweightPlanVersionSerializer(PlanVersionSerializer):
    class Meta(PlanVersionSerializer.Meta):
        model = PlanVersion
        fields = ("plan_id", "plan_name", "version_id")

    plan_name = serializers.CharField(read_only=True, source="plan.plan_name")
    plan_id = serializers.CharField(read_only=True, source="plan.plan_id")


class LightweightSubscriptionRecordSerializer(SubscriptionRecordSerializer):
    class Meta(SubscriptionRecordSerializer.Meta):
        model = SubscriptionRecord
        fields = tuple(
            set(SubscriptionRecordSerializer.Meta.fields).union(set(["plan_detail"]))
        )

    plan_detail = LightweightPlanVersionSerializer(
        source="billing_plan", read_only=True
    )
    subscription_filters = SubscriptionCategoricalFilterSerializer(
        source="filters", many=True, read_only=True
    )


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = (
            "subscription_id",
            "day_anchor",
            "month_anchor",
            "customer",
            "billing_cadence",
            "start_date",
            "end_date",
            "plans",
        )

    customer = ShortCustomerSerializer(read_only=True)
    plans = serializers.SerializerMethodField()

    def get_plans(self, obj) -> LightweightSubscriptionRecordSerializer(many=True):
        sub_records = obj.get_subscription_records().prefetch_related(
            "billing_plan",
            "filters",
            "billing_plan__plan",
            "billing_plan__pricing_unit",
        )

        data = LightweightSubscriptionRecordSerializer(sub_records, many=True).data
        return data


class SubscriptionInvoiceSerializer(SubscriptionRecordSerializer):
    class Meta(SubscriptionRecordSerializer.Meta):
        model = SubscriptionRecord
        fields = fields = tuple(
            set(SubscriptionRecordSerializer.Meta.fields)
            - set(
                [
                    "customer_id",
                    "plan_id",
                    "billing_plan",
                    "auto_renew",
                ]
            )
        )


class SubscriptionRecordUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionRecord
        fields = (
            "replace_plan_id",
            "replace_plan_invoicing_behavior",
            "replace_plan_usage_behavior",
            "turn_off_auto_renew",
            "end_date",
        )

    replace_plan_id = SlugRelatedFieldWithOrganization(
        slug_field="plan_id",
        read_only=False,
        source="billing_plan.plan",
        queryset=Plan.objects.all(),
        write_only=True,
        required=False,
        help_text="The plan to replace the current plan with",
    )
    replace_plan_invoicing_behavior = serializers.ChoiceField(
        choices=INVOICING_BEHAVIOR.choices,
        default=INVOICING_BEHAVIOR.INVOICE_NOW,
        required=False,
        help_text="The invoicing behavior to use when replacing the plan. Invoice now will invoice the customer for the prorated difference of the old plan and the new plan, whereas add_to_next_invoice will wait until the end of the subscription to do teh calculation.",
    )
    replace_plan_usage_behavior = serializers.ChoiceField(
        choices=USAGE_BEHAVIOR.choices,
        default=USAGE_BEHAVIOR.TRANSFER_TO_NEW_SUBSCRIPTION,
        help_text="The usage behavior to use when replacing the plan. Transfer to new subscription will transfer the usage from the old subscription to the new subscription, whereas reset_usage will reset the usage to 0 for the new subscription, while keeping the old usage on the old subscription and charging for that appropriately at the end of the month.",
    )
    turn_off_auto_renew = serializers.BooleanField(
        required=False, help_text="Turn off auto renew for the subscription"
    )
    end_date = serializers.DateTimeField(
        required=False, help_text="Change the end date for the subscription."
    )

    def validate(self, data):
        data = super().validate(data)
        # extract the plan version from the plan
        if data.get("billing_plan"):
            data["billing_plan"] = data["billing_plan"]["plan"].display_version
        return data


class SubscriptionRecordFilterSerializer(serializers.Serializer):
    customer_id = serializers.CharField(required=True)
    plan_id = serializers.CharField(required=True)
    subscription_filters = serializers.ListField(
        child=SubscriptionCategoricalFilterSerializer(), required=False
    )

    def validate(self, data):
        data = super().validate(data)
        # check that the customer ID matches an existing customer
        try:
            data["customer"] = Customer.objects.get(customer_id=data["customer_id"])
        except Customer.DoesNotExist:
            raise serializers.ValidationError(
                f"Customer with customer_id {data['customer_id']} does not exist"
            )
        # check that the plan ID matches an existing plan
        if data.get("plan_id"):
            try:
                data["plan"] = Plan.objects.get(plan_id=data["plan_id"])
            except Plan.DoesNotExist:
                raise serializers.ValidationError(
                    f"Plan with plan_id {data['plan_id']} does not exist"
                )
        return data


class SubscriptionRecordFilterSerializerDelete(SubscriptionRecordFilterSerializer):
    plan_id = serializers.CharField(required=False)


class SubscriptionRecordCancelSerializer(serializers.Serializer):
    flat_fee_behavior = serializers.ChoiceField(
        choices=FLAT_FEE_BEHAVIOR.choices,
        default=FLAT_FEE_BEHAVIOR.CHARGE_FULL,
        help_text="Can either charge the full amount of the flat fee, regardless of how long teh custoemr has been on the plan, prorate the fflat fee, or charge nothing for the flat fee. If the flat fee has already been invoiced (e.g. in advance payment on last subscription), and the reuslting charge is less than the amount already invoiced, the difference will be refunded as a credit. Defaults to charge full amount.",
    )
    usage_behavior = serializers.ChoiceField(
        choices=USAGE_BILLING_BEHAVIOR.choices,
        default=USAGE_BILLING_BEHAVIOR.BILL_FULL,
        help_text="If bill_full, current usage will be billed on the invoice. If bill_none, current unbilled usage will be dropped from the invoice. Defaults to bill_full.",
    )
    invoicing_behavior = serializers.ChoiceField(
        choices=INVOICING_BEHAVIOR.choices,
        default=INVOICING_BEHAVIOR.INVOICE_NOW,
        help_text="Whether to invoice now or invoice at the end of the billing period. Defaults to invoice now.",
    )


class ListSubscriptionRecordFilter(serializers.Serializer):
    customer_id = serializers.CharField(required=False)
    status = serializers.ChoiceField(
        choices=SUBSCRIPTION_STATUS.choices, required=False
    )
    status = serializers.MultipleChoiceField(
        choices=SUBSCRIPTION_STATUS.choices,
        required=False,
        default=[SUBSCRIPTION_STATUS.ACTIVE],
    )
    range_start = serializers.DateTimeField(required=False)
    range_end = serializers.DateTimeField(required=False)

    def validate(self, data):
        # check that the customer ID matches an existing customer
        data = super().validate(data)
        if data.get("customer_id"):
            try:
                data["customer"] = Customer.objects.get(customer_id=data["customer_id"])
            except Customer.DoesNotExist:
                raise serializers.ValidationError(
                    f"Customer with customer_id {data['customer_id']} does not exist"
                )
        return data


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
            "metadata",
            "plan_version_id",
            "plan_name",
            "subscription_filters",
        )

    plan_version_id = serializers.CharField(
        source="associated_subscription_record.billing_plan.plan_version_id",
        read_only=True,
    )
    plan_name = serializers.CharField(
        source="associated_subscription_record.billing_plan.plan.plan_name",
        read_only=True,
    )
    subscription_filters = SubscriptionCategoricalFilterSerializer(
        source="associated_subscription_record.filters", many=True, read_only=True
    )


class LightweightInvoiceLineItemSerializer(InvoiceLineItemSerializer):
    class Meta(InvoiceLineItemSerializer.Meta):
        fields = tuple(
            set(InvoiceLineItemSerializer.Meta.fields)
            - set(
                [
                    "plan_version_id",
                    "plan_name",
                    "subscription_filters",
                ]
            )
        )


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = (
            "invoice_number",
            "cost_due",
            "currency",
            "issue_date",
            "payment_status",
            "cust_connected_to_payment_provider",
            "org_connected_to_cust_payment_provider",
            "external_payment_obj_id",
            "external_payment_obj_type",
            "line_items",
            "customer",
            "subscription",
            "due_date",
        )

    cost_due = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    currency = PricingUnitSerializer(read_only=True)
    customer = CustomerSerializer(read_only=True)
    subscription = SubscriptionRecordDetailSerializer(read_only=True)
    line_items = InvoiceLineItemSerializer(many=True, read_only=True)
    external_payment_obj_type = serializers.ChoiceField(
        choices=PAYMENT_PROVIDERS.choices, read_only=True, required=False
    )


class LightweightInvoiceSerializer(InvoiceSerializer):
    class Meta(InvoiceSerializer.Meta):
        fields = tuple(
            set(InvoiceSerializer.Meta.fields)
            - set(
                [
                    "line_items",
                    "customer",
                    "subscription",
                    "cust_connected_to_payment_provider",
                    "org_connected_to_cust_payment_provider",
                ]
            )
        )


class InvoiceListFilterSerializer(serializers.Serializer):
    customer_id = serializers.CharField(required=False)
    payment_status = serializers.MultipleChoiceField(
        choices=[INVOICE_STATUS.UNPAID, INVOICE_STATUS.PAID],
        required=False,
        default=[INVOICE_STATUS.UNPAID, INVOICE_STATUS.PAID],
    )


class GroupedLineItemSerializer(serializers.Serializer):
    plan_name = serializers.CharField()
    subscription_filters = SubscriptionCategoricalFilterSerializer(many=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)
    start_date = serializers.DateTimeField()
    end_date = serializers.DateTimeField()
    sub_items = LightweightInvoiceLineItemSerializer(many=True)


class CustomerBalanceAdjustmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerBalanceAdjustment
        fields = (
            "adjustment_id",
            "customer_id",
            "amount",
            "pricing_unit_code",
            "pricing_unit",
            "description",
            "effective_at",
            "expires_at",
            "status",
            "parent_adjustment_id",
        )

    customer_id = SlugRelatedFieldWithOrganization(
        slug_field="customer_id",
        queryset=Customer.objects.all(),
        required=True,
        source="customer",
    )
    pricing_unit_code = SlugRelatedFieldWithOrganizationOrNull(
        slug_field="code",
        queryset=PricingUnit.objects.all(),
        required=True,
        source="pricing_unit",
        write_only=True,
    )
    pricing_unit = PricingUnitSerializer(read_only=True)
    parent_adjustment_id = SlugRelatedFieldWithOrganization(
        slug_field="adjustment_id",
        required=False,
        source="parent_adjustment",
        read_only=True,
    )

    def validate(self, data):
        data = super().validate(data)
        amount = data.get("amount", 0)
        customer = data["customer"]
        if amount <= 0:
            raise serializers.ValidationError("Amount must be non-zero")
        return data


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
            "integrations",
            "default_currency",
        )

    subscriptions = serializers.SerializerMethodField()
    invoices = serializers.SerializerMethodField()
    total_amount_due = serializers.SerializerMethodField()
    default_currency = PricingUnitSerializer()

    def get_subscriptions(self, obj) -> SubscriptionRecordSerializer(many=True):
        sr_objs = obj.subscription_records.filter(
            organization=self.context.get("organization"),
            status=SUBSCRIPTION_STATUS.ACTIVE,
            start_date__lte=now_utc(),
            end_date__gte=now_utc(),
        )
        return SubscriptionRecordSerializer(sr_objs, many=True).data

    def get_invoices(self, obj) -> LightweightInvoiceSerializer(many=True):
        timeline = (
            obj.invoices.filter(
                ~Q(payment_status=INVOICE_STATUS.DRAFT),
                organization=self.context.get("organization"),
            )
            .order_by("-issue_date")
            .prefetch_related("currency", "line_items", "subscription")
        )
        timeline = LightweightInvoiceSerializer(timeline, many=True).data
        return timeline

    def get_total_amount_due(self, obj) -> float:
        total_amount_due = float(obj.get_outstanding_revenue())
        return total_amount_due
