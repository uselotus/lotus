import datetime
import logging
from decimal import Decimal
from typing import Literal, Union

from django.conf import settings
from django.db.models import Max, Min, Sum
from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from metering_billing.invoice import generate_balance_adjustment_invoice
from metering_billing.models import (
    AddOnSpecification,
    Address,
    CategoricalFilter,
    ComponentFixedCharge,
    Customer,
    CustomerBalanceAdjustment,
    Event,
    ExternalPlanLink,
    Feature,
    Invoice,
    InvoiceLineItem,
    InvoiceLineItemAdjustment,
    Metric,
    NumericFilter,
    Organization,
    Plan,
    PlanComponent,
    PlanVersion,
    PriceAdjustment,
    PriceTier,
    PricingUnit,
    RecurringCharge,
    SubscriptionRecord,
    Tag,
    UsageAlert,
)
from metering_billing.payment_processors import PAYMENT_PROCESSOR_MAP
from metering_billing.serializers.serializer_utils import (
    AddOnSubscriptionUUIDField,
    AddOnUUIDField,
    BalanceAdjustmentUUIDField,
    ConvertEmptyStringToNullMixin,
    FeatureUUIDField,
    InvoiceUUIDField,
    MetricUUIDField,
    PlanUUIDField,
    PlanVersionUUIDField,
    SlugRelatedFieldWithOrganization,
    SubscriptionUUIDField,
    TimezoneFieldMixin,
    TimeZoneSerializerField,
    UsageAlertUUIDField,
)
from metering_billing.utils import convert_to_date, now_utc
from metering_billing.utils.enums import (
    CATEGORICAL_FILTER_OPERATORS,
    CUSTOMER_BALANCE_ADJUSTMENT_STATUS,
    FLAT_FEE_BEHAVIOR,
    INVOICE_STATUS_ENUM,
    INVOICING_BEHAVIOR,
    PAYMENT_PROCESSORS,
    PLAN_CUSTOM_TYPE,
    PLAN_DURATION,
    PLAN_VERSION_STATUS,
    SUBSCRIPTION_STATUS,
    TAX_PROVIDER,
    USAGE_BEHAVIOR,
    USAGE_BILLING_BEHAVIOR,
)

SVIX_CONNECTOR = settings.SVIX_CONNECTOR
logger = logging.getLogger("django.server")


class TagNameSerializer(TimezoneFieldMixin, serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("tag_name",)


class PricingUnitSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = PricingUnit
        fields = ("code", "name", "symbol")


class LightweightCustomerSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
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
            "customer_name": {"required": True, "read_only": True, "allow_null": True},
            "email": {"required": True, "read_only": True},
        }


class AddressCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ("city", "country", "line1", "line2", "postal_code", "state")


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ("city", "country", "line1", "line2", "postal_code", "state")

    extra_kwargs = {
        "city": {"required": True, "allow_null": True},
        "country": {"required": True, "allow_null": True},
        "line1": {"required": True, "allow_null": True},
        "line2": {"required": True, "allow_null": True, "allow_blank": True},
        "postal_code": {"required": True, "allow_null": True},
        "state": {"required": True, "allow_null": True},
    }


class LightweightCustomerSerializerForInvoice(LightweightCustomerSerializer):
    class Meta(LightweightCustomerSerializer.Meta):
        fields = LightweightCustomerSerializer.Meta.fields + ("address",)
        extra_kwargs = {
            **LightweightCustomerSerializer.Meta.extra_kwargs,
            "address": {"required": False, "allow_null": True},
        }

    address = serializers.SerializerMethodField(required=False, allow_null=True)

    def get_address(self, obj) -> AddressSerializer(allow_null=True, required=False):
        billing_address = obj.get_billing_address()
        if billing_address:
            return AddressSerializer(billing_address).data
        return None


class LightweightPlanVersionSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = PlanVersion
        fields = ("plan_name", "plan_id", "version_id", "version")
        extra_kwargs = {
            "plan_id": {"required": True, "read_only": True},
            "plan_name": {"required": True, "read_only": True},
            "version_id": {"required": True, "read_only": True},
            "version": {"required": True, "read_only": True},
        }

    plan_name = serializers.SerializerMethodField()
    plan_id = PlanUUIDField(source="plan.plan_id")
    version_id = PlanVersionUUIDField(read_only=True)
    version = serializers.SerializerMethodField()

    def get_plan_name(self, obj) -> str:
        return str(obj)

    def get_version(self, obj) -> Union[int, Literal["custom_version"]]:
        if obj.version == 0:
            return "custom_version"
        else:
            return obj.version


class LightweightPlanSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = Plan
        fields = (
            "plan_name",
            "plan_id",
        )
        extra_kwargs = {
            "plan_id": {"required": True, "read_only": True},
            "plan_name": {"required": True, "read_only": True},
        }

    plan_id = PlanUUIDField()


class CategoricalFilterSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = CategoricalFilter
        fields = ("property_name", "operator", "comparison_value")

    comparison_value = serializers.ListField(child=serializers.CharField())


class SubscriptionCategoricalFilterSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
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
        return CategoricalFilter.objects.get_or_create(
            **validated_data, operator=CATEGORICAL_FILTER_OPERATORS.ISIN
        )

    def to_representation(self, instance):
        data = {
            "property_name": instance.property_name,
            "value": instance.comparison_value[0],
        }
        return data


class SubscriptionCustomerSummarySerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = SubscriptionRecord
        fields = ("billing_plan_name", "plan_version", "end_date", "auto_renew")

    billing_plan_name = serializers.CharField(source="billing_plan.plan.plan_name")
    plan_version = serializers.IntegerField(source="billing_plan.version")


class SubscriptionCustomerDetailSerializer(SubscriptionCustomerSummarySerializer):
    class Meta(SubscriptionCustomerSummarySerializer.Meta):
        model = SubscriptionRecord
        fields = SubscriptionCustomerSummarySerializer.Meta.fields + ("start_date",)


class LightweightAddOnSerializer(TimezoneFieldMixin, serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ("addon_name", "addon_id", "addon_type", "billing_frequency")
        extra_kwargs = {
            "addon_name": {"required": True},
            "addon_id": {"required": True},
            "addon_type": {"required": True},
            "billing_frequency": {"required": True},
        }

    addon_name = serializers.CharField(
        help_text="The name of the add-on plan.",
        source="plan_name",
    )
    addon_id = AddOnUUIDField(
        source="plan_id",
        help_text="The ID of the add-on plan.",
    )
    addon_type = serializers.SerializerMethodField()
    billing_frequency = serializers.SerializerMethodField()

    def get_addon_type(self, obj) -> Literal["flat", "usage_based"]:
        version = obj.versions.first()
        if version.plan_components.all().count() > 0:
            return "usage_based"
        return "flat"

    def get_billing_frequency(
        self, obj
    ) -> serializers.ChoiceField(choices=AddOnSpecification.BillingFrequency.labels):
        version = obj.versions.first()
        return version.addon_spec.get_billing_frequency_display()


class LightweightAddOnSubscriptionRecordSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = SubscriptionRecord
        fields = (
            "addon_subscription_id",
            "start_date",
            "end_date",
            "addon",
            "fully_billed",
        )
        extra_kwargs = {
            "addon_subscription_id": {"required": True, "read_only": True},
            "start_date": {"required": True, "read_only": True},
            "end_date": {"required": True, "read_only": True},
            "addon": {"required": True, "read_only": True},
            "fully_billed": {"required": True, "read_only": True},
        }

    addon_subscription_id = AddOnSubscriptionUUIDField(source="subscription_record_id")
    addon = LightweightAddOnSerializer(source="billing_plan.plan")
    fully_billed = serializers.SerializerMethodField()

    def get_fully_billed(self, obj) -> bool:
        return all(obj.billing_records.values_list("fully_billed", flat=True))


class SubscriptionRecordSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = SubscriptionRecord
        fields = (
            "subscription_id",
            "start_date",
            "end_date",
            "auto_renew",
            "is_new",
            "subscription_filters",
            "customer",
            "billing_plan",
            "fully_billed",
            "addons",
            "metadata",
        )
        extra_kwargs = {
            "subscription_id": {"required": True},
            "start_date": {"required": True},
            "end_date": {"required": True},
            "auto_renew": {"required": True},
            "is_new": {"required": True},
            "subscription_filters": {"required": True},
            "customer": {"required": True},
            "fully_billed": {"required": True},
            "addons": {"required": True},
            "metadata": {"required": True},
        }

    subscription_id = SubscriptionUUIDField(source="subscription_record_id")
    subscription_filters = SubscriptionCategoricalFilterSerializer(
        many=True, source="filters"
    )
    customer = LightweightCustomerSerializer()
    billing_plan = LightweightPlanVersionSerializer()
    addons = LightweightAddOnSubscriptionRecordSerializer(
        many=True, source="addon_subscription_records"
    )
    fully_billed = serializers.SerializerMethodField()

    def get_fully_billed(self, obj) -> bool:
        return all(obj.billing_records.values_list("fully_billed", flat=True))


class InvoiceLineItemAdjustmentSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = InvoiceLineItemAdjustment
        fields = (
            "amount",
            "account",
            "adjustment_type",
        )

    adjustment_type = serializers.SerializerMethodField()
    account = serializers.SerializerMethodField()
    amount = serializers.DecimalField(
        max_digits=20, decimal_places=10, coerce_to_string=True
    )

    def get_adjustment_type(
        self, obj
    ) -> serializers.ChoiceField(
        choices=InvoiceLineItemAdjustment.AdjustmentType.labels
    ):
        return obj.get_adjustment_type_display()

    def get_account(self, obj) -> str:
        return str(obj.account)


@extend_schema_serializer(
    deprecate_fields=[
        "subtotal",
    ]
)
class InvoiceLineItemSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = InvoiceLineItem
        fields = (
            "name",
            "start_date",
            "end_date",
            "quantity",
            "billing_type",
            "metadata",
            "plan",
            "subscription_filters",
            # amounts
            "base",
            "adjustments",
            "amount",
            # deprecated
            "subtotal",
        )
        extra_kwargs = {
            "name": {"required": True},
            "start_date": {"required": True},
            "end_date": {"required": True},
            "quantity": {"required": True},
            "billing_type": {"required": True, "allow_blank": False},
            "metadata": {"required": True},
            "plan": {"required": True, "allow_null": True},
            # amounts
            "base": {"required": True},
            "adjustments": {"required": True},
            "amount": {"required": True},
            # deprecated
            "subtotal": {"required": True},
        }

    plan = serializers.SerializerMethodField(allow_null=True)
    subscription_filters = serializers.SerializerMethodField(allow_null=True)
    subtotal = serializers.DecimalField(
        max_digits=20,
        decimal_places=10,
        source="base",
    )
    adjustments = serializers.SerializerMethodField()

    def get_adjustments(self, obj) -> InvoiceLineItemAdjustmentSerializer(many=True):
        return InvoiceLineItemAdjustmentSerializer(
            obj.adjustments.all(), many=True
        ).data

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
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = Organization
        fields = ("name", "address", "phone", "email")

    name = serializers.CharField(source="organization_name")
    address = serializers.SerializerMethodField(required=False, allow_null=True)

    def get_address(self, obj) -> AddressSerializer(allow_null=True, required=False):
        billing_address = obj.get_address()
        if billing_address:
            return AddressSerializer(billing_address).data
        return None


@extend_schema_serializer(deprecate_fields=("cost_due",))
class InvoiceSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = Invoice
        fields = (
            "invoice_id",
            "invoice_number",
            "cost_due",
            "amount",
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
            "amount": {"required": True, "read_only": True},
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
        choices=PAYMENT_PROCESSORS.choices,
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
    cost_due = serializers.DecimalField(
        max_digits=20, decimal_places=10, min_value=0, source="amount"
    )

    def get_payment_status(
        self, obj
    ) -> serializers.ChoiceField(choices=Invoice.PaymentStatus.labels):
        return obj.get_payment_status_display()

    def get_start_date(self, obj) -> datetime.date:
        try:
            min_date = obj.min_date
        except AttributeError:
            min_date = obj.line_items.all().aggregate(min_date=Min("start_date"))[
                "min_date"
            ]
        return (
            convert_to_date(min_date) if min_date else convert_to_date(obj.issue_date)
        )

    def get_end_date(self, obj) -> datetime.date:
        try:
            max_date = obj.max_date
        except AttributeError:
            max_date = obj.line_items.all().aggregate(max_date=Max("end_date"))[
                "max_date"
            ]
        return (
            convert_to_date(max_date) if max_date else convert_to_date(obj.issue_date)
        )


class LightweightInvoiceSerializer(InvoiceSerializer):
    class Meta(InvoiceSerializer.Meta):
        fields = tuple(
            set(InvoiceSerializer.Meta.fields)
            - set(
                [
                    "line_items",
                    "customer",
                ]
            )
        )
        extra_kwargs = {**InvoiceSerializer.Meta.extra_kwargs}


class CustomerStripeIntegrationSerializer(serializers.Serializer):
    stripe_id = serializers.CharField()
    has_payment_method = serializers.BooleanField()


class CustomerBraintreeIntegrationSerializer(serializers.Serializer):
    braintree_id = serializers.CharField()
    has_payment_method = serializers.BooleanField()


class CustomerIntegrationsSerializer(serializers.Serializer):
    stripe = CustomerStripeIntegrationSerializer(required=False, allow_null=True)
    braintree = CustomerBraintreeIntegrationSerializer(required=False, allow_null=True)


@extend_schema_serializer(deprecate_fields=["address"])
class CustomerSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
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
            "payment_provider_id",
            "has_payment_method",
            "address",
            "billing_address",
            "shipping_address",
            "tax_rate",
            "timezone",
            "tax_providers",
        )
        extra_kwargs = {
            "customer_id": {"required": True, "read_only": True},
            "email": {"required": True, "read_only": True},
            "customer_name": {"required": True, "read_only": True, "allow_null": True},
            "invoices": {"required": True, "read_only": True},
            "total_amount_due": {"required": True, "read_only": True},
            "subscriptions": {"required": True, "read_only": True},
            "integrations": {"required": True, "read_only": True},
            "default_currency": {"required": True, "read_only": True},
            "payment_provider": {"required": True, "read_only": True},
            "payment_provider_id": {
                "required": True,
                "read_only": True,
                "allow_null": True,
                "allow_blank": True,
            },
            "has_payment_method": {"required": True, "read_only": True},
            "address": {"required": True, "read_only": True},
            "tax_rate": {"required": True, "read_only": True},
            "timezone": {"required": True, "read_only": True},
        }

    customer_id = serializers.CharField()
    email = serializers.EmailField()
    subscriptions = serializers.SerializerMethodField()
    invoices = serializers.SerializerMethodField()
    total_amount_due = serializers.SerializerMethodField()
    default_currency = PricingUnitSerializer()
    integrations = serializers.SerializerMethodField(
        help_text="A dictionary containing the customer's integrations. Keys are the integration type, and the value is a dictionary containing the integration's properties, which can vary by integration.",
    )
    payment_provider = serializers.ChoiceField(
        choices=PAYMENT_PROCESSORS.choices,
        allow_null=True,
        required=True,
        allow_blank=False,
    )
    payment_provider_id = serializers.SerializerMethodField()
    has_payment_method = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    billing_address = serializers.SerializerMethodField()
    shipping_address = serializers.SerializerMethodField()
    timezone = TimeZoneSerializerField(use_pytz=True)
    tax_providers = serializers.SerializerMethodField(
        help_text="A list of tax providers that are enabled for this customer. The list is ordered, meaning we will succesively try to calculate taxes using each provider until we find one that works."
    )

    def get_tax_providers(
        self, obj
    ) -> serializers.ListField(
        child=serializers.ChoiceField(choices=TAX_PROVIDER.labels), required=True
    ):
        return obj.get_readable_tax_providers()

    def get_billing_address(
        self, obj
    ) -> AddressSerializer(allow_null=True, required=True):
        billing_address = obj.get_billing_address()
        if billing_address:
            return AddressSerializer(billing_address).data
        return None

    def get_shipping_address(
        self, obj
    ) -> AddressSerializer(allow_null=True, required=True):
        shipping_address = obj.get_shipping_address()
        if shipping_address:
            return AddressSerializer(shipping_address).data
        return None

    def get_payment_provider_id(
        self, obj
    ) -> serializers.CharField(allow_null=True, required=True):
        d = self.get_integrations(obj)
        if obj.payment_provider == PAYMENT_PROCESSORS.STRIPE:
            stripe_dict = d.get(PAYMENT_PROCESSORS.STRIPE)
            if stripe_dict:
                return stripe_dict["stripe_id"]
        elif obj.payment_provider == PAYMENT_PROCESSORS.BRAINTREE:
            braintree_dict = d.get(PAYMENT_PROCESSORS.BRAINTREE)
            if braintree_dict:
                return braintree_dict["paypal_id"]
        return None

    def get_address(self, obj) -> AddressSerializer(allow_null=True, required=True):
        billing_address = obj.get_billing_address()
        if billing_address:
            return AddressSerializer(billing_address).data
        return None

    def get_has_payment_method(self, obj) -> bool:
        d = self.get_integrations(obj)
        if obj.payment_provider == PAYMENT_PROCESSORS.STRIPE:
            stripe_dict = d.get(PAYMENT_PROCESSORS.STRIPE)
            if stripe_dict:
                return stripe_dict["has_payment_method"]
        elif obj.payment_provider == PAYMENT_PROCESSORS.BRAINTREE:
            braintree_dict = d.get(PAYMENT_PROCESSORS.BRAINTREE)
            if braintree_dict:
                return braintree_dict["has_payment_method"]
        return False

    def _format_stripe_integration(
        self, stripe_connections_dict
    ) -> CustomerStripeIntegrationSerializer:
        return {
            "stripe_id": stripe_connections_dict["id"],
            "has_payment_method": len(
                stripe_connections_dict.get("payment_methods", [])
            )
            > 0,
        }

    def _format_braintree_integration(
        self, braintree_connections_dict
    ) -> CustomerBraintreeIntegrationSerializer:
        return {
            "braintree_id": braintree_connections_dict["id"],
            "has_payment_method": len(
                braintree_connections_dict.get("payment_methods", [])
            )
            > 0,
        }

    def get_integrations(self, customer) -> CustomerIntegrationsSerializer:
        d = {}
        if customer.stripe_integration:
            d[PAYMENT_PROCESSORS.STRIPE] = {
                "stripe_id": customer.stripe_integration.stripe_customer_id,
                "has_payment_method": PAYMENT_PROCESSOR_MAP[
                    PAYMENT_PROCESSORS.STRIPE
                ].has_payment_method(customer),
            }
        else:
            d[PAYMENT_PROCESSORS.STRIPE] = None
        if customer.braintree_integration:
            d[PAYMENT_PROCESSORS.BRAINTREE] = {
                "braintree_id": customer.braintree_integration.braintree_customer_id,
                "has_payment_method": PAYMENT_PROCESSOR_MAP[
                    PAYMENT_PROCESSORS.BRAINTREE
                ].has_payment_method(customer),
            }
        else:
            d[PAYMENT_PROCESSORS.BRAINTREE] = None
        return d

    def get_subscriptions(self, obj) -> SubscriptionRecordSerializer(many=True):
        try:
            sr_objs = obj.active_subscription_records
        except AttributeError:
            sr_objs = (
                obj.subscription_records.active()
                .filter(organization=obj.organization)
                .order_by("start_date")
            )
        return SubscriptionRecordSerializer(sr_objs, many=True).data

    def get_invoices(self, obj) -> LightweightInvoiceSerializer(many=True):
        try:
            timeline = obj.active_invoices
        except AttributeError:
            timeline = obj.invoices.filter(
                payment_status__in=[
                    Invoice.PaymentStatus.PAID,
                    Invoice.PaymentStatus.UNPAID,
                ],
                organization=obj.organization,
            ).order_by("-issue_date")
        timeline = LightweightInvoiceSerializer(timeline, many=True).data
        return timeline

    def get_total_amount_due(self, obj) -> Decimal:
        try:
            return obj.total_amount_due or Decimal(0)
        except AttributeError:
            return Decimal(0)


@extend_schema_serializer(deprecate_fields=["address"])
class CustomerCreateSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
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
            "billing_address",
            "shipping_address",
            "tax_rate",
        )
        extra_kwargs = {
            "customer_id": {"required": True},
            "email": {"required": True},
        }

    payment_provider = serializers.ChoiceField(
        choices=PAYMENT_PROCESSORS.choices,
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
    billing_address = AddressSerializer(required=False, allow_null=True)
    shipping_address = AddressSerializer(required=False, allow_null=True)

    def validate(self, data):
        super().validate(data)
        payment_provider = data.get("payment_provider", None)
        payment_provider_id = data.get("payment_provider_id", None)
        if payment_provider or payment_provider_id:
            if not PAYMENT_PROCESSOR_MAP[payment_provider].organization_connected(
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
        payment_provider = validated_data.pop("payment_provider", None)
        if payment_provider:
            payment_provider_valid = PAYMENT_PROCESSOR_MAP[
                payment_provider
            ].organization_connected(self.context["organization"])
        else:
            payment_provider_valid = False
        address = validated_data.pop("address", None)
        billing_address = validated_data.pop("billing_address", None)
        shipping_address = validated_data.pop("shipping_address", None)
        customer = Customer.objects.create(**validated_data)
        if address:
            address = Address.objects.get_or_create(
                **address, organization=self.context["organization"]
            )
            customer.billing_address = address
        if billing_address:
            billing_address = Address.objects.get_or_create(
                **billing_address, organization=self.context["organization"]
            )
            customer.billing_address = billing_address
        if shipping_address:
            shipping_address = Address.objects.get_or_create(
                **shipping_address, organization=self.context["organization"]
            )
            customer.shipping_address = shipping_address
        if address or billing_address or shipping_address:
            customer.save()
        if payment_provider and payment_provider_valid:
            PAYMENT_PROCESSOR_MAP[payment_provider].connect_customer(customer, pp_id)
        else:
            for pp in PAYMENT_PROCESSORS:
                if PAYMENT_PROCESSOR_MAP[pp].organization_connected(
                    self.context["organization"]
                ):
                    PAYMENT_PROCESSOR_MAP[pp].create_customer_flow(customer)

        return customer


class NumericFilterSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = NumericFilter
        fields = ("property_name", "operator", "comparison_value")


class LightweightMetricSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = Metric
        fields = (
            "metric_id",
            "event_name",
            "metric_name",
        )
        extra_kwargs = {
            "metric_id": {"required": True, "read_only": True, "allow_blank": False},
            "event_name": {"required": True, "read_only": True},
            "metric_name": {"required": True, "read_only": True},
        }

    metric_id = MetricUUIDField()
    metric_name = serializers.CharField(source="billable_metric_name")


class MetricSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
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
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = Feature
        fields = (
            "feature_id",
            "feature_name",
            "feature_description",
        )
        extra_kwargs = {
            "feature_id": {
                "required": True,
                "read_only": True,
            },
            "feature_name": {"required": True, "read_only": True},
            "feature_description": {"required": True, "read_only": True},
        }

    feature_id = FeatureUUIDField()


class PriceTierSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
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

    cost_per_batch = serializers.DecimalField(
        max_digits=20, decimal_places=10, min_value=0, allow_null=True
    )
    metric_units_per_batch = serializers.DecimalField(
        max_digits=20, decimal_places=10, min_value=0, allow_null=True
    )
    range_start = serializers.DecimalField(
        max_digits=20, decimal_places=10, min_value=0
    )
    range_end = serializers.DecimalField(
        max_digits=20, decimal_places=10, min_value=0, allow_null=True
    )
    type = serializers.SerializerMethodField()
    batch_rounding_type = serializers.SerializerMethodField()

    def get_type(
        self, obj
    ) -> serializers.ChoiceField(choices=PriceTier.PriceTierType.labels):
        return obj.get_type_display()

    def get_batch_rounding_type(
        self, obj
    ) -> serializers.ChoiceField(
        choices=PriceTier.BatchRoundingType.labels, allow_null=True
    ):
        return obj.get_batch_rounding_type_display()


class ComponentChargeSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = ComponentFixedCharge
        fields = ("units", "charge_behavior")
        extra_kwargs = {
            "units": {"required": True, "read_only": True},
            "charge_behavior": {"required": True, "read_only": True},
        }

    units = serializers.DecimalField(
        max_digits=20,
        decimal_places=10,
        min_value=0,
        allow_null=True,
        help_text="The number of units to charge for. If left null, then it will be required at subscription create time.",
    )
    charge_behavior = serializers.SerializerMethodField()

    def get_charge_behavior(
        self, obj
    ) -> serializers.ChoiceField(choices=ComponentFixedCharge.ChargeBehavior.labels):
        return obj.get_charge_behavior_display()


class PlanComponentSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = PlanComponent
        fields = (
            "billable_metric",
            "tiers",
            "pricing_unit",
            "invoicing_interval_unit",
            "invoicing_interval_count",
            "reset_interval_unit",
            "reset_interval_count",
            "prepaid_charge",
        )
        extra_kwargs = {
            "billable_metric": {"required": True, "read_only": True},
            "tiers": {"required": True},
            "pricing_unit": {"required": True, "read_only": True},
            "invoicing_interval_unit": {"required": True, "read_only": True},
            "invoicing_interval_count": {"required": True, "read_only": True},
            "reset_interval_unit": {"required": True, "read_only": True},
            "reset_interval_count": {"required": True, "read_only": True},
            "prepaid_charge": {"required": True, "read_only": True},
        }

    billable_metric = MetricSerializer()
    pricing_unit = PricingUnitSerializer()
    tiers = PriceTierSerializer(many=True)
    invoicing_interval_unit = serializers.SerializerMethodField()
    reset_interval_unit = serializers.SerializerMethodField()
    prepaid_charge = ComponentChargeSerializer(allow_null=True, source="fixed_charge")

    def get_invoicing_interval_unit(
        self, obj
    ) -> serializers.ChoiceField(
        choices=RecurringCharge.IntervalLengthType.labels, allow_null=True
    ):
        if obj.invoicing_interval_unit is None:
            return None
        return obj.get_invoicing_interval_unit_display()

    def get_reset_interval_unit(
        self, obj
    ) -> serializers.ChoiceField(
        choices=RecurringCharge.IntervalLengthType.labels, allow_null=True
    ):
        if obj.reset_interval_unit is None:
            return None
        return obj.get_reset_interval_unit_display()


class PriceAdjustmentSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
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


class RecurringChargeSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = RecurringCharge
        fields = (
            "name",
            "charge_timing",
            "charge_behavior",
            "amount",
            "pricing_unit",
            "invoicing_interval_unit",
            "invoicing_interval_count",
            "reset_interval_unit",
            "reset_interval_count",
        )
        extra_kwargs = {
            "name": {"required": True},
            "charge_timing": {"required": True},
            "amount": {"required": True},
            "pricing_unit": {"required": True},
            "invoicing_interval_unit": {"required": True},
            "invoicing_interval_count": {"required": True},
            "reset_interval_unit": {"required": True},
            "reset_interval_count": {"required": True},
        }

    pricing_unit = PricingUnitSerializer()
    charge_timing = serializers.SerializerMethodField()
    charge_behavior = serializers.SerializerMethodField()
    invoicing_interval_unit = serializers.SerializerMethodField()
    reset_interval_unit = serializers.SerializerMethodField()

    def get_charge_timing(
        self, obj
    ) -> serializers.ChoiceField(choices=RecurringCharge.ChargeTimingType.labels):
        return obj.get_charge_timing_display()

    def get_charge_behavior(
        self, obj
    ) -> serializers.ChoiceField(choices=RecurringCharge.ChargeBehaviorType.labels):
        return obj.get_charge_behavior_display()

    def get_invoicing_interval_unit(
        self, obj
    ) -> serializers.ChoiceField(
        choices=RecurringCharge.IntervalLengthType.labels, allow_null=True
    ):
        if obj.invoicing_interval_unit is None:
            return None
        return obj.get_invoicing_interval_unit_display()

    def get_reset_interval_unit(
        self, obj
    ) -> serializers.ChoiceField(
        choices=RecurringCharge.IntervalLengthType.labels, allow_null=True
    ):
        if obj.reset_interval_unit is None:
            return None
        return obj.get_reset_interval_unit_display()


@extend_schema_serializer(
    deprecate_fields=[
        "usage_billing_frequency",
        "flat_fee_billing_type",
        "flat_rate",
        "description",
    ]
)
class PlanVersionSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = PlanVersion
        fields = (
            "recurring_charges",
            "components",
            "features",
            "price_adjustment",
            "version",
            "status",
            "plan_name",
            "currency",
            "version",
            "active_from",
            "active_to",
            "localized_name",
            "target_customers",
            "created_on",
            # DEPRECATED
            "usage_billing_frequency",
            "flat_fee_billing_type",
            "flat_rate",
            "description",
        )
        extra_kwargs = {
            "components": {"required": True, "read_only": True},
            "recurring_charges": {"required": True, "read_only": True},
            "features": {"required": True, "read_only": True},
            "price_adjustment": {
                "required": True,
                "allow_null": True,
                "read_only": True,
            },
            "version": {"required": True, "read_only": True},
            "plan_name": {"required": True, "read_only": True},
            "active_from": {"required": True, "read_only": True},
            "active_to": {"required": True, "read_only": True},
            "localized_name": {"required": True, "read_only": True},
            "status": {"required": False, "read_only": True},
            "target_customers": {"required": False, "read_only": True},
            "created_on": {"required": False, "read_only": True},
            # DEPRECATED
            "flat_fee_billing_type": {"required": False, "read_only": True},
            "flat_rate": {"required": False, "read_only": True},
            "usage_billing_frequency": {"required": False, "read_only": True},
            "description": {"required": False, "read_only": True},
        }

    components = PlanComponentSerializer(many=True, source="plan_components")
    features = FeatureSerializer(many=True)
    recurring_charges = serializers.SerializerMethodField()
    price_adjustment = PriceAdjustmentSerializer(allow_null=True)
    plan_name = serializers.SerializerMethodField()
    currency = PricingUnitSerializer()
    version = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    target_customers = LightweightCustomerSerializer(many=True)

    # DEPRECATED
    description = serializers.SerializerMethodField()
    usage_billing_frequency = serializers.SerializerMethodField()
    flat_rate = serializers.SerializerMethodField()
    flat_fee_billing_type = serializers.SerializerMethodField()

    def get_plan_name(self, obj) -> serializers.CharField():
        return str(obj)

    def get_status(
        self, obj
    ) -> serializers.ChoiceField(choices=PLAN_VERSION_STATUS.choices):
        return obj.get_status()

    def get_recurring_charges(self, obj) -> RecurringChargeSerializer(many=True):
        try:
            return RecurringChargeSerializer(
                obj.recurring_charges_prefetched, many=True
            ).data
        except AttributeError as e:
            logger.error("Error getting get_recurring_charges: %s", e)
            return RecurringChargeSerializer(
                obj.recurring_charges.all(), many=True
            ).data

    def get_created_by(self, obj) -> str:
        if obj.created_by is not None:
            return obj.created_by.username
        else:
            return None

    def get_replace_with(self, obj) -> Union[str, None]:
        if obj.replace_with is not None:
            return str(obj.replace_with)
        else:
            return None

    def get_version(self, obj) -> Union[int, Literal["custom_version"]]:
        if obj.version == 0:
            return "custom_version"
        else:
            return obj.version

    # DEPRECATED
    def get_usage_billing_frequency(self, obj) -> Union[str, None]:
        return None

    def get_description(self, obj) -> Union[str, None]:
        return obj.plan.plan_description

    def get_flat_rate(
        self, obj
    ) -> serializers.DecimalField(max_digits=20, decimal_places=10, min_value=0):
        try:
            return sum(x.amount for x in obj.recurring_charges_prefetched)
        except AttributeError as e:
            logger.error("Error getting get_flat_rate: %s", e)
            return sum(x.amount for x in obj.recurring_charges.all())

    def get_flat_fee_billing_type(
        self, obj
    ) -> serializers.ChoiceField(choices=RecurringCharge.ChargeTimingType.labels):
        try:
            charges = obj.recurring_charges_prefetched
            if len(charges) == 0:
                return RecurringCharge.ChargeTimingType.IN_ADVANCE.label
            else:
                return charges[0].get_charge_timing_display()
        except AttributeError as e:
            logger.error("Error getting flat_fee_billing_type: %s", e)
            recurring_charge = obj.recurring_charges.first()
            if recurring_charge is not None:
                return recurring_charge.get_charge_timing_display()
            else:
                return RecurringCharge.ChargeTimingType.IN_ADVANCE.label


class PlanNameAndIDSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
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
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
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
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = ExternalPlanLink
        fields = ("source", "external_plan_id")


@extend_schema_serializer(
    deprecate_fields=["display_version", "parent_plan", "target_customer", "status"]
)
class PlanSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = Plan
        fields = (
            "plan_id",
            "plan_name",
            "plan_duration",
            "plan_description",
            "external_links",
            "num_versions",
            "active_version",
            "active_subscriptions",
            "tags",
            "versions",
            # DEPRECATED
            "parent_plan",
            "target_customer",
            "display_version",
            "status",
        )
        extra_kwargs = {
            "plan_name": {"required": True},
            "plan_duration": {"required": True},
            "plan_description": {"required": True},
            "external_links": {"required": True},
            "plan_id": {"required": True},
            "num_versions": {"required": True},
            "active_version": {"required": True},
            "active_subscriptions": {"required": True},
            "tags": {"required": True},
            "versions": {"required": True},
            # DEPRECATED
            "parent_plan": {"required": False},
            "target_customer": {"required": False},
            "status": {"required": False},
            "display_version": {"required": False},
        }

    plan_id = PlanUUIDField()
    num_versions = serializers.SerializerMethodField(
        help_text="The number of versions that this plan has."
    )
    active_version = serializers.SerializerMethodField(
        help_text="This plan's currently active version."
    )
    active_subscriptions = serializers.SerializerMethodField(
        help_text="The number of active subscriptions that this plan has across all versions.",
    )
    external_links = InitialExternalPlanLinkSerializer(
        many=True, help_text="The external links that this plan has."
    )
    tags = serializers.SerializerMethodField(help_text="The tags that this plan has.")
    versions = PlanVersionSerializer(many=True, help_text="This plan's versions.")

    # DEPRECATED
    parent_plan = serializers.SerializerMethodField(
        help_text="[DEPRECATED] The parent plan that this plan has."
    )
    target_customer = serializers.SerializerMethodField(
        help_text="[DEPRECATED] The target customer that this plan has."
    )
    display_version = serializers.SerializerMethodField(
        help_text="[DEPRECATED] Display version has been deprecated. Use 'versions' instead. We will still return this field for now with some heuristics for figuring out what the desired version is, but it will be removed in the near future."
    )
    status = serializers.SerializerMethodField(
        help_text="[DEPRECATED] The status of this plan."
    )

    def get_num_versions(self, obj) -> int:
        try:
            nv = len({x.version for x in obj.versions_prefetched if not x.is_custom})
            return nv
        except AttributeError:
            logger.error(
                "PlanSerializer.get_num_versions() called without prefetching 'versions_prefetched'"
            )
            return (
                obj.versions.filter(is_custom=False)
                .values_list("version", flat=True)
                .count()
            )

    def get_active_version(self, obj) -> int:
        return (
            obj.versions.active()
            .filter(is_custom=False)
            .values_list("version", flat=True)
            .order_by("-version")
            .first()
            or 0
        )

    def get_active_subscriptions(self, obj) -> int:
        try:
            return sum(x.active_subscriptions for x in obj.versions_prefetched)
        except AttributeError:
            logger.error(
                "PlanSerializer.get_active_subscriptions() called without prefetching 'versions_prefetched'"
            )
            return (
                obj.active_subs_by_version().aggregate(res=Sum("active_subscriptions"))[
                    "res"
                ]
                or 0
            )

    def get_tags(self, obj) -> serializers.ListField(child=serializers.SlugField()):
        return obj.tags.all().values_list("tag_name", flat=True)

    # DEPRECATED
    def get_status(self, obj) -> str:
        return "active"

    def get_parent_plan(self, obj) -> PlanNameAndIDSerializer(allow_null=True):
        return None

    def get_target_customer(
        self, obj
    ) -> LightweightCustomerSerializer(allow_null=True):
        return None

    def get_display_version(self, obj) -> PlanVersionSerializer:
        return PlanVersionSerializer(obj.versions.active().first()).data


class EventSerializer(TimezoneFieldMixin, serializers.ModelSerializer):
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
        help_text="A unique identifier for the specific event being passed in. Passing in a unique id allows Lotus to make sure no double counting occurs. We recommend using a UUID4.",
    )


class SubscriptionRecordCreateSerializerOld(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
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
    customer_id = SlugRelatedFieldWithOrganization(
        slug_field="customer_id",
        source="customer",
        queryset=Customer.objects.all(),
        write_only=True,
        help_text="The id provided when creating the customer",
    )
    plan_id = SlugRelatedFieldWithOrganization(
        slug_field="plan_id",
        queryset=Plan.objects.all(),
        write_only=True,
        required=False,
        help_text="The Lotus plan_id, found in the billing plan object. This field has been deprecated in favor of version_id for the sake of being explicit. If used, a best effort will be made to find the correct plan version (matching preferred currencies, prioritizing custom plans), but if more than one plan versions matches this criteria this will return an error.",
    )

    def validate(self, data):
        # extract the plan version from the plan
        if "plan_id" in data:
            data["billing_plan"] = data.pop("plan_id").get_version_for_customer(
                data["customer"]
            )
            if data["billing_plan"] is None:
                raise serializers.ValidationError(
                    "Unable to find a singular plan version that matches the plan_id. Please specify a version_id instead."
                )
        else:
            raise serializers.ValidationError("plan_id must be specified")
        if data["billing_plan"].is_custom:
            if data["customer"] not in data["billing_plan"].target_customers.all():
                raise serializers.ValidationError(
                    "The plan version you are trying to create a subscription for is a custom plan that is not available to this customer."
                )
        return data

    def create(self, validated_data):
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
                cf = (
                    CategoricalFilter.objects.filter(**sub_cat_filter_dict)
                    .first()
                    .delete()
                )
                cf = CategoricalFilter.objects.filter(**sub_cat_filter_dict).first()
            subscription_filters.append(cf)
        sr = SubscriptionRecord.create_subscription_record(
            start_date=validated_data["start_date"],
            end_date=validated_data.get("end_date"),
            billing_plan=validated_data["billing_plan"],
            customer=validated_data["customer"],
            organization=self.context["organization"],
            is_new=validated_data.get("is_new", True),
            subscription_filters=subscription_filters,
            quantity=validated_data.get("quantity", 1),
        )
        return sr


class ComponentsFixedChargeInitialValueSerializer(serializers.Serializer):
    metric_id = SlugRelatedFieldWithOrganization(
        slug_field="metric_id",
        queryset=Metric.objects.all(),
        write_only=True,
        help_text="The id of the metric that this initial value is for",
        source="metric",
    )
    units = serializers.DecimalField(
        max_digits=20,
        decimal_places=10,
        help_text="The number of units of the metric that this initial value is for",
        min_value=0,
    )


@extend_schema_serializer(exclude_fields=["version_id"])
class SubscriptionRecordCreateSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
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
            "version_id",
            "plan_id",
            "component_fixed_charges_initial_units",
            "metadata",
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

    customer_id = SlugRelatedFieldWithOrganization(
        slug_field="customer_id",
        source="customer",
        queryset=Customer.objects.all(),
        write_only=True,
        help_text="The id provided when creating the customer",
    )
    version_id = SlugRelatedFieldWithOrganization(
        slug_field="version_id",
        source="billing_plan",
        queryset=PlanVersion.plan_versions.all(),
        write_only=True,
        help_text="The Lotus version_id, found in the billing plan object. For maximum specificity, you can use this to control exactly what plan version becomes part of the subscription.",
        required=False,
    )
    plan_id = SlugRelatedFieldWithOrganization(
        slug_field="plan_id",
        source="plan",
        queryset=Plan.objects.all(),
        write_only=True,
        required=False,
        help_text="The Lotus plan_id, found in the billing plan object. We will make a best-effort attempt to find the correct plan version (matching preferred currencies, prioritizing custom plans), but if more than one plan version or no plan version matches these criteria this will return an error.",
    )
    component_fixed_charges_initial_units = ComponentsFixedChargeInitialValueSerializer(
        many=True,
        required=False,
        help_text="The initial units for the plan components' prepaid fixed charges. This is only required if the plan has plan components where you did not specify the initial units.",
    )
    metadata = serializers.JSONField(
        required=False,
        help_text="A JSON object containing additional information about the subscription.",
    )

    def validate(self, data):
        data = super().validate(data)
        plan_id_present = data.get("plan") is not None
        version_id_present = data.get("billing_plan") is not None
        if plan_id_present == version_id_present:  # xor check
            raise serializers.ValidationError(
                "You must specify exactly one of plan_id or version_id"
            )
        if plan_id_present:  # this means billing plan is not present
            data["billing_plan"] = data.pop("plan").get_version_for_customer(
                data["customer"]
            )
            if data["billing_plan"] is None:
                raise serializers.ValidationError(
                    "Unable to find a singular plan version that matches the plan_id. Please specify a version_id instead."
                )
        if data["billing_plan"].is_custom:
            if data["customer"] not in data["billing_plan"].target_customers.all():
                raise serializers.ValidationError(
                    "The plan version you are trying to create a subscription for is a custom plan that is not available to this customer."
                )
        return data

    def create(self, validated_data):
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
                cf = (
                    CategoricalFilter.objects.filter(**sub_cat_filter_dict)
                    .first()
                    .delete()
                )
                cf = CategoricalFilter.objects.filter(**sub_cat_filter_dict).first()
            subscription_filters.append(cf)
        sr = SubscriptionRecord.create_subscription_record(
            start_date=validated_data["start_date"],
            end_date=validated_data.get("end_date"),
            billing_plan=validated_data["billing_plan"],
            customer=validated_data["customer"],
            organization=self.context["organization"],
            subscription_filters=subscription_filters,
            is_new=validated_data.get("is_new", True),
            quantity=validated_data.get("quantity", 1),
            component_fixed_charges_initial_units=validated_data.get(
                "component_fixed_charges_initial_units", []
            ),
        )
        sr.metadata = validated_data.get("metadata", {})
        sr.save()
        return sr


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


class SubscriptionInvoiceSerializer(SubscriptionRecordSerializer):
    class Meta(SubscriptionRecordSerializer.Meta):
        model = SubscriptionRecord
        fields = tuple(
            set(SubscriptionRecordSerializer.Meta.fields)
            - set(
                ["customer_id", "plan_id", "billing_plan", "auto_renew", "invoice_pdf"]
            )
        )


class SubscriptionRecordUpdateSerializerOld(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
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
        source="plan",
        queryset=Plan.objects.all(),
        write_only=True,
        required=False,
        help_text="[DEPRECATED] Will currently perform a best-effort attempt to find the correct plan version to replace the current plan with. If more than one plan version matches the criteria, this will return an error. Use the change_plan method of a subscription instance instead.",
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
        help_text="The usage behavior to use when replacing the plan. Transfer to new subscription will transfer the usage from the old subscription to the new subscription, whereas keep_separate will reset the usage to 0 for the new subscription, while keeping the old usage on the old subscription and charging for that appropriately at the end of the month.",
    )
    turn_off_auto_renew = serializers.BooleanField(
        required=False, help_text="Turn off auto renew for the subscription"
    )
    end_date = serializers.DateTimeField(
        required=False, help_text="Change the end date for the subscription."
    )


class SubscriptionRecordUpdateSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = SubscriptionRecord
        fields = (
            "turn_off_auto_renew",
            "end_date",
            "metadata",
        )

    turn_off_auto_renew = serializers.BooleanField(
        required=False, help_text="Turn off auto renew for the subscription"
    )
    end_date = serializers.DateTimeField(
        required=False, help_text="Change the end date for the subscription."
    )
    metadata = serializers.JSONField(
        required=False, help_text="Update the metadata for the subscription."
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        now = now_utc()
        if "end_date" in attrs and attrs["end_date"] < now:
            raise serializers.ValidationError(
                "Cannot set end date to a date in the past."
            )
        return attrs

    def update(self, instance, validated_data):
        if "end_date" in validated_data:
            instance.end_date = validated_data["end_date"]
        if (
            "turn_off_auto_renew" in validated_data
            and validated_data["turn_off_auto_renew"]
        ):
            instance.auto_renew = False
        if "metadata" in validated_data:
            instance.metadata = validated_data["metadata"]
        instance.save()
        return instance


@extend_schema_serializer(exclude_fields=["switch_plan_version_id"])
class SubscriptionRecordSwitchPlanSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = SubscriptionRecord
        fields = (
            "switch_plan_version_id",
            "switch_plan_id",
            "invoicing_behavior",
            "usage_behavior",
            "component_fixed_charges_initial_units",
        )

    switch_plan_id = SlugRelatedFieldWithOrganization(
        slug_field="plan_id",
        read_only=False,
        source="plan",
        queryset=Plan.objects.all(),
        write_only=True,
        required=False,
        help_text="The new plan to switch to.",
    )
    switch_plan_version_id = SlugRelatedFieldWithOrganization(
        slug_field="version_id",
        read_only=False,
        source="plan_version",
        queryset=PlanVersion.plan_versions.all(),
        write_only=True,
        required=False,
        help_text="The new plan version to switch to.",
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
        help_text="The usage behavior to use when replacing the plan. Transfer to new subscription will transfer the usage from the old subscription to the new subscription, whereas keep_separate will reset the usage to 0 for the new subscription, while keeping the old usage on the old subscription and charging for that appropriately at the end of the month.",
    )
    component_fixed_charges_initial_units = ComponentsFixedChargeInitialValueSerializer(
        many=True,
        required=False,
        help_text="The initial units for the plan components' prepaid fixed charges. In the context of swithciong plans, this is only required if the new plan has a component the old plan did not have, that has a prepaid charge, that deos not have a default.",
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        # ensure either plan or plan_version is set
        if "plan" not in attrs and "plan_version" not in attrs:
            raise serializers.ValidationError(
                "Must specify either plan or plan_version."
            )
        return attrs


class AddOnSubscriptionRecordUpdateSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = SubscriptionRecord
        fields = (
            "invoicing_behavior",
            "turn_off_auto_renew",
            "end_date",
            "quantity",
            "metadata",
        )

    quantity = serializers.IntegerField(
        required=False,
        help_text="Change the quantity of the susbcription to be this number.",
    )
    invoicing_behavior = serializers.ChoiceField(
        choices=INVOICING_BEHAVIOR.choices,
        default=INVOICING_BEHAVIOR.INVOICE_NOW,
        required=False,
        help_text="The invoicing behavior to use when changing the quantity. Invoice now will recalculate the amount due immediately, whereas add_to_next_invoice will wait until the end of the subscription to do the calculation.",
    )
    turn_off_auto_renew = serializers.BooleanField(
        required=False, help_text="Turn off auto renew for the addon"
    )
    end_date = serializers.DateTimeField(
        required=False, help_text="Change the end date for the addon."
    )
    metadata = serializers.JSONField(
        required=False,
        help_text="Change the metadata for the addon. The current metadata will be replaced with this value.",
    )


class ListPlansFilterSerializer(serializers.Serializer):
    include_tags = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Filter to plans that have any of the tags in this list.",
    )
    include_tags_all = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Filter to plans that have all of the tags in this list.",
    )
    exclude_tags = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="Filter to plans that do not have any of the tags in this list.",
    )
    duration = serializers.ChoiceField(
        choices=PLAN_DURATION.choices,
        required=False,
        help_text="Filter to plans that have this duration.",
    )


class ListPlanVersionsFilterSerializer(serializers.Serializer):
    version_currency_code = SlugRelatedFieldWithOrganization(
        slug_field="code",
        queryset=PricingUnit.objects.all(),
        required=False,
        help_text="Filter to versions that have the currency specified by this currency code.",
        source="version_currency",
    )
    version_custom_type = serializers.ChoiceField(
        choices=PLAN_CUSTOM_TYPE.choices,
        required=False,
        default=PLAN_CUSTOM_TYPE.ALL,
        help_text="Filter to versions that have this custom type. If you choose custom_only, you will only see versions that have target customers. If you choose public_only, you will only see versions that do not have target customers.",
    )
    version_status = serializers.MultipleChoiceField(
        choices=SUBSCRIPTION_STATUS.choices,
        default={
            SUBSCRIPTION_STATUS.ACTIVE,
            SUBSCRIPTION_STATUS.ENDED,
            SUBSCRIPTION_STATUS.NOT_STARTED,
        },
        help_text="Filter to versions that have this status. Ended means it has an active_to date in the past. Not started means it has an active_from date in the future or null.",
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not attrs.get("version_status"):
            attrs["version_status"] = {
                SUBSCRIPTION_STATUS.ACTIVE,
                SUBSCRIPTION_STATUS.ENDED,
                SUBSCRIPTION_STATUS.NOT_STARTED,
            }
        return attrs


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
        queryset=Plan.objects.filter(is_addon=False),
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
        queryset=Plan.objects.filter(is_addon=False),
        required=False,
        help_text="Filter to a specific plan. If not specified, all plans will be included in the cancellation request.",
    )


class SubscriptionRecordCancelSerializer(serializers.Serializer):
    flat_fee_behavior = serializers.ChoiceField(
        choices=FLAT_FEE_BEHAVIOR.choices,
        allow_null=True,
        required=False,
        default=None,
        help_text="When canceling a subscription, the behavior used to calculate the flat fee. If null or not provided, the charge's default behavior will be used according to the subscription's start and end dates. If charge_full, the full flat fee will be charged, regardless of the duration of the subscription. If refund, the flat fee will not be charged. If charge_prorated, the prorated flat fee will be charged.",
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
    status = serializers.MultipleChoiceField(
        choices=SUBSCRIPTION_STATUS.choices,
        required=False,
        default=[SUBSCRIPTION_STATUS.ACTIVE],
        help_text="Filter to a specific set of subscription statuses. Defaults to active.",
    )
    plan_id = SlugRelatedFieldWithOrganization(
        slug_field="plan_id",
        source="billing_plan.plan",
        queryset=Plan.objects.filter(is_addon=False),
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


class AddOnSubscriptionRecordFilterSerializer(serializers.Serializer):
    attached_customer_id = SlugRelatedFieldWithOrganization(
        slug_field="customer_id",
        queryset=Customer.objects.all(),
        required=True,
        help_text="Filter to a specific customer.",
    )
    attached_plan_id = SlugRelatedFieldWithOrganization(
        slug_field="plan_id",
        queryset=Plan.objects.filter(is_addon=False),
        required=True,
        help_text="Filter to a specific plan.",
    )
    attached_subscription_filters = SubscriptionCategoricalFilterSerializer(
        many=True,
        required=False,
        help_text="Filter to a specific set of subscription filters. If your billing model only allows for one subscription per customer, you very likely do not need this field. Must be formatted as a JSON-encoded + stringified list of dictionaries, where each dictionary has a key of 'property_name' and a key of 'value'.",
    )
    addon_id = SlugRelatedFieldWithOrganization(
        slug_field="plan_id",
        queryset=Plan.addons.all(),
        required=True,
        help_text="Filter to a specific addon.",
    )


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


class CreditDrawdownSerializer(TimezoneFieldMixin, serializers.ModelSerializer):
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
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
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
    amount_paid_currency = PricingUnitSerializer(allow_null=True)
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
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
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


class CustomerBalanceAdjustmentUpdateSerializer(
    TimezoneFieldMixin, serializers.ModelSerializer
):
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
        if instance.status != CUSTOMER_BALANCE_ADJUSTMENT_STATUS.ACTIVE:
            raise serializers.ValidationError("Only active credits can be updated")
        instance.description = validated_data.get("description", instance.description)
        new_expires_at = validated_data.get("expires_at")
        now = now_utc()
        if new_expires_at and new_expires_at < now:
            raise serializers.ValidationError("Expiration date must be in the future")
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


class UsageAlertSerializer(TimezoneFieldMixin, serializers.ModelSerializer):
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
    metric = MetricSerializer()
    plan_version = LightweightPlanVersionSerializer()


class AddOnVersionSerializer(
    ConvertEmptyStringToNullMixin, TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = PlanVersion
        fields = (
            "recurring_charges",
            "components",
            "features",
            "status",
            "currency",
            "active_instances",
            "invoice_when",
            "billing_frequency",
            "addon_type",
        )
        extra_kwargs = {
            "recurring_charges": {"required": True, "read_only": True},
            "components": {"required": True, "read_only": True},
            "features": {"required": True, "read_only": True},
            "status": {"required": True, "read_only": True},
            "currency": {"required": True, "read_only": True},
            "active_instances": {"required": True, "read_only": True},
            "invoice_when": {"required": True, "read_only": True},
            "billing_frequency": {"required": True, "read_only": True},
            "addon_type": {"required": True, "read_only": True},
        }

    recurring_charges = RecurringChargeSerializer(many=True)
    components = PlanComponentSerializer(many=True, source="plan_components")
    features = FeatureSerializer(many=True)
    currency = PricingUnitSerializer(
        help_text="Currency of the plan. Can only be null if the flat fee is 0 and all components are of type free.",
    )
    active_instances = serializers.SerializerMethodField(
        help_text="The number of active instances of this version of the add-on plan."
    )
    invoice_when = serializers.SerializerMethodField()
    billing_frequency = serializers.SerializerMethodField()
    addon_type = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    def get_status(
        self, obj
    ) -> serializers.ChoiceField(choices=PLAN_VERSION_STATUS.choices):
        return obj.get_status()

    def get_invoice_when(
        self, obj
    ) -> serializers.ChoiceField(
        choices=AddOnSpecification.FlatFeeInvoicingBehaviorOnAttach.labels
    ):
        return obj.addon_spec.get_flat_fee_invoicing_behavior_on_attach_display()

    def get_addon_type(self, obj) -> Literal["usage_based", "flat"]:
        if obj.plan_components.all().count() > 0:
            return "usage_based"
        return "flat"

    def get_billing_frequency(
        self, obj
    ) -> serializers.ChoiceField(choices=AddOnSpecification.BillingFrequency.labels):
        return obj.addon_spec.get_billing_frequency_display()

    def get_active_instances(self, obj) -> int:
        return obj.subscription_records.active().count()


@extend_schema_serializer(
    deprecate_fields=[
        "flat_rate",
        "components",
        "features",
        "currency",
        "active_instances",
        "invoice_when",
        "billing_frequency",
        "addon_type",
    ]
)
class AddOnSerializer(TimezoneFieldMixin, serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = (
            "addon_id",
            "addon_name",
            "addon_description",
            "versions",
            "flat_rate",
            "components",
            "features",
            "currency",
            "active_instances",
            "invoice_when",
            "billing_frequency",
            "addon_type",
        )
        extra_kwargs = {
            "addon_name": {"required": True, "read_only": True},
            "addon_id": {"required": True, "read_only": True},
            "addon_description": {"required": True, "read_only": True},
            "versions": {"required": True, "read_only": True},
            "flat_rate": {"required": True, "read_only": True},
            "components": {"required": True, "read_only": True},
            "features": {"required": True, "read_only": True},
            "currency": {"required": True, "allow_null": True, "read_only": True},
            "active_instances": {"required": True, "read_only": True},
            "invoice_when": {"required": True, "read_only": True},
            "billing_frequency": {"required": True, "read_only": True},
            "addon_type": {"required": True, "read_only": True},
        }

    addon_id = AddOnUUIDField(
        source="plan_id",
        help_text="The ID of the add-on plan.",
    )
    addon_name = serializers.CharField(
        help_text="The name of the add-on plan.",
        source="plan_name",
    )
    addon_description = serializers.CharField(
        help_text="The description of the add-on plan.",
        source="plan_description",
    )
    flat_rate = serializers.SerializerMethodField()
    components = serializers.SerializerMethodField()
    features = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    active_instances = serializers.SerializerMethodField(
        help_text="The number of active instances of the add-on plan."
    )
    invoice_when = serializers.SerializerMethodField()
    billing_frequency = serializers.SerializerMethodField()
    addon_type = serializers.SerializerMethodField()
    versions = AddOnVersionSerializer(many=True, help_text="This addon's versions.")

    def get_components(self, obj) -> PlanComponentSerializer(many=True):
        version = obj.versions.first()
        return PlanComponentSerializer(version.plan_components.all(), many=True).data

    def get_features(self, obj) -> FeatureSerializer(many=True):
        version = obj.versions.first()
        return FeatureSerializer(version.features.all(), many=True).data

    def get_currency(self, obj) -> PricingUnitSerializer:
        version = obj.versions.first()
        return PricingUnitSerializer(version.currency).data

    def get_flat_rate(
        self, obj
    ) -> serializers.DecimalField(decimal_places=10, max_digits=20, min_value=0,):
        version = obj.versions.first()
        return sum(x.amount for x in version.recurring_charges.all())

    def get_invoice_when(
        self, obj
    ) -> serializers.ChoiceField(
        choices=AddOnSpecification.FlatFeeInvoicingBehaviorOnAttach.labels
    ):
        return obj.addon_spec.get_flat_fee_invoicing_behavior_on_attach_display()

    def get_addon_type(self, obj) -> Literal["usage_based", "flat"]:
        version = obj.versions.first()
        if version.plan_components.all().count() > 0:
            return "usage_based"
        return "flat"

    def get_billing_frequency(
        self, obj
    ) -> serializers.ChoiceField(choices=AddOnSpecification.BillingFrequency.labels):
        version = obj.versions.first()
        return version.get_billing_frequency_display()

    def get_active_instances(self, obj) -> int:
        return sum(x.active_subscriptions for x in obj.active_subs_by_version())


class AddOnSubscriptionRecordSerializer(
    TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = SubscriptionRecord
        fields = (
            "addon_subscription_id",
            "customer",
            "addon",
            "start_date",
            "end_date",
            "parent",
            "fully_billed",
            "auto_renew",
            "metadata",
        )
        extra_kwargs = {
            "addon_subscription_id": {"read_only": True, "required": True},
            "customer": {"read_only": True, "required": True},
            "addon": {"read_only": True, "required": True},
            "start_date": {"read_only": True, "required": True},
            "end_date": {"read_only": True, "required": True},
            "parent": {"read_only": True, "required": True},
            "fully_billed": {"read_only": True, "required": True},
            "auto_renew": {"read_only": True, "required": True},
            "metadata": {"read_only": True, "required": True},
        }

    addon_subscription_id = AddOnSubscriptionUUIDField(
        source="subscription_record_id",
    )
    customer = LightweightCustomerSerializer()
    addon = LightweightAddOnSerializer(source="billing_plan.plan")
    parent = LightweightSubscriptionRecordSerializer()
    fully_billed = serializers.SerializerMethodField()

    def get_fully_billed(self, obj) -> bool:
        return all(obj.billing_records.values_list("fully_billed", flat=True))


@extend_schema_serializer(exclude_fields=["addon_version_id"])
class AddOnSubscriptionRecordCreateSerializer(
    TimezoneFieldMixin, serializers.ModelSerializer
):
    class Meta:
        model = SubscriptionRecord
        fields = (
            "addon_id",
            "addon_version_id",
            "quantity",
            "metadata",
        )
        extra_kwargs = {
            "addon_version_id": {"required": False, "write_only": True},
            "addon_id": {"required": False, "write_only": True},
            "quantity": {"required": False, "write_only": True},
            "metadata": {"required": False, "write_only": True},
        }

    addon_id = SlugRelatedFieldWithOrganization(
        slug_field="plan_id",
        queryset=Plan.addons.all(),
        required=False,
        help_text="The add-on to be applied to the subscription. ",
        source="addon",
    )
    addon_version_id = SlugRelatedFieldWithOrganization(
        slug_field="version_id",
        queryset=PlanVersion.addon_versions.all(),
        required=False,
        help_text="The add-on to be applied to the subscription. You can use either this field or addon_id, but not both.",
        source="addon_version",
    )
    quantity = serializers.IntegerField(
        default=1,
        min_value=1,
        help_text="The quantity of the add-on to be applied to the subscription. Flat fees of add-ons will be multiplied by this quantity. Usage-based components of add-ons will be unaffected by the quantity.",
    )
    metadata = serializers.JSONField(
        required=False,
        help_text="A JSON object containing additional information about the add-on subscription. This will be returned in the response when you retrieve the add-on subscription.",
    )

    def validate(self, data):
        data = super().validate(data)
        plan_id_present = data.get("addon") is not None
        version_id_present = data.get("addon_version") is not None
        if plan_id_present == version_id_present:  # xor check
            raise serializers.ValidationError(
                "You must specify exactly one of addon_id or addon_version_id"
            )
        data["customer"] = self.context["customer"]
        if plan_id_present:
            data["addon_version"] = data.pop("addon").get_version_for_customer(
                data["customer"]
            )
            if data["addon_version"] is None:
                raise serializers.ValidationError(
                    "Unable to find a singular addon version that matches the addon_id. Please specify an addon_version_id instead."
                )

        data["attach_to_subscription_record"] = self.context[
            "attach_to_subscription_record"
        ]
        metrics_in_addon = {
            pc.billable_metric for pc in data["addon_version"].plan_components.all()
        }
        metrics_in_attach_sr = {
            pc.billable_metric
            for pc in data[
                "attach_to_subscription_record"
            ].billing_plan.plan_components.all()
        }
        intersection = metrics_in_addon & metrics_in_attach_sr
        if len(intersection) > 0:
            raise ValidationError(
                f"The add-on and the subscription to which it is being attached both contain the following metrics: {', '.join([x.metric_id for x in intersection])}."
            )
        return data

    def create(self, validated_data):
        from metering_billing.models import SubscriptionRecord

        sr = SubscriptionRecord.create_addon_subscription_record(
            parent_subscription_record=validated_data["attach_to_subscription_record"],
            addon_billing_plan=validated_data["addon_version"],
            quantity=validated_data["quantity"],
        )
        sr.metadata = validated_data.get("metadata", {})
        sr.save()
        return sr
