import datetime
import re
from typing import Literal, Optional, Union

from django.conf import settings
from django.db.models import Q, Sum
from metering_billing.invoice import generate_balance_adjustment_invoice
from metering_billing.models import (
    CategoricalFilter,
    Customer,
    CustomerBalanceAdjustment,
    Event,
    ExternalPlanLink,
    Feature,
    Invoice,
    InvoiceLineItem,
    Metric,
    NumericFilter,
    Organization,
    Plan,
    PlanComponent,
    PlanVersion,
    PriceAdjustment,
    PriceTier,
    PricingUnit,
    Subscription,
    SubscriptionRecord,
    Tag,
    UsageAlert,
)
from metering_billing.payment_providers import PAYMENT_PROVIDER_MAP
from metering_billing.serializers.serializer_utils import (
    BalanceAdjustmentUUIDField,
    InvoiceUUIDField,
    MetricUUIDField,
    PlanUUIDField,
    PlanVersionUUIDField,
    SlugRelatedFieldWithOrganization,
    SubscriptionUUIDField,
    UsageAlertUUIDField,
)
from metering_billing.utils import convert_to_date, now_utc
from metering_billing.utils.enums import (
    BATCH_ROUNDING_TYPE,
    CATEGORICAL_FILTER_OPERATORS,
    CUSTOMER_BALANCE_ADJUSTMENT_STATUS,
    FLAT_FEE_BEHAVIOR,
    FLAT_FEE_BILLING_TYPE,
    INVOICE_STATUS_ENUM,
    INVOICING_BEHAVIOR,
    PAYMENT_PROVIDERS,
    PRICE_TIER_TYPE,
    SUBSCRIPTION_STATUS,
    USAGE_BEHAVIOR,
    USAGE_BILLING_BEHAVIOR,
)
from rest_framework import serializers

SVIX_CONNECTOR = settings.SVIX_CONNECTOR


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("tag_name", "tag_hex", "tag_color")

    def validate(self, data):
        match = re.search(r"^#(?:[0-9a-fA-F]{3}){1,2}$", data["tag_hex"])
        if not match:
            raise serializers.ValidationError("Invalid hex code")
        return data


class ConvertEmptyStringToSerializerMixin:
    def recursive_convert_empty_string_to_none(self, data: dict):
        for key, value in data.items():
            if isinstance(value, dict):
                self.recursive_convert_empty_string_to_none(value)
            elif value == "":
                data[key] = None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        self.recursive_convert_empty_string_to_none(data)
        return data


class PricingUnitSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = PricingUnit
        fields = ("code", "name", "symbol")


class LightweightCustomerSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = Customer
        fields = (
            "customer_name",
            "email",
            "customer_id",
        )
        extra_kwargs = {
            "customer_id": {"required": True, "read_only": True},
            "customer_name": {"required": True, "read_only": True},
            "email": {"required": True, "read_only": True},
        }


class AddressSerializer(serializers.Serializer):
    city = serializers.CharField(
        required=True, help_text="City, district, suburb, town, or village"
    )
    country = serializers.CharField(
        min_length=2,
        max_length=2,
        required=True,
        help_text="ISO 3166-1 alpha-2 country code",
    )
    line1 = serializers.CharField(
        required=True,
        help_text="Address line 1 (e.g., street, PO Box, or company name)",
    )
    line2 = serializers.CharField(
        allow_blank=True,
        allow_null=True,
        required=False,
        help_text="Address line 2 (e.g., apartment, suite, unit, or building)",
    )
    postal_code = serializers.CharField(required=True, help_text="ZIP or postal code")
    state = serializers.CharField(
        required=True, help_text="State, county, province, or region"
    )


class LightweightCustomerSerializerForInvoice(LightweightCustomerSerializer):
    class Meta(LightweightCustomerSerializer.Meta):
        fields = LightweightCustomerSerializer.Meta.fields + ("address",)
        extra_kwargs = {
            **LightweightCustomerSerializer.Meta.extra_kwargs,
            "address": {"required": False, "allow_null": True},
        }

    address = serializers.SerializerMethodField(required=False, allow_null=True)

    def get_address(self, obj) -> AddressSerializer(allow_null=True, required=False):
        d = obj.properties.get("address", {})
        try:
            data = AddressSerializer(d).data
        except KeyError:
            data = None
        return data


class LightweightPlanVersionSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = PlanVersion
        fields = (
            "plan_name",
            "plan_id",
            "version",
        )
        extra_kwargs = {
            "plan_id": {"required": True, "read_only": True},
            "plan_name": {"required": True, "read_only": True},
            "version": {"required": True, "read_only": True},
        }

    plan_name = serializers.CharField(source="plan.plan_name")
    plan_id = PlanUUIDField(source="plan.plan_id")


class CategoricalFilterSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = CategoricalFilter
        fields = ("property_name", "operator", "comparison_value")

    comparison_value = serializers.ListField(child=serializers.CharField())


class SubscriptionCategoricalFilterSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = CategoricalFilter
        fields = ("value", "property_name")
        extra_kwargs = {
            "property_name": {
                "required": True,
            },
            "value": {"required": True},
        }

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


class SubscriptionCustomerSummarySerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = SubscriptionRecord
        fields = ("billing_plan_name", "plan_version", "end_date", "auto_renew")

    billing_plan_name = serializers.CharField(source="billing_plan.plan.plan_name")
    plan_version = serializers.CharField(source="billing_plan.version")


class SubscriptionCustomerDetailSerializer(SubscriptionCustomerSummarySerializer):
    class Meta(SubscriptionCustomerSummarySerializer.Meta):
        model = SubscriptionRecord
        fields = SubscriptionCustomerSummarySerializer.Meta.fields + ("start_date",)


class SubscriptionRecordSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = SubscriptionRecord
        fields = (
            "start_date",
            "end_date",
            "auto_renew",
            "is_new",
            "subscription_filters",
            "customer",
            "billing_plan",
            "fully_billed",
        )
        extra_kwargs = {
            "start_date": {"required": True},
            "end_date": {"required": True},
            "auto_renew": {"required": True},
            "is_new": {"required": True},
            "subscription_filters": {"required": True},
            "customer": {"required": True},
            "fully_billed": {"required": True},
        }

    subscription_filters = SubscriptionCategoricalFilterSerializer(
        many=True, source="filters"
    )
    customer = LightweightCustomerSerializer()
    billing_plan = LightweightPlanVersionSerializer()


class InvoiceLineItemSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
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
            "plan",
            "subscription_filters",
        )
        extra_kwargs = {
            "name": {"required": True},
            "start_date": {"required": True},
            "end_date": {"required": True},
            "quantity": {"required": True},
            "subtotal": {"required": True},
            "billing_type": {"required": True, "allow_blank": False},
            "metadata": {"required": True},
            "plan": {"required": True, "allow_null": True},
            "subscription_filters": {"required": True, "allow_null": True},
        }

    plan = serializers.SerializerMethodField(allow_null=True)
    subscription_filters = serializers.SerializerMethodField(allow_null=True)

    def get_subscription_filters(
        self, obj
    ) -> SubscriptionCategoricalFilterSerializer(many=True, allow_null=True):
        ass_sub_record = obj.associated_subscription_record
        if ass_sub_record:
            return SubscriptionCategoricalFilterSerializer(
                ass_sub_record.filters.all(), many=True
            ).data
        return None

    def get_plan(self, obj) -> LightweightPlanVersionSerializer(allow_null=True):
        ass_sub_record = obj.associated_subscription_record
        if ass_sub_record:
            return LightweightPlanVersionSerializer(ass_sub_record.billing_plan).data
        return None


class LightweightInvoiceLineItemSerializer(InvoiceLineItemSerializer):
    class Meta(InvoiceLineItemSerializer.Meta):
        fields = tuple(set(InvoiceLineItemSerializer.Meta.fields) - {"metadata"})
        extra_kwargs = {**InvoiceLineItemSerializer.Meta.extra_kwargs}


class SellerSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = Organization
        fields = ("name", "address", "phone", "email")

    name = serializers.CharField(source="organization_name")
    address = serializers.SerializerMethodField(required=False, allow_null=True)

    def get_address(self, obj) -> AddressSerializer(allow_null=True, required=False):
        d = obj.properties.get("address", {})
        try:
            data = AddressSerializer(d).data
        except KeyError:
            data = None
        return data


class InvoiceSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = Invoice
        fields = (
            "invoice_id",
            "invoice_number",
            "cost_due",
            "currency",
            "issue_date",
            "payment_status",
            "external_payment_obj_id",
            "external_payment_obj_type",
            "line_items",
            "customer",
            "due_date",
            "start_date",
            "end_date",
            "seller",
            "invoice_pdf",
        )
        extra_kwargs = {
            "invoice_id": {"required": True, "read_only": True},
            "invoice_number": {"required": True, "read_only": True},
            "cost_due": {"required": True, "read_only": True},
            "issue_date": {"required": True, "read_only": True},
            "payment_status": {"required": True, "read_only": True},
            "due_date": {"required": True, "allow_null": True, "read_only": True},
            "external_payment_obj_id": {
                "required": True,
                "allow_null": True,
                "allow_blank": False,
                "read_only": True,
            },
            "external_payment_obj_type": {
                "required": True,
                "allow_null": True,
                "allow_blank": False,
                "read_only": True,
            },
            "start_date": {"required": True, "read_only": True},
            "end_date": {"required": True, "read_only": True},
            "seller": {"required": True, "read_only": True},
            "invoice_pdf": {"required": True, "allow_null": True, "read_only": True},
        }

    invoice_id = InvoiceUUIDField()
    external_payment_obj_type = serializers.ChoiceField(
        choices=PAYMENT_PROVIDERS.choices,
        allow_null=True,
        required=True,
        allow_blank=False,
    )
    currency = PricingUnitSerializer()
    customer = LightweightCustomerSerializerForInvoice()
    line_items = InvoiceLineItemSerializer(many=True)
    start_date = serializers.SerializerMethodField()
    end_date = serializers.SerializerMethodField()
    seller = SellerSerializer(source="organization")
    payment_status = serializers.SerializerMethodField()

    def get_payment_status(
        self, obj
    ) -> Literal[INVOICE_STATUS_ENUM.PAID, INVOICE_STATUS_ENUM.UNPAID,]:
        ps = obj.payment_status
        if ps == Invoice.PaymentStatus.PAID:
            return INVOICE_STATUS_ENUM.PAID
        elif ps == Invoice.PaymentStatus.UNPAID:
            return INVOICE_STATUS_ENUM.UNPAID
        elif ps == Invoice.PaymentStatus.VOIDED:
            return INVOICE_STATUS_ENUM.VOIDED
        elif ps == Invoice.PaymentStatus.DRAFT:
            return INVOICE_STATUS_ENUM.DRAFT

    def get_start_date(self, obj) -> datetime.date:
        seq = [
            convert_to_date(x.start_date) for x in obj.line_items.all() if x.start_date
        ]
        return min(seq) if len(seq) > 0 else None

    def get_end_date(self, obj) -> datetime.date:
        seq = [convert_to_date(x.end_date) for x in obj.line_items.all() if x.end_date]
        return max(seq) if len(seq) > 0 else None


class LightweightInvoiceSerializer(InvoiceSerializer):
    class Meta(InvoiceSerializer.Meta):
        fields = tuple(
            set(InvoiceSerializer.Meta.fields)
            - set(
                [
                    "line_items",
                    "customer",
                    "invoice_pdf",
                ]
            )
        )
        extra_kwargs = {**InvoiceSerializer.Meta.extra_kwargs}


class CustomerStripeIntegrationSerializer(serializers.Serializer):
    stripe_id = serializers.CharField()
    has_payment_method = serializers.BooleanField()


class CustomerIntegrationsSerializer(serializers.Serializer):
    stripe = CustomerStripeIntegrationSerializer(required=False, allow_null=True)


class CustomerSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
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
            "payment_provider",
            "has_payment_method",
            "address",
            "tax_rate",
        )
        extra_kwargs = {
            "customer_id": {"required": True, "read_only": True},
            "email": {"required": True, "read_only": True},
            "customer_name": {"required": True, "read_only": True},
            "invoices": {"required": True, "read_only": True},
            "total_amount_due": {"required": True, "read_only": True},
            "subscriptions": {"required": True, "read_only": True},
            "integrations": {"required": True, "read_only": True},
            "default_currency": {"required": True, "read_only": True},
            "payment_provider": {"required": True, "read_only": True},
            "has_payment_method": {"required": True, "read_only": True},
            "address": {"required": True, "read_only": True},
            "tax_rate": {"required": True, "read_only": True},
        }

    customer_id = serializers.CharField()
    email = serializers.EmailField()
    customer_name = serializers.CharField()
    subscriptions = serializers.SerializerMethodField()
    invoices = serializers.SerializerMethodField()
    total_amount_due = serializers.SerializerMethodField()
    default_currency = PricingUnitSerializer()
    integrations = serializers.SerializerMethodField(
        help_text="A dictionary containing the customer's integrations. Keys are the integration type, and the value is a dictionary containing the integration's properties, which can vary by integration.",
    )
    payment_provider = serializers.ChoiceField(
        choices=PAYMENT_PROVIDERS.choices,
        allow_null=True,
        required=True,
        allow_blank=False,
    )
    has_payment_method = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()

    def get_address(self, obj) -> AddressSerializer(allow_null=True, required=True):
        d = obj.properties.get("address", {})
        try:
            data = AddressSerializer(d).data
        except KeyError:
            data = None
        return data

    def get_has_payment_method(self, obj) -> bool:
        d = self.get_integrations(obj)
        if obj.payment_provider == PAYMENT_PROVIDERS.STRIPE:
            stripe_dict = d.get(PAYMENT_PROVIDERS.STRIPE)
            if stripe_dict:
                return stripe_dict["has_payment_method"]
        return False

    def _format_stripe_integration(
        self, stripe_connections_dict
    ) -> CustomerStripeIntegrationSerializer:
        return {
            "stripe_id": stripe_connections_dict["id"],
            "has_payment_method": len(stripe_connections_dict["payment_methods"]) > 0,
        }

    def get_integrations(self, obj) -> CustomerIntegrationsSerializer:
        d = obj.integrations
        if PAYMENT_PROVIDERS.STRIPE in d:
            try:
                d[PAYMENT_PROVIDERS.STRIPE] = self._format_stripe_integration(
                    d[PAYMENT_PROVIDERS.STRIPE]
                )
            except (KeyError, TypeError):
                d[PAYMENT_PROVIDERS.STRIPE] = None
        else:
            d[PAYMENT_PROVIDERS.STRIPE] = None
        return d

    def get_subscriptions(self, obj) -> SubscriptionRecordSerializer(many=True):
        sr_objs = obj.subscription_records.active().filter(
            organization=self.context.get("organization"),
            start_date__lte=now_utc(),
            end_date__gte=now_utc(),
        )
        return SubscriptionRecordSerializer(sr_objs, many=True).data

    def get_invoices(self, obj) -> LightweightInvoiceSerializer(many=True):
        timeline = (
            obj.invoices.filter(
                ~Q(payment_status=Invoice.PaymentStatus.DRAFT),
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


class CustomerCreateSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = Customer
        fields = (
            "customer_name",
            "customer_id",
            "email",
            "payment_provider",
            "payment_provider_id",
            "properties",
            "default_currency_code",
            "address",
            "tax_rate",
        )
        extra_kwargs = {
            "customer_id": {"required": True},
            "email": {"required": True},
        }

    payment_provider = serializers.ChoiceField(
        choices=PAYMENT_PROVIDERS.choices,
        required=False,
        help_text="The payment provider this customer is associated with. Currently, only Stripe is supported.",
    )
    payment_provider_id = serializers.CharField(
        required=False,
        allow_null=True,
        write_only=True,
        help_text="The customer's ID in the specified payment provider. Please note that payment_provider and payment_provider_id are mutually necessary.",
    )
    email = serializers.EmailField(
        required=True,
        help_text="The primary email address of the customer, must be the same as the email address used to create the customer in the payment provider",
    )
    default_currency_code = SlugRelatedFieldWithOrganization(
        slug_field="code",
        queryset=PricingUnit.objects.all(),
        required=False,
        source="default_currency",
        write_only=True,
        help_text="The currency code this customer will be invoiced in. Codes are 3 letters, e.g. 'USD'.",
    )
    address = AddressSerializer(required=False, allow_null=True)

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
        address = validated_data.pop("address", None)
        if address:
            validated_data["properties"] = {
                **validated_data.get("properties", {}),
                "address": address,
            }
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


class NumericFilterSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = NumericFilter
        fields = ("property_name", "operator", "comparison_value")


class MetricSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = Metric
        fields = (
            "metric_id",
            "event_name",
            "property_name",
            "aggregation_type",
            "granularity",
            "event_type",
            "metric_type",
            "metric_name",
            "numeric_filters",
            "categorical_filters",
            "is_cost_metric",
            "custom_sql",
            "proration",
        )
        extra_kwargs = {
            "metric_id": {"required": True, "read_only": True, "allow_blank": False},
            "event_name": {"required": True, "read_only": True},
            "property_name": {"required": True, "read_only": True},
            "aggregation_type": {
                "required": True,
                "read_only": True,
                "allow_blank": False,
                "allow_null": True,
            },
            "granularity": {
                "required": True,
                "allow_null": True,
                "allow_blank": False,
                "read_only": True,
            },
            "event_type": {
                "required": True,
                "allow_null": True,
                "allow_blank": False,
                "read_only": True,
            },
            "metric_type": {"required": True, "read_only": True},
            "metric_name": {"required": True, "read_only": True},
            "numeric_filters": {"required": True, "read_only": True},
            "categorical_filters": {"required": True, "read_only": True},
            "is_cost_metric": {"required": True, "read_only": True},
            "custom_sql": {"required": True, "read_only": True},
            "proration": {"required": True, "read_only": True},
        }

    metric_id = MetricUUIDField()
    numeric_filters = NumericFilterSerializer(
        many=True,
    )
    categorical_filters = CategoricalFilterSerializer(
        many=True,
    )
    metric_name = serializers.CharField(source="billable_metric_name")
    aggregation_type = serializers.CharField(source="usage_aggregation_type")


class FeatureSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = Feature
        fields = (
            "feature_name",
            "feature_description",
        )
        extra_kwargs = {
            "feature_name": {"required": True},
            "feature_description": {"required": True},
        }


class PriceTierSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
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
        extra_kwargs = {
            "type": {"required": True, "read_only": True},
            "range_start": {"required": True, "read_only": True},
            "range_end": {"required": True, "allow_null": True, "read_only": True},
            "cost_per_batch": {"required": True, "allow_null": True, "read_only": True},
            "metric_units_per_batch": {
                "required": True,
                "allow_null": True,
                "read_only": True,
            },
            "batch_rounding_type": {
                "required": True,
                "allow_null": True,
                "allow_blank": False,
                "read_only": True,
            },
        }

    type = serializers.SerializerMethodField()
    batch_rounding_type = serializers.SerializerMethodField()

    def get_type(
        self, obj
    ) -> Literal[PRICE_TIER_TYPE.FLAT, PRICE_TIER_TYPE.PER_UNIT, PRICE_TIER_TYPE.FREE]:
        if obj.type == PriceTier.PriceTierType.FLAT:
            return PRICE_TIER_TYPE.FLAT
        elif obj.type == PriceTier.PriceTierType.PER_UNIT:
            return PRICE_TIER_TYPE.PER_UNIT
        elif obj.type == PriceTier.PriceTierType.FREE:
            return PRICE_TIER_TYPE.FREE
        else:
            raise ValueError("Invalid price tier type")

    def get_batch_rounding_type(
        self, obj
    ) -> Optional[
        Literal[
            BATCH_ROUNDING_TYPE.ROUND_UP,
            BATCH_ROUNDING_TYPE.ROUND_DOWN,
            BATCH_ROUNDING_TYPE.ROUND_NEAREST,
            BATCH_ROUNDING_TYPE.NO_ROUNDING,
        ]
    ]:
        if obj.batch_rounding_type == PriceTier.BatchRoundingType.ROUND_UP:
            return BATCH_ROUNDING_TYPE.ROUND_UP
        elif obj.batch_rounding_type == PriceTier.BatchRoundingType.ROUND_DOWN:
            return BATCH_ROUNDING_TYPE.ROUND_DOWN
        elif obj.batch_rounding_type == PriceTier.BatchRoundingType.ROUND_NEAREST:
            return BATCH_ROUNDING_TYPE.ROUND_NEAREST
        elif obj.batch_rounding_type == PriceTier.BatchRoundingType.NO_ROUNDING:
            return BATCH_ROUNDING_TYPE.NO_ROUNDING
        else:
            return None


class PlanComponentSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = PlanComponent
        fields = (
            "billable_metric",
            "tiers",
            "pricing_unit",
        )
        extra_kwargs = {
            "billable_metric": {"required": True, "read_only": True},
            "tiers": {"required": True},
            "pricing_unit": {"required": True, "read_only": True},
        }

    billable_metric = MetricSerializer()
    pricing_unit = PricingUnitSerializer()
    tiers = PriceTierSerializer(many=True)


class PriceAdjustmentSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = PriceAdjustment
        fields = (
            "price_adjustment_name",
            "price_adjustment_description",
            "price_adjustment_type",
            "price_adjustment_amount",
        )
        extra_kwargs = {
            "price_adjustment_name": {"required": True},
            "price_adjustment_description": {"required": True},
            "price_adjustment_type": {"required": True},
            "price_adjustment_amount": {"required": True},
        }


class PlanVersionSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = PlanVersion
        fields = (
            "description",
            "flat_fee_billing_type",
            "flat_rate",
            "components",
            "features",
            "price_adjustment",
            "usage_billing_frequency",
            "version",
            "status",
            "plan_name",
            "currency",
        )
        extra_kwargs = {
            "description": {"required": True, "read_only": True},
            "flat_fee_billing_type": {"required": True, "read_only": True},
            "flat_rate": {"required": True, "read_only": True},
            "components": {"required": True, "read_only": True},
            "features": {"required": True, "read_only": True},
            "price_adjustment": {
                "required": True,
                "allow_null": True,
                "read_only": True,
            },
            "usage_billing_frequency": {"required": True, "read_only": True},
            "version": {"required": True, "read_only": True},
            "status": {"required": True, "read_only": True},
            "plan_name": {"required": True, "read_only": True},
        }

    components = PlanComponentSerializer(many=True, source="plan_components")
    features = FeatureSerializer(many=True)
    price_adjustment = PriceAdjustmentSerializer(allow_null=True)

    plan_name = serializers.CharField(source="plan.plan_name")
    currency = PricingUnitSerializer(source="pricing_unit")

    def get_created_by(self, obj) -> str:
        if obj.created_by is not None:
            return obj.created_by.username
        else:
            return None

    def get_replace_with(self, obj) -> Union[int, None]:
        if obj.replace_with is not None:
            return obj.replace_with.version
        else:
            return None

    def get_transition_to(self, obj) -> Union[str, None]:
        if obj.transition_to is not None:
            return str(obj.transition_to.display_version)
        else:
            return None


class PlanNameAndIDSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = Plan
        fields = (
            "plan_name",
            "plan_id",
        )
        extra_kwargs = {
            "plan_name": {"required": True},
            "plan_id": {"required": True},
        }

    plan_id = PlanUUIDField()


class InvoiceUpdateSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = Invoice
        fields = ("payment_status",)

    payment_status = serializers.ChoiceField(
        choices=[INVOICE_STATUS_ENUM.PAID, INVOICE_STATUS_ENUM.UNPAID],
        required=True,
    )

    def validate(self, data):
        data = super().validate(data)
        if self.instance.external_payment_obj_id is not None:
            raise serializers.ValidationError(
                f"Can't manually update connected invoices. This invoice is connected to {self.instance.external_payment_obj_type}"
            )
        if data["payment_status"] == INVOICE_STATUS_ENUM.PAID:
            data["payment_status"] = Invoice.PaymentStatus.PAID
        elif data["payment_status"] == INVOICE_STATUS_ENUM.UNPAID:
            data["payment_status"] = Invoice.PaymentStatus.UNPAID
        elif data["payment_status"] == INVOICE_STATUS_ENUM.VOIDED:
            data["payment_status"] = Invoice.PaymentStatus.VOIDED
        elif data["payment_status"] == INVOICE_STATUS_ENUM.DRAFT:
            data["payment_status"] = Invoice.PaymentStatus.DRAFT
        return data

    def update(self, instance, validated_data):
        instance.payment_status = validated_data.get(
            "payment_status", instance.payment_status
        )
        instance.save()
        return instance


class InitialExternalPlanLinkSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = ExternalPlanLink
        fields = ("source", "external_plan_id")


class PlanSerializer(ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = (
            "plan_name",
            "plan_duration",
            "status",
            "external_links",
            "plan_id",
            "parent_plan",
            "target_customer",
            "display_version",
            "num_versions",
            "active_subscriptions",
            "tags",
        )
        extra_kwargs = {
            "plan_name": {"required": True},
            "plan_duration": {"required": True},
            "status": {"required": True},
            "external_links": {"required": True},
            "plan_id": {"required": True},
            "parent_plan": {"required": True, "allow_null": True},
            "target_customer": {"required": True, "allow_null": True},
            "display_version": {"required": True},
            "num_versions": {"required": True},
            "active_subscriptions": {"required": True},
            "tags": {"required": True},
        }

    plan_id = PlanUUIDField()
    parent_plan = PlanNameAndIDSerializer(allow_null=True)
    target_customer = LightweightCustomerSerializer(allow_null=True)
    display_version = PlanVersionSerializer()
    num_versions = serializers.SerializerMethodField(
        help_text="The number of versions that this plan has."
    )
    active_subscriptions = serializers.SerializerMethodField(
        help_text="The number of active subscriptions that this plan has across all versions.",
    )
    external_links = InitialExternalPlanLinkSerializer(
        many=True, help_text="The external links that this plan has."
    )
    tags = serializers.SerializerMethodField(help_text="The tags that this plan has.")

    def get_num_versions(self, obj) -> int:
        return obj.versions.all().count()

    def get_active_subscriptions(self, obj) -> int:
        try:
            return sum(x.active_subscriptions for x in obj.versions.all())
        except AttributeError:
            return (
                obj.active_subs_by_version().aggregate(res=Sum("active_subscriptions"))[
                    "res"
                ]
                or 0
            )

    def get_tags(self, obj) -> TagSerializer(many=True):
        data = TagSerializer(obj.tags.all(), many=True).data
        return data


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

    customer_id = serializers.CharField(
        source="cust_id",
        help_text="The id of the customer that this event is associated with, usually the customer id in your backend",
    )
    idempotency_id = serializers.CharField(
        required=True,
        help_text="A unique identifier for the specific event being passed in. Passing in a unique id allows Lotus to make sure no double counting occurs. We recommend using a UUID4. You can use the same idempotency_id again after 7 days",
    )


class SubscriptionRecordCreateSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
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
        help_text="Whether the subscription automatically renews. Defaults to true.",
    )
    is_new = serializers.BooleanField(required=False)
    subscription_filters = SubscriptionCategoricalFilterSerializer(
        many=True,
        required=False,
        help_text="Add filter key, value pairs that define which events will be applied to this plan subscription.",
    )

    # WRITE ONLY
    customer_id = SlugRelatedFieldWithOrganization(
        slug_field="customer_id",
        source="customer",
        queryset=Customer.objects.all(),
        write_only=True,
        help_text="The id provided when creating the customer",
    )
    plan_id = SlugRelatedFieldWithOrganization(
        slug_field="plan_id",
        source="billing_plan.plan",
        queryset=Plan.objects.all(),
        write_only=True,
        help_text="The Lotus plan_id, found in the billing plan object",
    )

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
        from metering_billing.invoice import generate_invoice

        filters = validated_data.pop("subscription_filters", [])
        subscription_filters = []
        for filter_data in filters:
            sub_cat_filter_dict = {
                "organization": validated_data["customer"].organization,
                "property_name": filter_data["property_name"],
                "operator": CATEGORICAL_FILTER_OPERATORS.ISIN,
                "comparison_value": [filter_data["value"]],
            }
            try:
                cf, _ = CategoricalFilter.objects.get_or_create(**sub_cat_filter_dict)
            except CategoricalFilter.MultipleObjectsReturned:
                cf = CategoricalFilter.objects.filter(**sub_cat_filter_dict).first()
            subscription_filters.append(cf)
        sub_record = SubscriptionRecord.objects.create_with_filters(
            **validated_data, subscription_filters=subscription_filters
        )
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


class LightweightPlanVersionSerializer(PlanVersionSerializer):
    class Meta(PlanVersionSerializer.Meta):
        model = PlanVersion
        fields = ("plan_id", "plan_name", "version_id")

    plan_name = serializers.CharField(read_only=True, source="plan.plan_name")
    plan_id = PlanUUIDField(read_only=True, source="plan.plan_id")
    version_id = PlanVersionUUIDField(read_only=True)


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


class SubscriptionSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
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

    subscription_id = SubscriptionUUIDField(read_only=True)
    customer = LightweightCustomerSerializer(read_only=True)
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
                ["customer_id", "plan_id", "billing_plan", "auto_renew", "invoice_pdf"]
            )
        )


class SubscriptionRecordUpdateSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = SubscriptionRecord
        fields = (
            "replace_plan_id",
            "invoicing_behavior",
            "usage_behavior",
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
    invoicing_behavior = serializers.ChoiceField(
        choices=INVOICING_BEHAVIOR.choices,
        default=INVOICING_BEHAVIOR.INVOICE_NOW,
        required=False,
        help_text="The invoicing behavior to use when replacing the plan. Invoice now will invoice the customer for the prorated difference of the old plan and the new plan, whereas add_to_next_invoice will wait until the end of the subscription to do the calculation.",
    )
    usage_behavior = serializers.ChoiceField(
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
    customer_id = SlugRelatedFieldWithOrganization(
        slug_field="customer_id",
        source="customer",
        queryset=Customer.objects.all(),
        required=True,
        help_text="Filter to a specific customer.",
    )
    plan_id = SlugRelatedFieldWithOrganization(
        slug_field="plan_id",
        source="billing_plan.plan",
        queryset=Plan.objects.all(),
        required=True,
        help_text="Filter to a specific plan.",
    )
    subscription_filters = SubscriptionCategoricalFilterSerializer(
        many=True,
        required=False,
        help_text="Filter to a specific set of subscription filters. If your billing model only allows for one subscription per customer, you very likely do not need this field. Must be formatted as a JSON-encoded + stringified list of dictionaries, where each dictionary has a key of 'property_name' and a key of 'value'.",
    )

    def validate(self, data):
        data = super().validate(data)
        if data.get("billing_plan"):
            data["plan"] = data["billing_plan"]["plan"]
        return data


class SubscriptionRecordFilterSerializerDelete(SubscriptionRecordFilterSerializer):
    plan_id = SlugRelatedFieldWithOrganization(
        slug_field="plan_id",
        source="billing_plan.plan",
        queryset=Plan.objects.all(),
        required=False,
        help_text="Filter to a specific plan. If not specified, all plans will be included in the cancellation request.",
    )


class SubscriptionRecordCancelSerializer(serializers.Serializer):
    flat_fee_behavior = serializers.ChoiceField(
        choices=FLAT_FEE_BEHAVIOR.choices,
        default=FLAT_FEE_BEHAVIOR.CHARGE_FULL,
        help_text="Can either charge the full amount of the flat fee, regardless of how long the customer has been on the plan, prorate the fflat fee, or charge nothing for the flat fee. If the flat fee has already been invoiced (e.g. in advance payment on last subscription), and the reuslting charge is less than the amount already invoiced, the difference will be refunded as a credit. Defaults to charge full amount.",
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


class ListSubscriptionRecordFilter(SubscriptionRecordFilterSerializer):
    subscription_filters = None
    status = serializers.MultipleChoiceField(
        choices=SUBSCRIPTION_STATUS.choices,
        required=False,
        default=[SUBSCRIPTION_STATUS.ACTIVE],
        help_text="Filter to a specific set of subscription statuses. Defaults to active.",
    )
    plan_id = SlugRelatedFieldWithOrganization(
        slug_field="plan_id",
        source="billing_plan.plan",
        queryset=Plan.objects.all(),
        required=False,
        help_text="Filter to a specific plan.",
    )
    range_start = serializers.DateTimeField(
        required=False,
        help_text="If specified, will only return subscriptions with an end date after this date.",
    )
    range_end = serializers.DateTimeField(
        required=False,
        help_text="If specified, will only return subscriptions with a start date before this date.",
    )

    def validate(self, data):
        # check that the customer ID matches an existing customer
        data = super().validate(data)
        return data


class InvoiceListFilterSerializer(serializers.Serializer):
    customer_id = SlugRelatedFieldWithOrganization(
        slug_field="customer_id",
        queryset=Customer.objects.all(),
        required=False,
        help_text="A filter for invoices for a specific customer",
    )
    payment_status = serializers.MultipleChoiceField(
        choices=[INVOICE_STATUS_ENUM.UNPAID, INVOICE_STATUS_ENUM.PAID],
        required=False,
        default=[INVOICE_STATUS_ENUM.PAID],
        help_text="A filter for invoices with a specific payment status",
    )

    def validate(self, data):
        data = super().validate(data)
        payment_status_str = data.get("payment_status", [])
        payment_status = []
        if INVOICE_STATUS_ENUM.PAID in payment_status_str:
            payment_status.append(Invoice.PaymentStatus.PAID)
        if INVOICE_STATUS_ENUM.UNPAID in payment_status_str:
            payment_status.append(Invoice.PaymentStatus.UNPAID)
        data["payment_status"] = payment_status
        return data


class CreditDrawdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerBalanceAdjustment
        fields = (
            "credit_id",
            "amount",
            "description",
            "applied_at",
        )

    extra_kwargs = {
        "credit_id": {"read_only": True, "required": True},
        "amount": {"required": True, "read_only": True},
        "description": {"required": True, "read_only": True},
        "applied_at": {"required": True, "read_only": True},
    }

    credit_id = BalanceAdjustmentUUIDField(source="adjustment_id")
    applied_at = serializers.DateTimeField(source="effective_at")
    amount = serializers.DecimalField(max_value=0, decimal_places=10, max_digits=20)


class CustomerBalanceAdjustmentSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = CustomerBalanceAdjustment
        fields = (
            "credit_id",
            "customer",
            "amount",
            "amount_remaining",
            "currency",
            "description",
            "effective_at",
            "expires_at",
            "status",
            "amount_paid",
            "amount_paid_currency",
            "drawdowns",
        )
        extra_kwargs = {
            "credit_id": {"read_only": True, "required": True},
            "customer": {"read_only": True, "required": True},
            "amount": {"required": True, "read_only": True},
            "amount_remaining": {"read_only": True, "required": True},
            "currency": {"read_only": True, "required": True},
            "description": {"required": True, "read_only": True},
            "effective_at": {"required": True, "read_only": True},
            "expires_at": {"required": True, "read_only": True, "allow_null": True},
            "status": {"read_only": True, "required": True},
            "amount_paid": {"read_only": True, "required": True},
            "amount_paid_currency": {
                "read_only": True,
                "required": True,
                "allow_null": True,
            },
            "drawdowns": {"read_only": True, "required": True},
        }

    credit_id = BalanceAdjustmentUUIDField(source="adjustment_id")
    customer = LightweightCustomerSerializer()
    currency = PricingUnitSerializer(source="pricing_unit")
    amount_paid_currency = PricingUnitSerializer()
    drawdowns = serializers.SerializerMethodField()
    amount = serializers.DecimalField(min_value=0, max_digits=20, decimal_places=10)
    amount_remaining = serializers.SerializerMethodField()

    def get_drawdowns(self, obj) -> CreditDrawdownSerializer(many=True):
        return CreditDrawdownSerializer(obj.drawdowns, many=True).data

    def get_amount_remaining(
        self, obj
    ) -> serializers.DecimalField(min_value=0, max_digits=20, decimal_places=10):
        return obj.get_remaining_balance()


class CustomerBalanceAdjustmentCreateSerializer(
    ConvertEmptyStringToSerializerMixin, serializers.ModelSerializer
):
    class Meta:
        model = CustomerBalanceAdjustment
        fields = (
            "customer_id",
            "amount",
            "currency_code",
            "description",
            "effective_at",
            "expires_at",
            "amount_paid",
            "amount_paid_currency_code",
        )
        extra_kwargs = {
            "customer_id": {"required": True, "write_only": True},
            "amount": {"required": True, "write_only": True},
            "currency_code": {"required": True, "write_only": True},
            "description": {"required": False, "write_only": True},
            "effective_at": {"required": False, "write_only": True},
            "expires_at": {"required": False, "write_only": True},
            "amount_paid": {"required": False, "write_only": True},
            "amount_paid_currency_code": {"required": False, "write_only": True},
        }

    customer_id = SlugRelatedFieldWithOrganization(
        slug_field="customer_id",
        queryset=Customer.objects.all(),
        required=True,
        source="customer",
    )
    currency_code = SlugRelatedFieldWithOrganization(
        slug_field="code",
        queryset=PricingUnit.objects.all(),
        required=True,
        source="pricing_unit",
        write_only=True,
    )
    amount_paid_currency_code = SlugRelatedFieldWithOrganization(
        slug_field="code",
        queryset=PricingUnit.objects.all(),
        required=False,
        source="amount_paid_currency",
        write_only=True,
    )
    amount_paid = serializers.DecimalField(
        min_value=0, max_digits=20, decimal_places=10, required=False
    )

    def validate(self, data):
        data = super().validate(data)
        amount = data.get("amount", 0)
        if amount <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        if data.get("amount_paid_currency_code") and data.get("amount_paid") <= 0:
            raise serializers.ValidationError("Amount paid must be greater than 0")
        return data

    def create(self, validated_data):
        balance_adjustment = super().create(validated_data)
        if balance_adjustment.amount_paid and balance_adjustment.amount_paid > 0:
            generate_balance_adjustment_invoice(balance_adjustment)
        return balance_adjustment


class CustomerBalanceAdjustmentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerBalanceAdjustment
        fields = (
            "description",
            "expires_at",
        )

    def validate(self, data):
        now = now_utc()
        expires_at = data.get("expires_at")
        if expires_at and expires_at < now:
            raise serializers.ValidationError("Expiration date must be in the future")
        return data

    def update(self, instance, validated_data):
        instance.description = validated_data.get("description", instance.description)
        instance.expires_at = validated_data.get("expires_at", instance.expires_at)
        instance.save()
        return instance


class CustomerBalanceAdjustmentFilterSerializer(serializers.Serializer):
    customer_id = SlugRelatedFieldWithOrganization(
        slug_field="customer_id",
        queryset=Customer.objects.all(),
        required=True,
        source="customer",
    )
    expires_before = serializers.DateTimeField(
        required=False, help_text="Filter to adjustments that expire before this date"
    )
    expires_after = serializers.DateTimeField(
        required=False, help_text="Filter to adjustments that expire after this date"
    )
    issued_before = serializers.DateTimeField(
        required=False,
        help_text="Filter to adjustments that were issued before this date",
    )
    issued_after = serializers.DateTimeField(
        required=False,
        help_text="Filter to adjustments that were issued after this date",
    )
    effective_before = serializers.DateTimeField(
        required=False,
        help_text="Filter to adjustments that are effective before this date",
    )
    effective_after = serializers.DateTimeField(
        required=False,
        help_text="Filter to adjustments that are effective after this date",
    )
    status = serializers.MultipleChoiceField(
        choices=CUSTOMER_BALANCE_ADJUSTMENT_STATUS.choices,
        required=False,
        default=[
            CUSTOMER_BALANCE_ADJUSTMENT_STATUS.ACTIVE,
            CUSTOMER_BALANCE_ADJUSTMENT_STATUS.INACTIVE,
        ],
        help_text="Filter to a specific set of adjustment statuses. Defaults to both active and inactive.",
    )
    currency_code = SlugRelatedFieldWithOrganization(
        slug_field="code",
        queryset=PricingUnit.objects.all(),
        required=False,
        source="pricing_unit",
        help_text="Filter to adjustments in a specific currency",
    )


class UsageAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsageAlert
        fields = (
            "usage_alert_id",
            "metric",
            "plan_version",
            "threshold",
        )

    usage_alert_id = UsageAlertUUIDField(read_only=True)
    metric = MetricSerializer()
    plan_version = LightweightPlanVersionSerializer()
