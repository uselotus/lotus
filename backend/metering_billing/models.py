import datetime
import itertools
import json
import logging
import math
import uuid
from decimal import Decimal
from typing import Literal, Optional, TypedDict, Union

# import lotus_python
import pycountry
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import ArrayField
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxLengthValidator,
    MaxValueValidator,
    MinLengthValidator,
    MinValueValidator,
)
from django.db import connection, models
from django.db.models import Count, F, FloatField, Q, Sum
from django.db.models.constraints import CheckConstraint, UniqueConstraint
from django.db.models.functions import Cast, Coalesce
from django.utils.translation import gettext_lazy as _
from metering_billing.exceptions.exceptions import (
    ExternalConnectionFailure,
    NotEditable,
    OverlappingPlans,
    PrepaymentMissingUnits,
    SubscriptionAlreadyEnded,
)
from metering_billing.payment_processors import PAYMENT_PROCESSOR_MAP
from metering_billing.utils import (
    calculate_end_date,
    convert_to_date,
    convert_to_decimal,
    customer_uuid,
    dates_bwn_two_dts,
    event_uuid,
    now_plus_day,
    now_utc,
    product_uuid,
)
from metering_billing.utils.enums import (
    ACCOUNTS_RECEIVABLE_TRANSACTION_TYPES,
    ANALYSIS_KPI,
    CATEGORICAL_FILTER_OPERATORS,
    CHARGEABLE_ITEM_TYPE,
    CUSTOMER_BALANCE_ADJUSTMENT_STATUS,
    EVENT_TYPE,
    EXPERIMENT_STATUS,
    FLAT_FEE_BEHAVIOR,
    INVOICE_CHARGE_TIMING_TYPE,
    METRIC_AGGREGATION,
    METRIC_GRANULARITY,
    METRIC_STATUS,
    METRIC_TYPE,
    NUMERIC_FILTER_OPERATORS,
    PAYMENT_PROCESSORS,
    PLAN_DURATION,
    PLAN_VERSION_STATUS,
    PRICE_ADJUSTMENT_TYPE,
    PRODUCT_STATUS,
    SUPPORTED_CURRENCIES,
    SUPPORTED_CURRENCIES_VERSION,
    TAG_GROUP,
    TAX_PROVIDER,
    WEBHOOK_TRIGGER_EVENTS,
)
from metering_billing.webhooks import invoice_paid_webhook, usage_alert_webhook
from rest_framework_api_key.models import AbstractAPIKey
from simple_history.models import HistoricalRecords
from svix.api import ApplicationIn, EndpointIn, EndpointSecretRotateIn, EndpointUpdate
from svix.internal.openapi_client.models.http_error import HttpError
from svix.internal.openapi_client.models.http_validation_error import (
    HTTPValidationError,
)
from timezone_field import TimeZoneField

logger = logging.getLogger("django.server")
META = settings.META
SVIX_CONNECTOR = settings.SVIX_CONNECTOR
CUSTOMER_ID_NAMESPACE = settings.CUSTOMER_ID_NAMESPACE


class Team(models.Model):
    name = models.CharField(max_length=100, blank=False, null=False)
    team_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    crm_integration_allowed = models.BooleanField(default=False)
    # accounting_integration_allowed = models.BooleanField(default=False)
    __original_crm_integration_allowed = None

    def __init__(self, *args, **kwargs):
        super(Team, self).__init__(*args, **kwargs)
        self.__original_crm_integration_allowed = self.crm_integration_allowed

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        new = self._state.adding is True
        # self._state.adding represents whether creating new instance or updating
        if self.crm_integration_allowed is True and (
            self.__original_crm_integration_allowed is False or new
        ):
            for org in self.organizations.all():
                org.provision_crm_settings()
        super(Team, self).save(*args, **kwargs)
        self.__original_crm_integration_allowed = self.crm_integration_allowed


class Address(models.Model):
    organization = models.ForeignKey(
        "Organization", on_delete=models.CASCADE, related_name="addresses"
    )
    city = models.CharField(
        max_length=50, help_text="City, district, suburb, town, or village"
    )
    country = models.CharField(
        max_length=2,
        help_text="Two-letter country code (ISO 3166-1 alpha-2)",
        validators=[MinLengthValidator(2), MaxLengthValidator(2)],
        choices=list([(x.alpha_2, x.name) for x in pycountry.countries]),
    )
    line1 = models.TextField(
        max_length=100,
        help_text="Address line 1 (e.g., street, PO Box, or company name)",
    )
    line2 = models.TextField(
        help_text="Address line 2 (e.g., apartment, suite, unit, or building)",
        null=True,
    )
    postal_code = models.CharField(
        max_length=20,
        help_text="ZIP or postal code",
    )
    state = models.CharField(
        max_length=30,
        help_text="State, county, province, or region",
        null=True,
    )

    def __str__(self):
        return f"Address: {self.line1}, {self.city}, {self.state}, {self.postal_code}, {self.country}"


class TaxProviderListField(models.CharField):
    description = "List of Tax Provider choices"

    def __init__(self, *args, **kwargs):
        self.enum = TAX_PROVIDER
        # set the max length to 16.. no way we ever have more than 8 tax providers
        kwargs.setdefault("max_length", 16)
        super().__init__(*args, **kwargs)

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return []
        value = [
            int(x) for x in value.split(",") if x != ""
        ]  # Ensure that all values in the list are valid tax provider choices
        choices_set = set(dict(self.enum.choices).keys())
        for val in value:
            if val not in choices_set:
                raise ValidationError(f"{val} is not a valid tax provider choice.")

        return value

    def to_python(self, value):
        if isinstance(value, list):
            return value
        elif value is None:
            return []
        else:
            return [int(val) for val in value.split(",")]

    def get_prep_value(self, value):
        if value is None or value == []:
            return ""
        else:
            if all(isinstance(v, int) for v in value):
                return ",".join(str(val) for val in value)
            else:
                enum_dict = dict(self.enum.choices)
                reverse_enum_dict = {v: k for k, v in enum_dict.items()}
                int_list = [str(reverse_enum_dict[val]) for val in value]
                return ",".join(int_list)

    def get_choices(self, include_blank=True, blank_choice=None, limit_choices_to=None):
        return self.enum.choices

    def value_to_string(self, obj):
        value = self.value_from_object(obj)
        pv = self.get_prep_value(value)
        return pv


class Organization(models.Model):
    class OrganizationType(models.IntegerChoices):
        PRODUCTION = (1, "Production")
        DEVELOPMENT = (2, "Development")
        EXTERNAL_DEMO = (3, "Demo")
        INTERNAL_DEMO = (4, "Internal Demo")

    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, null=True, related_name="organizations"
    )
    organization_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    organization_name = models.CharField(max_length=100, blank=False, null=False)
    created = models.DateField(default=now_utc)
    organization_type = models.PositiveSmallIntegerField(
        choices=OrganizationType.choices, default=OrganizationType.DEVELOPMENT
    )
    properties = models.JSONField(default=dict, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)

    # BILLING RELATED FIELDS
    default_payment_provider = models.CharField(
        blank=True, choices=PAYMENT_PROCESSORS.choices, max_length=40, null=True
    )
    stripe_integration = models.ForeignKey(
        "StripeOrganizationIntegration",
        on_delete=models.SET_NULL,
        related_name="organizations",
        null=True,
        blank=True,
    )
    braintree_integration = models.ForeignKey(
        "BraintreeOrganizationIntegration",
        on_delete=models.SET_NULL,
        related_name="organizations",
        null=True,
        blank=True,
    )
    address = models.ForeignKey(
        "Address",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
        help_text="The primary origin address for the organization",
    )
    default_currency = models.ForeignKey(
        "PricingUnit",
        on_delete=models.SET_NULL,
        related_name="organizations",
        null=True,
        blank=True,
    )

    # TAX RELATED FIELDS
    tax_rate = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        validators=[
            MinValueValidator(Decimal(0)),
            MaxValueValidator(Decimal(999.9999)),
        ],
        help_text="Tax rate as percentage. For example, 10.5 for 10.5%",
        null=True,
    )
    tax_providers = TaxProviderListField(default=[TAX_PROVIDER.LOTUS])

    # TIMEZONE RELATED FIELDS
    timezone = TimeZoneField(default="UTC", use_pytz=True)
    __original_timezone = None

    # SUBSCRIPTION RELATED FIELDS
    subscription_filter_keys = ArrayField(
        models.TextField(),
        default=list,
        blank=True,
        help_text="Allowed subscription filter keys",
    )
    __original_subscription_filter_keys = None

    # PROVISIONING FIELDS
    webhooks_provisioned = models.BooleanField(default=False)
    currencies_provisioned = models.IntegerField(default=0)
    crm_settings_provisioned = models.BooleanField(default=False)

    # settings
    gen_cust_in_stripe_after_lotus = models.BooleanField(default=False)
    gen_cust_in_braintree_after_lotus = models.BooleanField(default=False)
    payment_grace_period = models.IntegerField(null=True, default=None)
    lotus_is_customer_source_for_salesforce = models.BooleanField(default=False)

    # HISTORY RELATED FIELDS
    history = HistoricalRecords()

    def __init__(self, *args, **kwargs):
        super(Organization, self).__init__(*args, **kwargs)
        self.__original_timezone = self.timezone
        self.__original_subscription_filter_keys = self.subscription_filter_keys

    class Meta:
        indexes = [
            models.Index(fields=["organization_name"]),
            models.Index(fields=["organization_type"]),
            models.Index(fields=["organization_id"]),
            models.Index(fields=["team"]),
        ]

    def __str__(self):
        return self.organization_name

    def save(self, *args, **kwargs):
        from metering_billing.aggregation.billable_metrics import METRIC_HANDLER_MAP

        new = self._state.adding is True
        # self._state.adding represents whether creating new instance or updating
        if self.timezone != self.__original_timezone and not new:
            num_updated = self.customers.filter(timezone_set=False).update(
                timezone=self.timezone
            )
            if num_updated > 0:
                customer_ids = self.customers.filter(timezone_set=False).values_list(
                    "id", flat=True
                )
                customer_cache_keys = [f"tz_customer_{id}" for id in customer_ids]
                cache.delete_many(customer_cache_keys)
        if self.team is None:
            self.team = Team.objects.create(name=self.organization_name)
        if self.subscription_filter_keys is None:
            self.subscription_filter_keys = []
        self.subscription_filter_keys = sorted(
            list(
                set(self.subscription_filter_keys).union(
                    set(self.__original_subscription_filter_keys)
                )
            )
        )
        super(Organization, self).save(*args, **kwargs)
        if self.subscription_filter_keys != self.__original_subscription_filter_keys:
            for metric in self.metrics.all():
                METRIC_HANDLER_MAP[metric.metric_type].create_continuous_aggregate(
                    metric, refresh=True
                )
        self.__original_timezone = self.timezone
        self.__original_subscription_filter_keys = self.subscription_filter_keys
        if new:
            self.provision_currencies()
        if not self.default_currency:
            self.default_currency = PricingUnit.objects.get(
                organization=self, code="USD"
            )
            self.save()
        if not self.webhooks_provisioned:
            self.provision_webhooks()

    def get_tax_provider_values(self):
        return self.tax_providers

    def get_readable_tax_providers(self):
        choices_dict = dict(TAX_PROVIDER.choices)
        return [choices_dict.get(val) for val in self.tax_providers]

    def get_address(self) -> Address:
        if self.default_payment_provider == PAYMENT_PROCESSORS.STRIPE:
            return PAYMENT_PROCESSOR_MAP[
                PAYMENT_PROCESSORS.STRIPE
            ].get_organization_address(self)
        elif self.default_payment_provider == PAYMENT_PROCESSORS.BRAINTREE:
            return PAYMENT_PROCESSOR_MAP[
                PAYMENT_PROCESSORS.BRAINTREE
            ].get_organization_address(self)
        else:
            return self.address

    def provision_webhooks(self):
        if SVIX_CONNECTOR is not None and not self.webhooks_provisioned:
            logger.info("provisioning webhooks")
            svix = SVIX_CONNECTOR
            svix.application.create(
                ApplicationIn(uid=self.organization_id.hex, name=self.organization_name)
            )
            self.webhooks_provisioned = True
            self.save()

    def provision_currencies(self):
        if SUPPORTED_CURRENCIES_VERSION != self.currencies_provisioned:
            for name, code, symbol in SUPPORTED_CURRENCIES:
                PricingUnit.objects.get_or_create(
                    organization=self, code=code, name=name, symbol=symbol, custom=False
                )
            PricingUnit.objects.filter(
                ~Q(code__in=[code for _, code, _ in SUPPORTED_CURRENCIES]),
                custom=False,
                organization=self,
            ).delete()
            self.currencies_provisioned = SUPPORTED_CURRENCIES_VERSION
            self.save()


class WebhookEndpointManager(models.Manager):
    def create_with_triggers(self, *args, **kwargs):
        triggers = kwargs.pop("triggers", [])
        wh_endpoint = self.model(**kwargs)
        wh_endpoint.save(triggers=triggers)
        return wh_endpoint


class WebhookEndpoint(models.Model):
    webhook_endpoint_id = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="webhook_endpoints"
    )
    name = models.CharField(max_length=100, blank=True, null=True)
    webhook_url = models.CharField(max_length=100)
    webhook_secret = models.UUIDField(default=uuid.uuid4, editable=False)

    objects = WebhookEndpointManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "webhook_url"], name="unique_webhook_url"
            )
        ]
        indexes = [
            models.Index(
                fields=["organization", "webhook_endpoint_id"]
            ),  # for single lookup
        ]

    def save(self, *args, **kwargs):
        new = self._state.adding is True
        triggers = kwargs.pop("triggers", [])
        super(WebhookEndpoint, self).save(*args, **kwargs)
        if SVIX_CONNECTOR is not None:
            try:
                svix = SVIX_CONNECTOR
                if new:
                    endpoint_create_dict = {
                        "uid": self.webhook_endpoint_id.hex,
                        "description": self.name,
                        "url": self.webhook_url,
                        "version": 1,
                        "secret": "whsec_" + self.webhook_secret.hex,
                    }
                    if len(triggers) > 0:
                        endpoint_create_dict["filter_types"] = []
                        for trigger in triggers:
                            endpoint_create_dict["filter_types"].append(
                                trigger.trigger_name
                            )
                            trigger.webhook_endpoint = self
                            trigger.save()
                    svix_endpoint = svix.endpoint.create(
                        self.organization.organization_id.hex,
                        EndpointIn(**endpoint_create_dict),
                    )
                else:
                    triggers = self.triggers.all().values_list(
                        "trigger_name", flat=True
                    )
                    svix_endpoint = svix.endpoint.get(
                        self.organization.organization_id.hex,
                        self.webhook_endpoint_id.hex,
                    )

                    svix_endpoint = svix_endpoint.__dict__
                    svix_update_dict = {}
                    svix_update_dict["uid"] = self.webhook_endpoint_id.hex
                    svix_update_dict["description"] = self.name
                    svix_update_dict["url"] = self.webhook_url

                    # triggers
                    svix_triggers = svix_endpoint.get("filter_types") or []
                    version = svix_endpoint.get("version")
                    if set(triggers) != set(svix_triggers):
                        version += 1
                    svix_update_dict["filter_types"] = list(triggers)
                    svix_update_dict["version"] = version
                    svix.endpoint.update(
                        self.organization.organization_id.hex,
                        self.webhook_endpoint_id.hex,
                        EndpointUpdate(**svix_update_dict),
                    )

                    current_endpoint_secret = svix.endpoint.get_secret(
                        self.organization.organization_id.hex,
                        self.webhook_endpoint_id.hex,
                    )
                    if current_endpoint_secret.key != self.webhook_secret.hex:
                        svix.endpoint.rotate_secret(
                            self.organization.organization_id.hex,
                            self.webhook_endpoint_id.hex,
                            EndpointSecretRotateIn(key=self.webhook_secret.hex),
                        )
            except (HttpError, HTTPValidationError) as e:
                list_response_application_out = svix.application.list()
                dt = list_response_application_out.data
                lst = [x for x in dt if x.uid == self.organization.organization_id.hex]
                try:
                    svix_app = lst[0]
                except IndexError:
                    svix_app = None
                if svix_app:
                    list_response_endpoint_out = svix.endpoint.list(svix_app.id).data
                else:
                    list_response_endpoint_out = []

                dictionary = {
                    "error": e,
                    "organization_id": self.organization.organization_id.hex,
                    "webhook_endpoint_id": self.webhook_endpoint_id.hex,
                    "svix_app": svix_app,
                    "endpoint data": list_response_endpoint_out,
                }
                self.delete()

                raise ExternalConnectionFailure(
                    "Webhooks service failed to connect. Did not provision webhook endpoint. Error: {}".format(
                        dictionary
                    )
                )


class WebhookTrigger(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="webhook_triggers",
        null=True,
    )
    webhook_endpoint = models.ForeignKey(
        WebhookEndpoint, on_delete=models.CASCADE, related_name="triggers"
    )
    trigger_name = models.CharField(
        choices=WEBHOOK_TRIGGER_EVENTS.choices, max_length=40
    )

    class Meta:
        indexes = [
            models.Index(
                fields=["organization", "webhook_endpoint", "trigger_name"],
                name="unique_webhook_trigger",
            )
        ]


class User(AbstractUser):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="users",
    )
    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, null=True, related_name="users"
    )
    email = models.EmailField(unique=True)
    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        if not self.team and self.organization:
            self.team = self.organization.team
        super(User, self).save(*args, **kwargs)


class Product(models.Model):
    """
    This model is used to store the products that are available to be purchased.
    """

    name = models.CharField(max_length=100, blank=False)
    description = models.TextField(null=True, blank=True)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="products"
    )
    product_id = models.SlugField(default=product_uuid, max_length=100, unique=True)
    status = models.CharField(choices=PRODUCT_STATUS.choices, max_length=40)
    history = HistoricalRecords()

    class Meta:
        unique_together = ("organization", "product_id")

    def __str__(self):
        return f"{self.name}"


class BaseCustomerManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted__isnull=True)


class DeletedCustomerManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted__isnull=False)


class Customer(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="customers"
    )
    customer_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="The display name of the customer",
        null=True,
    )
    email = models.EmailField(
        max_length=100,
        help_text="The primary email address of the customer, must be the same as the email address used to create the customer in the payment provider",
        null=True,
    )
    customer_id = models.TextField(
        default=customer_uuid,
        help_text="The id provided when creating the customer, we suggest matching with your internal customer id in your backend",
        null=True,
    )
    uuidv5_customer_id = models.UUIDField(
        help_text="The v5 UUID generated from the customer_id. This is used for efficient lookups in the database, specifically for the Events table",
        null=True,
    )
    properties = models.JSONField(
        default=dict, null=True, help_text="Extra metadata for the customer"
    )
    deleted = models.DateTimeField(
        null=True, help_text="The date the customer was deleted"
    )

    # BILLING RELATED FIELDS
    default_currency = models.ForeignKey(
        "PricingUnit",
        on_delete=models.SET_NULL,
        related_name="customers",
        null=True,
        blank=True,
        help_text="The currency the customer will be invoiced in",
    )
    shipping_address = models.ForeignKey(
        "Address",
        on_delete=models.SET_NULL,
        related_name="shipping_customers",
        null=True,
        blank=True,
        help_text="The shipping address for the customer",
    )
    billing_address = models.ForeignKey(
        "Address",
        on_delete=models.SET_NULL,
        related_name="billing_customers",
        null=True,
        blank=True,
        help_text="The billing address for the customer",
    )

    # TAX RELATED FIELDS
    tax_providers = TaxProviderListField(default=[])
    tax_rate = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        validators=[
            MinValueValidator(Decimal(0)),
            MaxValueValidator(Decimal(999.9999)),
        ],
        help_text="Tax rate as percentage. For example, 10.5 for 10.5%",
        null=True,
    )

    # TIMEZONE FIELDS
    timezone = TimeZoneField(default="UTC", use_pytz=True)
    timezone_set = models.BooleanField(default=False)

    # PAYMENT PROCESSOR FIELDS
    payment_provider = models.CharField(
        blank=True, choices=PAYMENT_PROCESSORS.choices, max_length=40, null=True
    )
    stripe_integration = models.ForeignKey(
        "StripeCustomerIntegration",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customers",
    )
    braintree_integration = models.ForeignKey(
        "BraintreeCustomerIntegration",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customers",
    )
    salesforce_integration = models.OneToOneField(
        "UnifiedCRMCustomerIntegration",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer",
    )

    # HISTORY FIELDS
    created = models.DateTimeField(default=now_utc)
    history = HistoricalRecords()
    objects = BaseCustomerManager()
    deleted_objects = DeletedCustomerManager()

    class Meta:
        constraints = [
            UniqueConstraint(fields=["organization", "email"], name="unique_email"),
            UniqueConstraint(
                fields=["organization", "customer_id"], name="unique_customer_id"
            ),
        ]

    def __str__(self) -> str:
        return str(self.customer_name) + " " + str(self.customer_id)

    def save(self, *args, **kwargs):
        if not self.default_currency:
            try:
                self.default_currency = (
                    self.organization.default_currency
                    or PricingUnit.objects.get(
                        code="USD", organization=self.organization
                    )
                )
            except PricingUnit.DoesNotExist:
                self.default_currency = None
        super(Customer, self).save(*args, **kwargs)

    def get_active_subscription_records(self):
        active_subscription_records = self.subscription_records.active().filter(
            fully_billed=False,
        )
        return active_subscription_records

    def get_tax_provider_values(self):
        return self.tax_providers

    def get_readable_tax_providers(self):
        choices_dict = dict(TAX_PROVIDER.choices)
        return [choices_dict.get(val) for val in self.tax_providers]

    def get_usage_and_revenue(self):
        customer_subscriptions = (
            SubscriptionRecord.objects.active()
            .filter(
                customer=self,
                organization=self.organization,
            )
            .prefetch_related("billing_plan__plan_components")
            .prefetch_related("billing_plan__plan_components__billable_metric")
            .select_related("billing_plan")
        )
        subscription_usages = {"subscriptions": [], "sub_objects": []}
        for subscription in customer_subscriptions:
            sub_dict = subscription.get_usage_and_revenue()
            del sub_dict["components"]
            sub_dict["billing_plan_name"] = subscription.billing_plan.plan.plan_name
            subscription_usages["subscriptions"].append(sub_dict)
            subscription_usages["sub_objects"].append(subscription)

        return subscription_usages

    def get_active_sub_drafts_revenue(self):
        from metering_billing.invoice import generate_invoice

        total = 0
        sub_records = self.get_active_subscription_records()
        if sub_records is not None and len(sub_records) > 0:
            invs = generate_invoice(
                sub_records,
                draft=True,
                charge_next_plan=True,
            )
            total += sum([inv.amount for inv in invs])
            for inv in invs:
                inv.delete()
        return total

    def get_currency_balance(self, currency):
        now = now_utc()
        balance = self.customer_balance_adjustments.filter(
            Q(expires_at__gte=now) | Q(expires_at__isnull=True),
            effective_at__lte=now,
            amount_currency=currency,
        ).aggregate(balance=Sum("amount"))["balance"] or Decimal(0)
        return balance

    def get_outstanding_revenue(self):
        unpaid_invoice_amount_due = (
            self.invoices.filter(payment_status=Invoice.PaymentStatus.UNPAID)
            .aggregate(unpaid_inv_amount=Sum("amount"))
            .get("unpaid_inv_amount")
        )
        total_amount_due = unpaid_invoice_amount_due or 0
        return total_amount_due

    def get_billing_address(self) -> Address:
        if self.payment_provider == PAYMENT_PROCESSORS.STRIPE:
            return PAYMENT_PROCESSOR_MAP[
                PAYMENT_PROCESSORS.STRIPE
            ].get_customer_address(self, type="billing")
        elif self.payment_provider == PAYMENT_PROCESSORS.BRAINTREE:
            return PAYMENT_PROCESSOR_MAP[
                PAYMENT_PROCESSORS.BRAINTREE
            ].get_customer_address(self, type="billing")
        else:
            return self.billing_address

    def get_shipping_address(self) -> Address:
        if self.payment_provider == PAYMENT_PROCESSORS.STRIPE:
            return PAYMENT_PROCESSOR_MAP[
                PAYMENT_PROCESSORS.STRIPE
            ].get_customer_address(self, type="shipping")
        elif self.payment_provider == PAYMENT_PROCESSORS.BRAINTREE:
            return PAYMENT_PROCESSOR_MAP[
                PAYMENT_PROCESSORS.BRAINTREE
            ].get_customer_address(self, type="billing")
        else:
            return self.shipping_address


class CustomerBalanceAdjustment(models.Model):
    """
    This model is used to store the customer balance adjustments.
    """

    adjustment_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="+", null=True
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="customer_balance_adjustments"
    )
    amount = models.DecimalField(decimal_places=10, max_digits=20)
    pricing_unit = models.ForeignKey(
        "PricingUnit",
        on_delete=models.SET_NULL,
        related_name="adjustments",
        null=True,
        blank=True,
    )
    description = models.TextField(null=True, blank=True)
    created = models.DateTimeField(default=now_utc)
    effective_at = models.DateTimeField(default=now_utc)
    expires_at = models.DateTimeField(null=True, blank=True)
    parent_adjustment = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="drawdowns",
    )
    amount_paid = models.DecimalField(
        decimal_places=10, max_digits=20, default=Decimal(0)
    )
    amount_paid_currency = models.ForeignKey(
        "PricingUnit",
        on_delete=models.SET_NULL,
        related_name="paid_adjustments",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=CUSTOMER_BALANCE_ADJUSTMENT_STATUS.choices,
        default=CUSTOMER_BALANCE_ADJUSTMENT_STATUS.ACTIVE,
    )

    def __str__(self):
        return f"{self.customer.customer_name} {self.amount} {self.created}"

    class Meta:
        ordering = ["-created"]
        unique_together = ("customer", "created")
        indexes = [
            models.Index(
                fields=["organization", "adjustment_id"]
            ),  # for lookup for single
            models.Index(
                fields=["organization", "customer", "pricing_unit", "-expires_at"]
            ),  # for lookup for drawdowns
            models.Index(fields=["status", "expires_at"]),  # for lookup for expired
        ]

    def save(self, *args, **kwargs):
        new = self._state.adding is True
        if not new:
            orig = CustomerBalanceAdjustment.objects.get(pk=self.pk)
            if (
                orig.amount != self.amount
                or orig.pricing_unit != self.pricing_unit
                or orig.created != self.created
                or orig.effective_at != self.effective_at
                or orig.parent_adjustment != self.parent_adjustment
            ):
                raise NotEditable(
                    "Cannot update any fields in a balance adjustment other than status and description"
                )
            if self.expires_at is not None and now_utc() > self.expires_at:
                raise NotEditable("Cannot change the expiry date to the past")
        if self.amount < 0:
            assert (
                self.parent_adjustment is not None
            ), "If credit is negative, parent adjustment must be provided"
        if self.parent_adjustment:
            assert (
                self.parent_adjustment.amount > 0
            ), "Parent adjustment must be a credit adjustment"
            assert (
                self.parent_adjustment.customer == self.customer
            ), "Parent adjustment must be for the same customer"
            assert self.amount < 0, "Child adjustment must be a debit adjustment"
            assert (
                self.pricing_unit == self.parent_adjustment.pricing_unit
            ), "Child adjustment must be in the same currency as parent adjustment"
            assert self.parent_adjustment.get_remaining_balance() - self.amount >= 0, (
                "Child adjustment must be less than or equal to the remaining balance of "
                "the parent adjustment"
            )
        if not self.organization:
            self.organization = self.customer.organization
        if self.amount_paid is None or self.amount_paid == 0:
            self.amount_paid_currency = None
        if not self.pricing_unit:
            raise ValidationError("Pricing unit must be provided")
        super(CustomerBalanceAdjustment, self).save(*args, **kwargs)

    def get_remaining_balance(self):
        try:
            dd_aggregate = self.total_drawdowns
        except AttributeError:
            dd_aggregate = self.drawdowns.aggregate(drawdowns=Sum("amount"))[
                "drawdowns"
            ]
        drawdowns = dd_aggregate or 0
        return self.amount + drawdowns

    def zero_out(self, reason=None):
        if reason == "expired":
            fmt = self.expires_at.strftime("%Y-%m-%d %H:%M")
            description = f"Expiring remaining credit at {fmt} UTC"
        elif reason == "voided":
            fmt = now_utc().strftime("%Y-%m-%d %H:%M")
            description = f"Voiding remaining credit at {fmt} UTC"
        else:
            description = "Zeroing out remaining credit"
        remaining_balance = self.get_remaining_balance()
        if remaining_balance > 0:
            CustomerBalanceAdjustment.objects.create(
                organization=self.customer.organization,
                customer=self.customer,
                amount=-remaining_balance,
                pricing_unit=self.pricing_unit,
                parent_adjustment=self,
                description=description,
            )
        self.status = CUSTOMER_BALANCE_ADJUSTMENT_STATUS.INACTIVE
        self.save()

    @staticmethod
    def draw_down_amount(customer, amount, pricing_unit, description=""):
        now = now_utc()
        adjs = (
            CustomerBalanceAdjustment.objects.filter(
                Q(expires_at__gte=now) | Q(expires_at__isnull=True),
                organization=customer.organization,
                customer=customer,
                pricing_unit=pricing_unit,
                amount__gt=0,
                status=CUSTOMER_BALANCE_ADJUSTMENT_STATUS.ACTIVE,
            )
            .annotate(
                cost_basis=Cast(
                    Coalesce(F("amount_paid") / F("amount"), 0), FloatField()
                )
            )
            .order_by(
                F("expires_at").asc(nulls_last=True),
                F("cost_basis").desc(nulls_last=True),
            )
            .annotate(
                drawn_down_amount=Coalesce(
                    Sum("drawdowns__amount"), 0, output_field=models.DecimalField()
                )
            )
            .annotate(remaining_balance=F("amount") + F("drawn_down_amount"))
        )
        am = amount
        for adj in adjs:
            remaining_balance = adj.remaining_balance
            if remaining_balance <= 0:
                adj.status = CUSTOMER_BALANCE_ADJUSTMENT_STATUS.INACTIVE
                adj.save()
                continue
            drawdown_amount = min(am, remaining_balance)
            CustomerBalanceAdjustment.objects.create(
                organization=customer.organization,
                customer=customer,
                amount=-drawdown_amount,
                pricing_unit=adj.pricing_unit,
                parent_adjustment=adj,
                description=description,
            )
            if drawdown_amount == remaining_balance:
                adj.status = CUSTOMER_BALANCE_ADJUSTMENT_STATUS.INACTIVE
                adj.save()
            am -= drawdown_amount
            if am == 0:
                break
        return am

    @staticmethod
    def get_pricing_unit_balance(customer, pricing_unit):
        now = now_utc()
        adjs = (
            CustomerBalanceAdjustment.objects.filter(
                Q(expires_at__gte=now) | Q(expires_at__isnull=True),
                organization=customer.organization,
                customer=customer,
                pricing_unit=pricing_unit,
                amount__gt=0,
                status=CUSTOMER_BALANCE_ADJUSTMENT_STATUS.ACTIVE,
            )
            .prefetch_related("drawdowns")
            .annotate(
                drawn_down_amount=Coalesce(
                    Sum("drawdowns__amount"), 0, output_field=models.DecimalField()
                )
            )
            .annotate(remaining_balance=F("amount") - F("drawn_down_amount"))
            .aggregate(total_balance=Sum("remaining_balance"))["total_balance"]
        )
        total_balance = adjs or 0
        return total_balance


class IdempotenceCheck(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.SET_NULL, related_name="+", null=True, blank=True
    )
    time_created = models.DateTimeField(
        help_text="The time that the event occured, represented as a datetime in RFC3339 in the UTC timezome."
    )
    uuidv5_idempotency_id = models.UUIDField(primary_key=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "uuidv5_idempotency_id"],
                name="unique_hashed_idempotency_id_per_org_raw",
            )
        ]

    def __str__(self):
        return str(self.time_created)[:10] + "-" + str(self.idempotency_id)[:6]


class EventManager(models.Manager):
    def create(self, **kwargs):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT insert_metric(%s::integer, %s::text, %s::text, %s::timestamptz, %s::jsonb, %s::text)",
                [
                    kwargs.get("organization").id,
                    str(kwargs.get("cust_id")),
                    str(kwargs.get("event_name")),
                    kwargs.get("time_created"),
                    json.dumps(kwargs.get("properties", {})),
                    str(kwargs.get("idempotency_id")),
                ],
            )
            cursor.close()
            connection.commit()
        return self.model(**kwargs)


class Event(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.SET_NULL, related_name="+", null=True, blank=True
    )
    cust_id = models.TextField(blank=True)
    uuidv5_customer_id = models.UUIDField()
    event_name = models.TextField(
        help_text="String name of the event, corresponds to definition in metrics",
    )
    uuidv5_event_name = models.UUIDField()
    time_created = models.DateTimeField(
        help_text="The time that the event occured, represented as a datetime in RFC3339 in the UTC timezome."
    )
    properties = models.JSONField(
        default=dict,
        blank=True,
        help_text="Extra metadata on the event that can be filtered and queried on in the metrics. All key value pairs should have string keys and values can be either strings or numbers. Place subscription filters in this object to specify which subscription the event should be tracked under",
    )
    idempotency_id = models.TextField(
        default=event_uuid,
        help_text="A unique identifier for the specific event being passed in. Passing in a unique id allows Lotus to make sure no double counting occurs. We recommend using a UUID4. You can use the same idempotency_id again after 45 days.",
        primary_key=True,
    )
    uuidv5_idempotency_id = models.UUIDField()
    inserted_at = models.DateTimeField(default=now_utc)
    objects = EventManager()

    class Meta:
        managed = False
        db_table = "metering_billing_usageevent"

    def __str__(self):
        return (
            str(self.event_name)[:6]
            + "-"
            + str(self.cust_id)[:8]
            + "-"
            + str(self.time_created)[:10]
            + "-"
            + str(self.idempotency_id)[:6]
        )


class NumericFilter(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="numeric_filters",
        null=True,
    )
    property_name = models.CharField(max_length=100)
    operator = models.CharField(max_length=10, choices=NUMERIC_FILTER_OPERATORS.choices)
    comparison_value = models.FloatField()


class CategoricalFilter(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="categorical_filters",
        null=True,
    )
    property_name = models.CharField(max_length=100)
    operator = models.CharField(
        max_length=10, choices=CATEGORICAL_FILTER_OPERATORS.choices
    )
    comparison_value = models.JSONField()

    def __str__(self):
        return f"{self.property_name} {self.operator} {self.comparison_value}"


class Metric(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="metrics",
    )
    event_name = models.CharField(
        max_length=50, help_text="Name of the event that this metric is tracking."
    )
    metric_type = models.CharField(
        max_length=20,
        choices=METRIC_TYPE.choices,
        default=METRIC_TYPE.COUNTER,
        help_text="The type of metric that this is. Please refer to our documentation for an explanation of the different types.",
    )
    properties = models.JSONField(default=dict, blank=True, null=True)
    billable_metric_name = models.CharField(max_length=50, blank=True, null=True)
    metric_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPE.choices,
        blank=True,
        null=True,
        help_text="Used only for metrics of type 'gauge'. Please refer to our documentation for an explanation of the different types.",
    )
    # metric type specific
    usage_aggregation_type = models.CharField(
        max_length=10,
        choices=METRIC_AGGREGATION.choices,
        default=METRIC_AGGREGATION.COUNT,
        help_text="The type of aggregation that should be used for this metric. Please refer to our documentation for an explanation of the different types.",
    )
    billable_aggregation_type = models.CharField(
        max_length=10,
        choices=METRIC_AGGREGATION.choices,
        default=METRIC_AGGREGATION.SUM,
        blank=True,
        null=True,
    )
    property_name = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="The name of the property of the event that should be used for this metric. Doesn't apply if the metric is of type 'counter' with an aggregation of count.",
    )
    granularity = models.CharField(
        choices=METRIC_GRANULARITY.choices,
        default=METRIC_GRANULARITY.TOTAL,
        max_length=10,
        blank=True,
        null=True,
        help_text="The granularity of the metric. Only applies to metrics of type 'gauge' or 'rate'.",
    )
    proration = models.CharField(
        choices=METRIC_GRANULARITY.choices,
        default=None,
        max_length=10,
        blank=True,
        null=True,
        help_text="The proration of the metric. Only applies to metrics of type 'gauge'.",
    )
    is_cost_metric = models.BooleanField(
        default=False,
        help_text="Whether or not this metric is a cost metric (used to track costs to your business).",
    )
    custom_sql = models.TextField(
        blank=True,
        null=True,
        help_text="A custom SQL query that can be used to define the metric. Please refer to our documentation for more information.",
    )

    # filters
    numeric_filters = models.ManyToManyField(NumericFilter, blank=True)
    categorical_filters = models.ManyToManyField(CategoricalFilter, blank=True)

    # status
    status = models.CharField(
        choices=METRIC_STATUS.choices, max_length=40, default=METRIC_STATUS.ACTIVE
    )
    mat_views_provisioned = models.BooleanField(default=False)

    # records
    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "billable_metric_name"],
                condition=Q(status=METRIC_STATUS.ACTIVE),
                name="unique_org_billable_metric_name",
            ),
        ] + [
            models.UniqueConstraint(
                fields=sorted(
                    list(
                        {
                            "organization",
                            "billable_metric_name",  # nullable
                            "event_name",
                            "metric_type",
                            "usage_aggregation_type",
                            "billable_aggregation_type",  # nullable
                            "property_name",  # nullable
                            "granularity",  # nullable
                            "is_cost_metric",
                            "custom_sql",  # nullable
                        }
                        - {x for x in nullables}
                    )
                ),
                condition=Q(
                    **{f"{nullable}__in": [None, ""] for nullable in sorted(nullables)}
                )
                & Q(status=METRIC_STATUS.ACTIVE),
                name="uq_metric_w_null__"
                + "_".join(
                    [
                        "_".join([x[:2] for x in nullable.split("_")])
                        for nullable in sorted(nullables)
                    ]
                ),
            )
            for nullables in itertools.chain(
                *map(
                    lambda x: itertools.combinations(
                        [
                            "billable_metric_name",
                            "billable_aggregation_type",
                            "property_name",
                            "granularity",
                            "custom_sql",
                        ],
                        x,
                    ),
                    range(
                        0,
                        len(
                            [
                                "billable_metric_name",
                                "billable_aggregation_type",
                                "property_name",
                                "granularity",
                                "custom_sql",
                            ],
                        )
                        + 1,
                    ),
                )
            )
        ]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "is_cost_metric"]),
            models.Index(fields=["organization", "metric_id"]),
        ]

    def __str__(self):
        return self.billable_metric_name or ""

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def delete_materialized_views(self):
        from metering_billing.aggregation.billable_metrics import METRIC_HANDLER_MAP

        handler = METRIC_HANDLER_MAP[self.metric_type]
        handler.archive_metric(self)
        self.mat_views_provisioned = False
        self.save()

    def get_aggregation_type(self):
        return self.aggregation_type

    def get_billing_record_total_billable_usage(self, billing_record):
        from metering_billing.aggregation.billable_metrics import METRIC_HANDLER_MAP

        if self.status == METRIC_STATUS.ACTIVE and not self.mat_views_provisioned:
            self.provision_materialized_views()

        handler = METRIC_HANDLER_MAP[self.metric_type]
        usage = handler.get_billing_record_total_billable_usage(self, billing_record)

        return usage

    def get_billing_record_daily_billable_usage(self, billing_record):
        from metering_billing.aggregation.billable_metrics import METRIC_HANDLER_MAP

        if self.status == METRIC_STATUS.ACTIVE and not self.mat_views_provisioned:
            self.provision_materialized_views()

        handler = METRIC_HANDLER_MAP[self.metric_type]
        usage = handler.get_billing_record_daily_billable_usage(self, billing_record)

        return usage

    def get_billing_record_current_usage(self, billing_record):
        from metering_billing.aggregation.billable_metrics import METRIC_HANDLER_MAP

        if self.status == METRIC_STATUS.ACTIVE and not self.mat_views_provisioned:
            self.provision_materialized_views()

        handler = METRIC_HANDLER_MAP[self.metric_type]
        usage = handler.get_billing_record_current_usage(self, billing_record)

        return usage

    def get_daily_total_usage(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        customer: Optional[Customer] = None,
        top_n: Optional[int] = None,
    ) -> dict[Union[Customer, Literal["Other"]], dict[datetime.date, Decimal]]:
        from metering_billing.aggregation.billable_metrics import METRIC_HANDLER_MAP

        if self.status == METRIC_STATUS.ACTIVE and not self.mat_views_provisioned:
            self.provision_materialized_views()

        handler = METRIC_HANDLER_MAP[self.metric_type]
        usage = handler.get_daily_total_usage(
            self, start_date, end_date, customer, top_n
        )

        return usage

    def refresh_materialized_views(self):
        from metering_billing.aggregation.billable_metrics import METRIC_HANDLER_MAP

        handler = METRIC_HANDLER_MAP[self.metric_type]
        handler.create_continuous_aggregate(self, refresh=True)
        self.mat_views_provisioned = True
        self.save()

    def provision_materialized_views(self):
        from metering_billing.aggregation.billable_metrics import METRIC_HANDLER_MAP

        handler = METRIC_HANDLER_MAP[self.metric_type]
        handler.create_continuous_aggregate(self)
        self.mat_views_provisioned = True
        self.save()


class UsageRevenueSummary(TypedDict):
    revenue: Decimal
    usage_qty: Decimal


class PriceTier(models.Model):
    class PriceTierType(models.IntegerChoices):
        FLAT = (1, _("flat"))
        PER_UNIT = (2, _("per_unit"))
        FREE = (3, _("free"))

    class BatchRoundingType(models.IntegerChoices):
        ROUND_UP = (1, _("round_up"))
        ROUND_DOWN = (2, _("round_down"))
        ROUND_NEAREST = (3, _("round_nearest"))
        NO_ROUNDING = (4, _("no_rounding"))

    organization = models.ForeignKey(
        "Organization", on_delete=models.CASCADE, related_name="price_tiers", null=True
    )
    plan_component = models.ForeignKey(
        "PlanComponent",
        on_delete=models.CASCADE,
        related_name="tiers",
        null=True,
        blank=True,
    )
    type = models.PositiveSmallIntegerField(choices=PriceTierType.choices)
    range_start = models.DecimalField(
        max_digits=20, decimal_places=10, validators=[MinValueValidator(0)]
    )
    range_end = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    cost_per_batch = models.DecimalField(
        decimal_places=10,
        max_digits=20,
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
    )
    metric_units_per_batch = models.DecimalField(
        decimal_places=10,
        max_digits=20,
        blank=True,
        null=True,
        default=1.0,
        validators=[MinValueValidator(0)],
    )
    batch_rounding_type = models.PositiveSmallIntegerField(
        choices=BatchRoundingType.choices,
        blank=True,
        null=True,
    )

    def calculate_revenue(self, usage: float, prev_tier_end=False, bulk_pricing_enabled=False):
        # if division_factor is None:
        #     division_factor = len(usage_dict)
        revenue = 0
        discontinuous_range = (
            prev_tier_end != self.range_start and prev_tier_end is not None
        )
        # for usage in usage_dict.values():
        usage = convert_to_decimal(usage)
        
        if bulk_pricing_enabled and self.range_end is not None and self.range_end <= usage:
            return revenue
        
        usage_in_range = (
            self.range_start <= usage
            if discontinuous_range
            else self.range_start < usage or self.range_start == 0
        )
        if usage_in_range:
            if self.type == PriceTier.PriceTierType.FLAT:
                revenue += self.cost_per_batch
                return revenue
            
            if self.type == PriceTier.PriceTierType.PER_UNIT:
                if bulk_pricing_enabled:
                    billable_units = usage
                elif self.range_end is not None:
                    billable_units = min(
                        usage - self.range_start, self.range_end - self.range_start
                    )
                else:
                    billable_units = usage - self.range_start
                if discontinuous_range:
                    billable_units += 1
                billable_batches = billable_units / self.metric_units_per_batch
                if self.batch_rounding_type == PriceTier.BatchRoundingType.ROUND_UP:
                    billable_batches = math.ceil(billable_batches)
                elif self.batch_rounding_type == PriceTier.BatchRoundingType.ROUND_DOWN:
                    billable_batches = math.floor(billable_batches)
                elif (
                    self.batch_rounding_type
                    == PriceTier.BatchRoundingType.ROUND_NEAREST
                ):
                    billable_batches = round(billable_batches)
                revenue += self.cost_per_batch * billable_batches
        return revenue


class ComponentFixedCharge(models.Model):
    class ChargeBehavior(models.IntegerChoices):
        PRORATE = (1, _("prorate"))
        FULL = (2, _("full"))

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="component_charges"
    )
    units = models.DecimalField(
        decimal_places=10,
        max_digits=20,
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
    )
    charge_behavior = models.PositiveSmallIntegerField(
        choices=ChargeBehavior.choices, default=ChargeBehavior.PRORATE
    )

    def __str__(self):
        try:
            return f"Fixed Charge for {self.component}"
        except AttributeError:
            return "Fixed Charge"

    @staticmethod
    def get_charge_behavior_from_label(label):
        mapping = {
            ComponentFixedCharge.ChargeBehavior.PRORATE.label: ComponentFixedCharge.ChargeBehavior.PRORATE.value,
            ComponentFixedCharge.ChargeBehavior.FULL.label: ComponentFixedCharge.ChargeBehavior.FULL.value,
        }
        return mapping.get(label, label)


class PlanComponent(models.Model):
    class IntervalLengthType(models.IntegerChoices):
        DAY = (1, "day")
        WEEK = (2, "week")
        MONTH = (3, "month")
        YEAR = (4, "year")

    organization = models.ForeignKey(
        "Organization",
        on_delete=models.CASCADE,
        related_name="plan_components",
        null=True,
    )
    usage_component_id = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True
    )
    billable_metric = models.ForeignKey(
        Metric,
        on_delete=models.CASCADE,
        related_name="+",
        null=True,
        blank=True,
    )
    plan_version = models.ForeignKey(
        "PlanVersion",
        on_delete=models.CASCADE,
        related_name="plan_components",
        null=True,
        blank=True,
    )
    pricing_unit = models.ForeignKey(
        "PricingUnit",
        on_delete=models.SET_NULL,
        related_name="components",
        null=True,
        blank=True,
    )
    invoicing_interval_unit = models.PositiveSmallIntegerField(
        choices=IntervalLengthType.choices, null=True, blank=True
    )
    invoicing_interval_count = models.PositiveSmallIntegerField(null=True, blank=True)
    reset_interval_unit = models.PositiveSmallIntegerField(
        choices=IntervalLengthType.choices, null=True, blank=True
    )
    reset_interval_count = models.PositiveSmallIntegerField(null=True, blank=True)
    fixed_charge = models.OneToOneField(
        ComponentFixedCharge,
        on_delete=models.SET_NULL,
        related_name="component",
        null=True,
    )
    bulk_pricing_enabled = models.BooleanField(default=False)

    def __str__(self):
        return str(self.billable_metric)

    def save(self, *args, **kwargs):
        if self.pricing_unit is None and self.plan_version is not None:
            self.pricing_unit = self.plan_version.currency
        super().save(*args, **kwargs)

    @staticmethod
    def convert_length_label_to_value(label):
        label_map = {
            PlanComponent.IntervalLengthType.DAY.label: PlanComponent.IntervalLengthType.DAY,
            PlanComponent.IntervalLengthType.WEEK.label: PlanComponent.IntervalLengthType.WEEK,
            PlanComponent.IntervalLengthType.MONTH.label: PlanComponent.IntervalLengthType.MONTH,
            PlanComponent.IntervalLengthType.YEAR.label: PlanComponent.IntervalLengthType.YEAR,
            None: None,
        }
        return label_map[label]

    def get_component_invoicing_dates(
        self, subscription_record, override_start_date=None
    ):
        # FOR PLAN COMPONENTS
        start_date = override_start_date or subscription_record.start_date
        end_date = subscription_record.end_date
        if self.invoicing_interval_unit is None:
            return [end_date]

        unit_map = {
            PlanComponent.IntervalLengthType.DAY: "days",
            PlanComponent.IntervalLengthType.WEEK: "weeks",
            PlanComponent.IntervalLengthType.MONTH: "months",
            PlanComponent.IntervalLengthType.YEAR: "years",
        }

        interval_delta = relativedelta(
            **{
                unit_map[self.invoicing_interval_unit]: self.invoicing_interval_count
                or 1
            }
        )

        invoicing_dates = []

        invoicing_date = start_date
        while invoicing_date < end_date:
            invoicing_date += interval_delta
            append_date = min(invoicing_date, end_date)
            invoicing_dates.append(append_date)

        return invoicing_dates

    def get_component_reset_dates(self, subscription_record, override_start_date=None):
        # FOR PLAN COMPONENTS

        sr_start_date = subscription_record.start_date
        sr_end_date = subscription_record.end_date
        if subscription_record.parent:
            range_start_date = subscription_record.parent.start_date
            range_end_date = subscription_record.parent.end_date
        else:
            range_start_date = sr_start_date
            range_end_date = sr_end_date
        if override_start_date:
            range_start_date = override_start_date
        reset_interval_unit = self.reset_interval_unit
        reset_interval_count = self.reset_interval_count
        # if we don't have a sub-plan length reset interval, use the plan length
        if not reset_interval_unit:
            # problem here is for addons. Their plans do not have durations as they depend on the parent subscription.
            reset_interval_unit = (
                self.plan_version.plan.plan_duration
                or subscription_record.parent.billing_plan.plan.plan_duration
            )
            if reset_interval_unit == PLAN_DURATION.QUARTERLY:
                reset_interval_count = 3

        unit_map = {
            PlanComponent.IntervalLengthType.DAY: "days",
            PlanComponent.IntervalLengthType.WEEK: "weeks",
            PlanComponent.IntervalLengthType.MONTH: "months",
            PlanComponent.IntervalLengthType.YEAR: "years",
            PLAN_DURATION.MONTHLY: "months",
            PLAN_DURATION.QUARTERLY: "months",
            PLAN_DURATION.YEARLY: "years",
        }

        interval_delta = relativedelta(
            **{unit_map[reset_interval_unit]: reset_interval_count or 1}
        )
        if not self.reset_interval_unit:
            unadjusted_duration_microseconds = (
                (range_start_date + interval_delta) - range_start_date
            ).total_seconds() * 10**6
            return [(sr_start_date, sr_end_date, unadjusted_duration_microseconds)]

        reset_dates = []

        reset_date = range_start_date
        while reset_date < range_end_date:
            append_date = min(reset_date, range_end_date)
            reset_dates.append(append_date)
            reset_date += interval_delta
        # Construct non-overlapping date ranges
        reset_ranges = []
        for i in range(len(reset_dates)):
            start = reset_dates[i]
            if i == len(reset_dates) - 1:
                end = sr_end_date
            else:
                end = reset_dates[i + 1] - datetime.timedelta(microseconds=1)
            unadjusted_duration_microseconds = (
                (reset_dates[i] + interval_delta) - reset_dates[i]
            ).total_seconds() * 10**6
            reset_ranges.append((start, end, unadjusted_duration_microseconds))

        return reset_ranges

    def calculate_total_revenue(
        self, billing_record, prepaid_units=None
    ) -> UsageRevenueSummary:
        assert isinstance(
            billing_record, BillingRecord
        ), "billing_record must be a BillingRecord"
        billable_metric = self.billable_metric
        usage_qty = billable_metric.get_billing_record_total_billable_usage(
            billing_record
        )
        revenue = self.tier_rating_function(usage_qty)
        latest_component_charge = self.component_charge_records.order_by(
            "-start_date"
        ).first()
        if latest_component_charge is not None:
            revenue_from_prepaid_units = self.tier_rating_function(prepaid_units)
            revenue = max(revenue - revenue_from_prepaid_units, 0)
        return {"revenue": revenue, "usage_qty": usage_qty}

    def tier_rating_function(self, usage_qty):
        revenue = 0
        tiers = self.tiers.all()
        for i, tier in enumerate(tiers):
            if i > 0:
                # this is for determining whether this is a continuous or discontinuous range
                prev_tier_end = tiers[i - 1].range_end
                tier_revenue = tier.calculate_revenue(
                    usage_qty, prev_tier_end=prev_tier_end, bulk_pricing_enabled=self.bulk_pricing_enabled
                )
            else:
                tier_revenue = tier.calculate_revenue(usage_qty, bulk_pricing_enabled=self.bulk_pricing_enabled)
            revenue += tier_revenue
        revenue = convert_to_decimal(revenue)
        return revenue

    def calculate_revenue_per_day(
        self, billing_record
    ) -> dict[datetime.datetime, UsageRevenueSummary]:
        assert isinstance(billing_record, BillingRecord)
        billable_metric = self.billable_metric
        usage_per_day = billable_metric.get_billing_record_daily_billable_usage(
            billing_record
        )
        results = {}
        for period in dates_bwn_two_dts(
            billing_record.start_date, billing_record.end_date
        ):
            period = convert_to_date(period)
            results[period] = {"revenue": Decimal(0), "usage_qty": Decimal(0)}

        running_total_revenue = Decimal(0)
        running_total_usage = Decimal(0)
        for date, usage_qty in usage_per_day.items():
            date = convert_to_date(date)
            usage_qty = convert_to_decimal(usage_qty)
            running_total_usage += usage_qty
            revenue = Decimal(0)
            tiers = self.tiers.all()
            for i, tier in enumerate(tiers):
                if i > 0:
                    prev_tier_end = tiers[i - 1].range_end
                    tier_revenue = tier.calculate_revenue(
                        running_total_usage, prev_tier_end=prev_tier_end
                    )
                else:
                    tier_revenue = tier.calculate_revenue(running_total_usage)
                revenue += convert_to_decimal(tier_revenue)
            date_revenue = revenue - running_total_revenue
            running_total_revenue += date_revenue
            if date in results:
                results[date]["revenue"] += date_revenue
                results[date]["usage_qty"] += usage_qty
        return results


class Feature(models.Model):
    feature_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="features"
    )
    feature_name = models.CharField(max_length=50, blank=False)
    feature_description = models.TextField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "feature_name"], name="unique_feature"
            )
        ]

    def __str__(self):
        return str(self.feature_name)


class Invoice(models.Model):
    class PaymentStatus(models.IntegerChoices):
        DRAFT = (1, _("draft"))
        VOIDED = (2, _("voided"))
        PAID = (3, _("paid"))
        UNPAID = (4, _("unpaid"))

    amount = models.DecimalField(
        decimal_places=10,
        max_digits=20,
        default=Decimal(0.0),
        validators=[MinValueValidator(0)],
    )
    currency = models.ForeignKey(
        "PricingUnit",
        on_delete=models.SET_NULL,
        related_name="invoices",
        null=True,
        blank=True,
    )
    issue_date = models.DateTimeField(max_length=100, default=now_utc)
    invoice_pdf = models.URLField(max_length=300, null=True, blank=True)
    org_connected_to_cust_payment_provider = models.BooleanField(default=False)
    cust_connected_to_payment_provider = models.BooleanField(default=False)
    payment_status = models.PositiveSmallIntegerField(
        choices=PaymentStatus.choices, default=PaymentStatus.UNPAID
    )
    due_date = models.DateTimeField(max_length=100, null=True, blank=True)
    invoice_number = models.CharField(max_length=13)
    invoice_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invoices", null=True
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, null=True, related_name="invoices"
    )
    subscription_records = models.ManyToManyField(
        "SubscriptionRecord", related_name="invoices"
    )
    invoice_past_due_webhook_sent = models.BooleanField(default=False)
    history = HistoricalRecords()
    __original_payment_status = None

    # EXTERNAL CONNECTIONS
    external_payment_obj_id = models.CharField(max_length=100, blank=True, null=True)
    external_payment_obj_type = models.CharField(
        choices=PAYMENT_PROCESSORS.choices, max_length=40, blank=True, null=True
    )
    external_payment_obj_status = models.TextField(blank=True, null=True)
    salesforce_integration = models.OneToOneField(
        "UnifiedCRMInvoiceIntegration", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __init__(self, *args, **kwargs):
        super(Invoice, self).__init__(*args, **kwargs)
        self.__original_payment_status = self.payment_status

    class Meta:
        indexes = [
            models.Index(fields=["organization", "payment_status"]),
            models.Index(fields=["organization", "customer"]),
            models.Index(fields=["organization", "invoice_number"]),
            models.Index(fields=["organization", "invoice_id"]),
            models.Index(fields=["organization", "external_payment_obj_id"]),
            models.Index(fields=["organization", "-issue_date"]),
        ]

    def __str__(self):
        return str(self.invoice_number)

    def save(self, *args, **kwargs):
        if not self.currency:
            self.currency = self.organization.default_currency

        ### Generate invoice number
        new = self._state.adding is True
        if new and self.payment_status != Invoice.PaymentStatus.DRAFT:
            issue_date = self.issue_date.date()
            issue_date_string = issue_date.strftime("%y%m%d")
            next_invoice_number = "000001"
            last_invoice = (
                Invoice.objects.filter(
                    invoice_number__startswith=issue_date_string,
                    organization=self.organization,
                )
                .order_by("-invoice_number")
                .first()
            )
            if last_invoice:
                last_invoice_number = int(last_invoice.invoice_number[7:])
                next_invoice_number = "{0:06d}".format(last_invoice_number + 1)

            self.invoice_number = issue_date_string + "-" + next_invoice_number
        super().save(*args, **kwargs)
        if (
            self.__original_payment_status != self.payment_status
            and self.payment_status == Invoice.PaymentStatus.PAID
            and self.amount > 0
        ):
            invoice_paid_webhook(self, self.organization)
        self.__original_payment_status = self.payment_status


class InvoiceLineItemAdjustment(models.Model):
    class AdjustmentType(models.IntegerChoices):
        SALES_TAX = (1, _("sales_tax"))
        PLAN_ADJUSTMENT = (2, _("plan_adjustment"))

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="invoice_line_item_adjustments",
        null=True,
    )
    invoice_line_item = models.ForeignKey(
        "InvoiceLineItem",
        on_delete=models.CASCADE,
        related_name="adjustments",
        null=True,
    )
    amount = models.DecimalField(
        decimal_places=10,
        max_digits=20,
    )
    account = models.PositiveBigIntegerField()
    adjustment_type = models.PositiveSmallIntegerField(choices=AdjustmentType.choices)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.invoice_line_item.save()


class InvoiceLineItem(models.Model):
    invoice_line_item_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="invoice_line_items",
        null=True,
    )
    name = models.CharField(max_length=100)
    start_date = models.DateTimeField(max_length=100, default=now_utc)
    end_date = models.DateTimeField(max_length=100, default=now_utc)
    quantity = models.DecimalField(
        decimal_places=10,
        max_digits=20,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    base = models.DecimalField(
        decimal_places=10,
        max_digits=20,
        default=Decimal(0.0),
        help_text="Base price of the line item. This is the price before any adjustments are applied.",
    )
    amount = models.DecimalField(
        decimal_places=10,
        max_digits=20,
        default=Decimal(0.0),
        help_text="Amount of the line item. This is the price after any adjustments are applied.",
    )
    pricing_unit = models.ForeignKey(
        "PricingUnit",
        on_delete=models.SET_NULL,
        related_name="line_items",
        null=True,
        blank=True,
    )
    billing_type = models.CharField(
        max_length=40, choices=INVOICE_CHARGE_TIMING_TYPE.choices, blank=True, null=True
    )
    chargeable_item_type = models.CharField(
        max_length=40, choices=CHARGEABLE_ITEM_TYPE.choices, blank=True, null=True
    )
    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, null=True, related_name="line_items"
    )
    associated_plan_version = models.ForeignKey(
        "PlanVersion",
        on_delete=models.SET_NULL,
        null=True,
        related_name="line_items",
    )
    associated_subscription_record = models.ForeignKey(
        "SubscriptionRecord",
        on_delete=models.SET_NULL,
        null=True,
        related_name="line_items",
    )
    associated_billing_record = models.ForeignKey(
        "BillingRecord",
        on_delete=models.SET_NULL,
        null=True,
        related_name="line_items",
    )
    metadata = models.JSONField(default=dict, blank=True, null=True)

    def __str__(self):
        return self.name + " " + str(self.invoice.invoice_number) + f"[{self.base}]"

    def save(self, *args, **kwargs):
        self.amount = self.base + sum(
            [adjustment.amount for adjustment in self.adjustments.all()]
        )
        super().save(*args, **kwargs)


class APIToken(AbstractAPIKey):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="api_keys"
    )

    class Meta(AbstractAPIKey.Meta):
        verbose_name = "API Token"
        verbose_name_plural = "API Tokens"

    def __str__(self):
        return str(self.name) + " " + str(self.organization.organization_name)


class TeamInviteToken(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="user_invite_token"
    )
    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="team_invite_token"
    )
    email = models.EmailField()
    token = models.SlugField(max_length=250, default=uuid.uuid4)
    expire_at = models.DateTimeField(default=now_plus_day, null=False, blank=False)

    def __str__(self):
        return str(self.email) + " - " + str(self.team)


class RecurringCharge(models.Model):
    class ChargeTimingType(models.IntegerChoices):
        IN_ADVANCE = (1, "in_advance")
        IN_ARREARS = (2, "in_arrears")

    class ChargeBehaviorType(models.IntegerChoices):
        PRORATE = (1, "prorate")
        CHARGE_FULL = (2, "full")

    class IntervalLengthType(models.IntegerChoices):
        DAY = (1, "day")
        WEEK = (2, "week")
        MONTH = (3, "month")
        YEAR = (4, "year")

    recurring_charge_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="recurring_charges",
    )
    name = models.TextField()
    plan_version = models.ForeignKey(
        "PlanVersion",
        on_delete=models.CASCADE,
        related_name="recurring_charges",
    )
    charge_timing = models.PositiveSmallIntegerField(
        choices=ChargeTimingType.choices, default=ChargeTimingType.IN_ADVANCE
    )
    charge_behavior = models.PositiveSmallIntegerField(
        choices=ChargeBehaviorType.choices, default=ChargeBehaviorType.PRORATE
    )
    amount = models.DecimalField(
        decimal_places=10,
        max_digits=20,
        default=Decimal(0.0),
        validators=[MinValueValidator(0)],
    )
    pricing_unit = models.ForeignKey(
        "PricingUnit",
        on_delete=models.SET_NULL,
        related_name="recurring_charges",
        null=True,
    )
    reset_interval_unit = models.PositiveSmallIntegerField(
        choices=IntervalLengthType.choices, null=True, blank=True
    )
    reset_interval_count = models.PositiveSmallIntegerField(null=True, blank=True)
    invoicing_interval_unit = models.PositiveSmallIntegerField(
        choices=IntervalLengthType.choices, null=True, blank=True
    )
    invoicing_interval_count = models.PositiveSmallIntegerField(null=True, blank=True)

    def __str__(self):
        return self.name + " [" + str(self.plan_version) + "]"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "plan_version", "name"],
                name="unique_recurring_charge_name_in_plan_version",
            )
        ]

    @staticmethod
    def convert_length_label_to_value(label):
        label_map = {
            RecurringCharge.IntervalLengthType.DAY.label: RecurringCharge.IntervalLengthType.DAY,
            RecurringCharge.IntervalLengthType.WEEK.label: RecurringCharge.IntervalLengthType.WEEK,
            RecurringCharge.IntervalLengthType.MONTH.label: RecurringCharge.IntervalLengthType.MONTH,
            RecurringCharge.IntervalLengthType.YEAR.label: RecurringCharge.IntervalLengthType.YEAR,
            None: None,
        }
        return label_map[label]

    def get_recurring_charge_invoicing_dates(
        self, subscription_record, append_range_start=False
    ):
        # FOR RECURRIG CHARGES
        # first we get the actual star tdate and end date of this subscription. However, if this is an addon, we need to calculate the periods w.r.t the parent subscription
        sr_start_date = subscription_record.start_date
        sr_end_date = subscription_record.end_date
        if subscription_record.parent:
            range_start_date = subscription_record.parent.start_date
            range_end_date = subscription_record.parent.end_date
        else:
            range_start_date = sr_start_date
            range_end_date = sr_end_date
        invoicing_interval_unit = self.invoicing_interval_unit
        invoicing_interval_count = self.invoicing_interval_count
        # if we don't have a sub-plan length invoicing interval, use the plan length
        if not invoicing_interval_unit:
            # problem here is for addons. Their plans do not have durations as they depend on the parent subscription.
            invoicing_interval_unit = (
                self.plan_version.plan.plan_duration
                or subscription_record.parent.billing_plan.plan.plan_duration
            )
            if invoicing_interval_unit == PLAN_DURATION.QUARTERLY:
                invoicing_interval_count = 3

        unit_map = {
            PlanComponent.IntervalLengthType.DAY: "days",
            PlanComponent.IntervalLengthType.WEEK: "weeks",
            PlanComponent.IntervalLengthType.MONTH: "months",
            PlanComponent.IntervalLengthType.YEAR: "years",
            PLAN_DURATION.MONTHLY: "months",
            PLAN_DURATION.QUARTERLY: "months",
            PLAN_DURATION.YEARLY: "years",
        }
        interval_delta = relativedelta(
            **{unit_map[invoicing_interval_unit]: invoicing_interval_count or 1}
        )

        invoicing_dates = []

        invoicing_date = range_start_date
        # now generate invoicing dates
        while invoicing_date < range_end_date:
            invoicing_date += interval_delta
            append_date = min(invoicing_date, range_end_date)
            invoicing_dates.append(append_date)

        # purge the ones that don't match up with the real duration, and add the start + end dates
        invoicing_dates = {
            x for x in invoicing_dates if x >= sr_start_date and x <= sr_end_date
        }
        if append_range_start:
            invoicing_dates = invoicing_dates | {sr_start_date}
        invoicing_dates = invoicing_dates | {sr_end_date}
        invoicing_dates = sorted(list(invoicing_dates))
        return invoicing_dates

    def get_recurring_charge_reset_dates(self, subscription_record):
        # FOR RECURRIG CHARGES
        sr_start_date = subscription_record.start_date
        sr_end_date = subscription_record.end_date
        if subscription_record.parent:
            range_start_date = subscription_record.parent.start_date
            range_end_date = subscription_record.parent.end_date
        else:
            range_start_date = sr_start_date
            range_end_date = sr_end_date
        reset_interval_unit = self.reset_interval_unit
        reset_interval_count = self.reset_interval_count
        # if we don't have a sub-plan length reset interval, use the plan length
        if not reset_interval_unit:
            # problem here is for addons. Their plans do not have durations as they depend on the parent subscription.
            reset_interval_unit = (
                self.plan_version.plan.plan_duration
                or subscription_record.parent.billing_plan.plan.plan_duration
            )
            if reset_interval_unit == PLAN_DURATION.QUARTERLY:
                reset_interval_count = 3

        unit_map = {
            PlanComponent.IntervalLengthType.DAY: "days",
            PlanComponent.IntervalLengthType.WEEK: "weeks",
            PlanComponent.IntervalLengthType.MONTH: "months",
            PlanComponent.IntervalLengthType.YEAR: "years",
            PLAN_DURATION.MONTHLY: "months",
            PLAN_DURATION.QUARTERLY: "months",
            PLAN_DURATION.YEARLY: "years",
        }

        interval_delta = relativedelta(
            **{unit_map[reset_interval_unit]: reset_interval_count or 1}
        )
        if not self.reset_interval_unit:
            unadjusted_duration_microseconds = (
                (range_start_date + interval_delta) - range_start_date
            ).total_seconds() * 10**6
            return [(sr_start_date, sr_end_date, unadjusted_duration_microseconds)]

        reset_dates = []

        reset_date = range_start_date
        while reset_date < range_end_date:
            append_date = min(reset_date, range_end_date)
            reset_dates.append(append_date)
            reset_date += interval_delta
        # Construct non-overlapping date ranges
        reset_ranges = []
        for i in range(len(reset_dates)):
            if sr_start_date > reset_dates[i]:
                continue
            start = max(reset_dates[i], sr_start_date)
            if i == len(reset_dates) - 1:
                end = sr_end_date
            else:
                end = reset_dates[i + 1] - datetime.timedelta(microseconds=1)
            unadjusted_duration_microseconds = (
                (reset_dates[i] + interval_delta) - reset_dates[i]
            ).total_seconds() * 10**6
            reset_ranges.append((start, end, unadjusted_duration_microseconds))

        return reset_ranges


class BasePlanManager(models.Manager):
    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.filter(deleted__isnull=True)
        return qs

    def active(self, time=None):
        if time is None:
            time = now_utc()
        return self.filter(
            Q(active_from__lte=time)
            & ((Q(active_to__gt=time) | Q(active_to__isnull=True)))
        )

    def ended(self, time=None):
        if time is None:
            time = now_utc()
        return self.filter(active_to__lte=time)

    def not_started(self, time=None):
        if time is None:
            time = now_utc()
        return self.filter(active_from__gt=time)


class PlanVersionManager(BasePlanManager):
    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.filter(deleted__isnull=True)
        return qs


class DeletedPlanVersionManager(models.Manager):
    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.filter(deleted__isnull=False)
        return qs


class RegularPlanVersionManager(PlanVersionManager):
    def get_queryset(self):
        return super().get_queryset().filter(addon_spec__isnull=True)


class AddOnPlanVersionManager(PlanVersionManager):
    def get_queryset(self):
        return super().get_queryset().filter(addon_spec__isnull=False)


class PlanVersion(models.Model):
    # META
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="plan_versions",
    )
    version = models.PositiveSmallIntegerField(default=1)
    version_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    localized_name = models.TextField(null=True, blank=True, default=None)
    plan = models.ForeignKey("Plan", on_delete=models.CASCADE, related_name="versions")
    created_on = models.DateTimeField(default=now_utc)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="created_plan_versions",
        null=True,
        blank=True,
    )
    deleted = models.DateTimeField(null=True, blank=True)

    # BILLING SCHEDULE
    day_anchor = models.SmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        null=True,
        blank=True,
    )
    month_anchor = models.SmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        null=True,
        blank=True,
    )
    replace_with = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    transition_to = models.ForeignKey(
        "Plan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transition_from",
    )
    addon_spec = models.OneToOneField(
        "AddOnSpecification",
        on_delete=models.SET_NULL,
        related_name="plan_version",
        null=True,
        blank=True,
    )
    active_from = models.DateTimeField(null=True, default=now_utc, blank=True)
    active_to = models.DateTimeField(null=True, blank=True)

    # PRICING
    features = models.ManyToManyField(Feature, blank=True)
    price_adjustment = models.ForeignKey(
        "PriceAdjustment", on_delete=models.SET_NULL, null=True, blank=True
    )
    currency = models.ForeignKey(
        "PricingUnit",
        on_delete=models.SET_NULL,
        related_name="versions",
        null=True,
        blank=True,
    )

    # MISC
    is_custom = models.BooleanField(default=False)
    target_customers = models.ManyToManyField(Customer, related_name="plan_versions")

    objects = PlanVersionManager()
    plan_versions = RegularPlanVersionManager()
    addon_versions = AddOnPlanVersionManager()
    deleted_objects = DeletedPlanVersionManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "version", "currency"],
                name="unique_plan_version_per_currency",
                condition=Q(is_custom=False),
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "plan"]),
            models.Index(fields=["organization", "version_id"]),
        ]

    def __str__(self) -> str:
        if self.localized_name is not None:
            return self.localized_name
        return str(self.plan)

    def num_active_subs(self):
        cnt = self.subscription_records.active().count()
        return cnt

    def is_active(self, time=None):
        if time is None:
            time = now_utc()
        return self.active_from <= time and (
            self.active_to is None or self.active_to > time
        )

    def get_status(self) -> PLAN_VERSION_STATUS:
        now = now_utc()
        if self.deleted is not None:
            return PLAN_VERSION_STATUS.DELETED
        if not self.active_from:
            return PLAN_VERSION_STATUS.INACTIVE
        if self.active_from <= now:
            if self.active_to is None or self.active_to > now:
                return PLAN_VERSION_STATUS.ACTIVE
            else:
                n_active_subs = self.num_active_subs()
                if self.replace_with is None:
                    if n_active_subs > 0:
                        # SHOULD NEVER HAPPEN. EXPIRED PLAN, ACTIVE SUBS, NO REPLACEMENT
                        return PLAN_VERSION_STATUS.GRANDFATHERED
                    else:
                        return PLAN_VERSION_STATUS.INACTIVE
                elif self.replace_with == self:
                    if n_active_subs > 0:
                        return PLAN_VERSION_STATUS.GRANDFATHERED
                    else:
                        return PLAN_VERSION_STATUS.INACTIVE
                else:
                    if n_active_subs > 0:
                        return PLAN_VERSION_STATUS.RETIRING
                    else:
                        return PLAN_VERSION_STATUS.INACTIVE
        else:
            return PLAN_VERSION_STATUS.INACTIVE


class PriceAdjustment(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="price_adjustments"
    )
    price_adjustment_name = models.CharField(max_length=100)
    price_adjustment_description = models.TextField(blank=True, null=True)
    price_adjustment_type = models.CharField(
        max_length=40, choices=PRICE_ADJUSTMENT_TYPE.choices
    )
    price_adjustment_amount = models.DecimalField(
        max_digits=20,
        decimal_places=10,
    )

    def __str__(self):
        if self.price_adjustment_name != "":
            return str(self.price_adjustment_name)
        else:
            return (
                str(round(self.price_adjustment_amount, 2))
                + " "
                + str(self.price_adjustment_type)
            )

    def apply(self, amount):
        if self.price_adjustment_type == PRICE_ADJUSTMENT_TYPE.PERCENTAGE:
            return amount * (1 + self.price_adjustment_amount / 100)
        elif self.price_adjustment_type == PRICE_ADJUSTMENT_TYPE.FIXED:
            return amount + self.price_adjustment_amount
        elif self.price_adjustment_type == PRICE_ADJUSTMENT_TYPE.PRICE_OVERRIDE:
            return self.price_adjustment_amount


class DeletedPlanManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted__isnull=False)


class RegularPlanManager(BasePlanManager):
    def get_queryset(self):
        return super().get_queryset().filter(is_addon=False)


class AddOnPlanManager(BasePlanManager):
    def get_queryset(self):
        return super().get_queryset().filter(is_addon=True)


class AddOnSpecification(models.Model):
    class BillingFrequency(models.IntegerChoices):
        ONE_TIME = (1, _("one_time"))
        RECURRING = (2, _("recurring"))

    class FlatFeeInvoicingBehaviorOnAttach(models.IntegerChoices):
        INVOICE_ON_ATTACH = (1, _("invoice_on_attach"))
        INVOICE_ON_SUBSCRIPTION_END = (2, _("invoice_on_subscription_end"))

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="+"
    )
    billing_frequency = models.PositiveSmallIntegerField(
        choices=BillingFrequency.choices, default=BillingFrequency.ONE_TIME
    )
    flat_fee_invoicing_behavior_on_attach = models.PositiveSmallIntegerField(
        choices=FlatFeeInvoicingBehaviorOnAttach.choices,
        default=FlatFeeInvoicingBehaviorOnAttach.INVOICE_ON_ATTACH,
    )

    @staticmethod
    def get_billing_frequency_value(label):
        mapping = {
            AddOnSpecification.BillingFrequency.ONE_TIME.label: AddOnSpecification.BillingFrequency.ONE_TIME.value,
            AddOnSpecification.BillingFrequency.RECURRING.label: AddOnSpecification.BillingFrequency.RECURRING.value,
        }
        return mapping.get(label, label)

    @staticmethod
    def get_flat_fee_invoicing_behavior_value(label):
        mapping = {
            AddOnSpecification.FlatFeeInvoicingBehaviorOnAttach.INVOICE_ON_ATTACH.label: AddOnSpecification.FlatFeeInvoicingBehaviorOnAttach.INVOICE_ON_ATTACH.value,
            AddOnSpecification.FlatFeeInvoicingBehaviorOnAttach.INVOICE_ON_SUBSCRIPTION_END.label: AddOnSpecification.FlatFeeInvoicingBehaviorOnAttach.INVOICE_ON_SUBSCRIPTION_END.value,
        }
        return mapping.get(label, label)


class Plan(models.Model):
    # META
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="plans"
    )
    plan_name = models.TextField(help_text="Name of the plan")
    plan_description = models.TextField(
        help_text="Description of the plan", blank=True, null=True
    )
    plan_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_on = models.DateTimeField(default=now_utc)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="created_plans",
        null=True,
        blank=True,
    )
    deleted = models.DateTimeField(null=True, blank=True)
    is_addon = models.BooleanField(default=False)

    # BILLING
    taxjar_code = models.TextField(max_length=30, null=True, blank=True)
    plan_duration = models.CharField(
        choices=PLAN_DURATION.choices,
        max_length=40,
        help_text="Duration of the plan",
        null=True,
    )
    active_from = models.DateTimeField(default=now_utc, blank=True)
    active_to = models.DateTimeField(null=True, blank=True)

    # MISC
    tags = models.ManyToManyField("Tag", blank=True, related_name="plans")

    objects = BasePlanManager()
    plans = RegularPlanManager()
    addons = AddOnPlanManager()
    deleted_objects = DeletedPlanManager()

    history = HistoricalRecords()

    # USELESS RN
    parent_product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="product_plans",
        null=True,
        blank=True,
        help_text="The product that this plan belongs to",
    )

    class Meta:
        indexes = [
            models.Index(fields=["organization", "plan_id"]),
        ]

    def __str__(self):
        return self.plan_name

    def add_tags(self, tags):
        existing_tags = self.tags.all()
        existing_tag_names = [tag.tag_name.lower() for tag in existing_tags]
        for tag in tags:
            if tag["tag_name"].lower() not in existing_tag_names:
                defaults = {
                    "tag_group": TAG_GROUP.PLAN,
                    "tag_hex": tag.get("tag_hex"),
                    "tag_color": tag.get("tag_color"),
                    "tag_name": tag["tag_name"],
                }
                tag_obj, _ = Tag.objects.get_or_create(
                    organization=self.organization,
                    tag_name__iexact=tag["tag_name"].lower(),
                    defaults=defaults,
                )
                self.tags.add(tag_obj)

    def remove_tags(self, tags):
        existing_tags = self.tags.all()
        tags_lower = [tag["tag_name"].lower() for tag in tags]
        for existing_tag in existing_tags:
            if existing_tag.tag_name.lower() in tags_lower:
                self.tags.remove(existing_tag)

    def set_tags(self, tags):
        existing_tags = self.tags.all()
        existing_tag_names = [tag.tag_name.lower() for tag in existing_tags]
        new_tag_names_lower = [tag["tag_name"].lower() for tag in tags]
        for tag in tags:
            if tag["tag_name"].lower() not in existing_tag_names:
                defaults = {
                    "tag_group": TAG_GROUP.PLAN,
                    "tag_hex": tag.get("tag_hex"),
                    "tag_color": tag.get("tag_color"),
                    "tag_name": tag["tag_name"],
                }
                tag_obj, _ = Tag.objects.get_or_create(
                    organization=self.organization,
                    tag_name__iexact=tag["tag_name"].lower(),
                    defaults=defaults,
                )
                self.tags.add(tag_obj)
        for existing_tag in existing_tags:
            if existing_tag.tag_name.lower() not in new_tag_names_lower:
                self.tags.remove(existing_tag)

    def active_subs_by_version(self):
        versions = self.versions.all().prefetch_related("subscription_records")
        now = now_utc()
        versions_count = versions.annotate(
            active_subscriptions=Count(
                "subscription_record",
                filter=Q(
                    subscription_record__start_date__lte=now,
                    subscription_record__end_date__gte=now,
                ),
                output_field=models.IntegerField(),
            )
        )
        return versions_count

    def get_version_for_customer(self, customer) -> Optional[PlanVersion]:
        versions = self.versions.active().prefetch_related(
            "subscription_records", "target_customers"
        )
        # rules are as follows:
        # 1. if there is only one version, return it
        # 2. custom plans, preferring the customer's preferred currency
        # 3. filter down to the customer's preferred currency
        # 4. filter down to the organization's preferred currency

        if versions.count() == 0:
            return None
        elif versions.count() == 1:
            return versions.first()
        else:
            customer_target_plans = customer.plan_versions.filter(plan=self)
            customer_target_plan_in_customer_currency = customer_target_plans.filter(
                currency=customer.default_currency
            )
            customer_target_plan_in_org_currency = customer_target_plans.filter(
                currency=customer.organization.default_currency
            )
            if customer_target_plans.count() == 1:
                return customer_target_plans.first()
            elif customer_target_plan_in_customer_currency.count() == 1:
                return customer_target_plan_in_customer_currency.first()
            elif customer_target_plan_in_customer_currency.count() > 1:
                return None  # DO NOT randomly choose a plan if multiple match
            elif customer_target_plan_in_org_currency.count() == 1:
                return customer_target_plan_in_org_currency.first()
            elif customer_target_plan_in_org_currency.count() > 1:
                return None

            # if we get here that means there are no customer specific plans
            versions_in_customer_currency = versions.filter(
                currency=customer.default_currency
            )
            if versions_in_customer_currency.count() == 1:
                return versions_in_customer_currency.first()
            elif versions_in_customer_currency.count() > 1:
                return None
            versions_in_org_currency = versions.filter(
                currency=customer.organization.default_currency
            )
            if versions_in_org_currency.count() == 1:
                return versions_in_org_currency.first()
            elif versions_in_org_currency.count() > 1:
                return None
            return None


class ExternalPlanLink(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="external_plan_links",
    )
    plan = models.ForeignKey(
        Plan, on_delete=models.CASCADE, related_name="external_links"
    )
    source = models.CharField(choices=PAYMENT_PROCESSORS.choices, max_length=40)
    external_plan_id = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.plan} - {self.source} - {self.external_plan_id}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "source", "external_plan_id"],
                name="unique_external_plan_link",
            )
        ]


class StripeSubscriptionRecordManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(stripe_subscription_id__isnull=False)


class SubscriptionRecordManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(stripe_subscription_id__isnull=True)

    def active(self, time=None):
        if time is None:
            time = now_utc()
        return self.filter(
            Q(start_date__lte=time)
            & ((Q(end_date__gte=time) | Q(end_date__isnull=True)))
        )

    def ended(self, time=None):
        if time is None:
            time = now_utc()
        return self.filter(end_date__lte=time)

    def not_started(self, time=None):
        if time is None:
            time = now_utc()
        return self.filter(start_date__gt=time)


class BaseSubscriptionRecordManager(SubscriptionRecordManager):
    def get_queryset(self):
        return super().get_queryset().filter(billing_plan__addon_spec__isnull=True)


class AddOnSubscriptionRecordManager(SubscriptionRecordManager):
    def get_queryset(self):
        return super().get_queryset().filter(billing_plan__addon_spec__isnull=False)


class SubscriptionRecord(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="subscription_records",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        null=False,
        related_name="subscription_records",
        help_text="The customer object associated with this subscription.",
    )
    billing_plan = models.ForeignKey(
        PlanVersion,
        on_delete=models.CASCADE,
        null=True,
        related_name="subscription_records",
        related_query_name="subscription_record",
        help_text="The plan associated with this subscription.",
    )
    usage_start_date = models.DateTimeField(null=True, blank=True)
    start_date = models.DateTimeField(
        help_text="The time the subscription starts. This will be a string in yyyy-mm-dd HH:mm:ss format in UTC time."
    )
    end_date = models.DateTimeField(
        help_text="The time the subscription starts. This will be a string in yyyy-mm-dd HH:mm:ss format in UTC time."
    )
    auto_renew = models.BooleanField(
        default=True,
        help_text="Whether the subscription automatically renews. Defaults to true.",
    )
    is_new = models.BooleanField(
        default=True,
        help_text="Whether this subscription came from a renewal or from a first-time. Defaults to true on creation.",
    )
    subscription_record_id = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True
    )
    subscription_filters = ArrayField(
        ArrayField(
            models.TextField(blank=False, null=False),
            size=2,
        ),
        default=list,
    )
    invoice_usage_charges = models.BooleanField(default=True)
    flat_fee_behavior = models.CharField(
        choices=FLAT_FEE_BEHAVIOR.choices, max_length=20, null=True, default=None
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="addon_subscription_records",
        help_text="The parent subscription record.",
    )
    quantity = models.PositiveIntegerField(default=1)
    metadata = models.JSONField(default=dict, blank=True)
    stripe_subscription_id = models.TextField(null=True, blank=True, default=None)

    # managers etc
    objects = SubscriptionRecordManager()
    addon_objects = AddOnSubscriptionRecordManager()
    base_objects = BaseSubscriptionRecordManager()
    stripe_objects = StripeSubscriptionRecordManager()
    history = HistoricalRecords()

    class Meta:
        constraints = [
            CheckConstraint(
                check=Q(start_date__lte=F("end_date")), name="end_date_gte_start_date"
            ),
            CheckConstraint(check=Q(quantity__gt=0), name="quantity_gt_0"),
            # check if stripe subscription id is null, then billing plan is not null, and vice versa
            CheckConstraint(
                check=(
                    Q(stripe_subscription_id__isnull=False)
                    & Q(billing_plan__isnull=True)
                )
                | (
                    Q(stripe_subscription_id__isnull=True)
                    & Q(billing_plan__isnull=False)
                ),
                name="stripe_subscription_id_xor_billing_plan",
            ),
        ]

    def __str__(self):
        addon = "[ADDON] " if self.billing_plan.addon_spec else ""
        if self.stripe_subscription_id:
            plan_name = "Stripe Subscription {}".format(self.stripe_subscription_id)
        else:
            plan_name = self.billing_plan.plan.plan_name
        return f"{addon}{self.customer.customer_name}  {plan_name} : {self.start_date.date()} to {self.end_date.date()}"

    @staticmethod
    def create_subscription_record(
        start_date,
        end_date,
        billing_plan,
        customer,
        organization,
        subscription_filters=None,
        is_new=True,
        quantity=1,
        component_fixed_charges_initial_units=None,
        do_generate_invoice=True,
    ):
        from metering_billing.invoice import generate_invoice

        if component_fixed_charges_initial_units is None:
            component_fixed_charges_initial_units = []
        component_fixed_charges_initial_units = {
            d["metric"]: d["units"] for d in component_fixed_charges_initial_units
        }
        assert (
            billing_plan.addon_spec is None
        ), "Cannot create a base subscription record with an addon plan"
        sr = SubscriptionRecord.objects.create(
            start_date=start_date,
            end_date=end_date,
            billing_plan=billing_plan,
            customer=customer,
            organization=organization,
            subscription_filters=subscription_filters,
            is_new=is_new,
            quantity=quantity,
        )
        for component in sr.billing_plan.plan_components.all():
            metric = component.billable_metric
            kwargs = {}
            if metric in component_fixed_charges_initial_units:
                kwargs["initial_units"] = component_fixed_charges_initial_units[metric]
            sr._create_component_billing_records(component, **kwargs)
        for recurring_charge in sr.billing_plan.recurring_charges.all():
            sr._create_recurring_charge_billing_records(recurring_charge)
        if do_generate_invoice:
            generate_invoice(sr)
        return sr

    @staticmethod
    def create_addon_subscription_record(
        parent_subscription_record,
        addon_billing_plan,
        quantity=1,
    ):
        from metering_billing.invoice import generate_invoice

        now = now_utc()
        assert (
            addon_billing_plan.addon_spec is not None
        ), "Cannot create an addon subscription record with a base plan"
        sr = SubscriptionRecord.objects.create(
            parent=parent_subscription_record,
            start_date=now,
            end_date=parent_subscription_record.end_date,
            billing_plan=addon_billing_plan,
            customer=parent_subscription_record.customer,
            organization=parent_subscription_record.organization,
            subscription_filters=parent_subscription_record.subscription_filters,
            is_new=True,
            quantity=quantity,
            auto_renew=addon_billing_plan.addon_spec.billing_frequency
            == AddOnSpecification.BillingFrequency.RECURRING,
        )
        for component in sr.billing_plan.plan_components.all():
            sr._create_component_billing_records(component)
        for recurring_charge in sr.billing_plan.recurring_charges.all():
            sr._create_recurring_charge_billing_records(recurring_charge)
        generate_invoice(sr)
        return sr

    def _create_component_billing_records(
        self,
        component,
        override_start_date=None,
        initial_units=None,
        ignore_prepaid=False,
        fail_on_no_prepaid=True,
    ):
        prepaid_charge = component.fixed_charge
        invoicing_dates = component.get_component_invoicing_dates(
            self, override_start_date
        )
        reset_ranges = component.get_component_reset_dates(self, override_start_date)
        brs = []
        for start_date, end_date, unadjusted_duration_microseconds in reset_ranges:
            one_past_end_added = False
            br_invoicing_dates = set()
            for inv_date in invoicing_dates:
                if one_past_end_added:
                    break
                if inv_date >= start_date:
                    br_invoicing_dates.add(inv_date)
                    if inv_date >= end_date:
                        one_past_end_added = True
            br_invoicing_dates = sorted(list(br_invoicing_dates))

            br = BillingRecord.objects.create(
                organization=self.organization,
                subscription=self,
                component=component,
                start_date=start_date,
                end_date=end_date,
                invoicing_dates=br_invoicing_dates,
                unadjusted_duration_microseconds=unadjusted_duration_microseconds,
            )
            new_invoicing_dates = set(br_invoicing_dates)
            if prepaid_charge and not ignore_prepaid:
                units = initial_units or prepaid_charge.units
                if units is None and fail_on_no_prepaid:
                    raise PrepaymentMissingUnits(
                        "No units specified for prepayment. This is usually an input error but may possibly be caused by inconsistent state in the backend."
                    )
                if units:
                    ComponentChargeRecord.objects.create(
                        organization=self.organization,
                        billing_record=br,
                        component_charge=prepaid_charge,
                        component=component,
                        start_date=start_date,
                        end_date=end_date,
                        units=units,
                    )
                    new_invoicing_dates |= {start_date}
            new_invoicing_dates = sorted(list(new_invoicing_dates))
            if new_invoicing_dates != br_invoicing_dates:
                br.invoicing_dates = new_invoicing_dates
                br.next_invoicing_date = new_invoicing_dates[0]
                br.save()
            brs.append(br)
        return brs

    def _create_recurring_charge_billing_records(self, recurring_charge):
        # first thign we want to see is if we need to charge "in advance" at all, that will
        # affect the way we calculate the reset ranges and invociing dates
        append_range_start = False
        if (
            recurring_charge.charge_timing
            == RecurringCharge.ChargeTimingType.IN_ADVANCE
        ):
            addon_spec = recurring_charge.plan_version.addon_spec
            if (
                addon_spec
                and addon_spec.flat_fee_invoicing_behavior_on_attach
                == AddOnSpecification.FlatFeeInvoicingBehaviorOnAttach.INVOICE_ON_SUBSCRIPTION_END
            ):
                # this is the ONLY case where its in advance and we don't want to append the range start. in this case they explicitly do not want to charge the flat fee on attach
                append_range_start = False
            else:
                append_range_start = True

        invoicing_dates = recurring_charge.get_recurring_charge_invoicing_dates(
            self, append_range_start
        )
        reset_ranges = recurring_charge.get_recurring_charge_reset_dates(self)
        brs = []
        for start_date, end_date, unadjusted_duration_microseconds in reset_ranges:
            one_past_end_added = False
            br_invoicing_dates = set()
            for inv_date in invoicing_dates:
                if one_past_end_added:
                    break
                if inv_date >= start_date:
                    br_invoicing_dates.add(inv_date)
                    if inv_date >= end_date:
                        one_past_end_added = True
            br_invoicing_dates = sorted(list(br_invoicing_dates))
            br = BillingRecord.objects.create(
                organization=self.organization,
                subscription=self,
                recurring_charge=recurring_charge,
                invoicing_dates=br_invoicing_dates,
                start_date=start_date,
                end_date=end_date,
                unadjusted_duration_microseconds=unadjusted_duration_microseconds,
            )
            brs.append(br)
        return brs

    def save(self, *args, **kwargs):
        if self.subscription_filters is None:
            self.subscription_filters = []
        now = now_utc()
        timezone = self.customer.timezone
        if not self.end_date:
            day_anchor, month_anchor = (
                self.billing_plan.day_anchor,
                self.billing_plan.month_anchor,
            )
            self.end_date = calculate_end_date(
                self.billing_plan.plan.plan_duration,
                self.start_date,
                timezone,
                day_anchor=day_anchor,
                month_anchor=month_anchor,
            )
        new = self._state.adding is True
        if new:
            new_filters = set(tuple(x) for x in self.subscription_filters)
            overlapping_subscriptions = SubscriptionRecord.objects.filter(
                Q(start_date__range=(self.start_date, self.end_date))
                | Q(end_date__range=(self.start_date, self.end_date)),
                organization=self.organization,
                customer=self.customer,
                billing_plan=self.billing_plan,
            )
            for subscription in overlapping_subscriptions:
                old_filters = set(tuple(x) for x in subscription.subscription_filters)
                if old_filters.issubset(new_filters) or new_filters.issubset(
                    old_filters
                ):
                    raise OverlappingPlans(
                        f"Overlapping subscriptions with the same filters are not allowed. \n Plan: {self.billing_plan} \n Customer: {self.customer}. \n New dates: ({self.start_date, self.end_date}) \n New subscription_filters: {new_filters} \n Old dates: ({self.start_date, self.end_date}) \n Old subscription_filters: {list(old_filters)}"
                    )
        super(SubscriptionRecord, self).save(*args, **kwargs)
        if new:
            alerts = UsageAlert.objects.filter(
                organization=self.organization, plan_version=self.billing_plan
            )
            now = now_utc()
            for alert in alerts:
                UsageAlertResult.objects.create(
                    organization=self.organization,
                    alert=alert,
                    subscription_record=self,
                    last_run_value=0,
                    last_run_timestamp=now,
                )

    def get_filters_dictionary(self):
        filters_dict = {f[0]: f[1] for f in self.subscription_filters}
        return filters_dict

    def amt_already_invoiced(self):
        billed_invoices = self.line_items.filter(
            ~Q(invoice__payment_status=Invoice.PaymentStatus.VOIDED)
            & ~Q(invoice__payment_status=Invoice.PaymentStatus.DRAFT),
            base__isnull=False,
        ).aggregate(tot=Sum("base"))["tot"]
        return billed_invoices or 0

    def get_usage_and_revenue(self):
        sub_dict = {"components": []}
        # set up the billing plan for this subscription
        plan = self.billing_plan
        # set up other details of the subscription
        self.start_date
        self.end_date
        # extract other objects that we need when calculating usage
        self.customer
        plan_components_qs = plan.plan_components.all()
        # For each component of the plan, calculate usage/revenue
        for plan_component in plan_components_qs:
            plan_component_summary = plan_component.calculate_total_revenue(self)
            sub_dict["components"].append((plan_component.pk, plan_component_summary))
        sub_dict["usage_amount_due"] = Decimal(0)
        for component_pk, component_dict in sub_dict["components"]:
            sub_dict["usage_amount_due"] += component_dict["revenue"]
        sub_dict["flat_amount_due"] = sum(
            x.amount for x in plan.recurring_charges.all()
        )
        sub_dict["total_amount_due"] = (
            sub_dict["flat_amount_due"] + sub_dict["usage_amount_due"]
        )
        return sub_dict

    def cancel_subscription(
        self,
        bill_usage=True,
        flat_fee_behavior=FLAT_FEE_BEHAVIOR.CHARGE_FULL,
        invoice_now=True,
    ):
        from metering_billing.invoice import generate_invoice

        now = now_utc()
        if self.end_date <= now:
            logger.info("Subscription already ended.")
            raise SubscriptionAlreadyEnded
        self.flat_fee_behavior = flat_fee_behavior
        self.invoice_usage_charges = bill_usage
        self.auto_renew = False
        self.end_date = now
        self.save()
        for billing_record in self.billing_records.all():
            billing_record.cancel_billing_record(now)
        addon_srs = []
        for addon_sr in self.addon_subscription_records.filter(end_date__gt=now):
            addon_sr.cancel_subscription(
                bill_usage=bill_usage,
                flat_fee_behavior=flat_fee_behavior,
                invoice_now=False,
            )
            addon_srs.append(addon_sr)
        srs = [self] + addon_srs
        if invoice_now:
            generate_invoice(srs)

    def turn_off_auto_renew(self):
        self.auto_renew = False
        self.save()

    @staticmethod
    def _billing_record_cancel_protocol(billing_record, cancel_date, invoice_now=True):
        if billing_record.start_date >= cancel_date:
            # this billing record hasn't started yet, so we can just delete it
            billing_record.delete()
        elif billing_record.end_date < cancel_date:
            # this billing record has already ended, so we can just check if we should invoice it now or not.
            if invoice_now:
                billing_record.cancel_billing_record(
                    cancel_date=cancel_date,
                    change_invoice_date_to_cancel_date=invoice_now,
                )
            else:
                # we don't want to invoice it now, so we can just leave the old invoice date
                pass
        else:
            # this means it's currently active
            billing_record.cancel_billing_record(
                cancel_date=cancel_date, change_invoice_date_to_cancel_date=invoice_now
            )

    @staticmethod
    def _check_should_transfer_cancel_if_not(
        billing_record, cancel_date, invoice_now=True
    ):
        if billing_record.start_date >= cancel_date:
            # this billing record hasn't started yet, so we can just delete it
            billing_record.delete()
            return False
        elif billing_record.end_date < cancel_date:
            # this billing record has already ended, so we can just check if we should invoice it now or not.
            if invoice_now:
                billing_record.cancel_billing_record(
                    cancel_date=cancel_date,
                    change_invoice_date_to_cancel_date=invoice_now,
                )
            else:
                # we don't want to invoice it now, so we can just leave the old invoice date
                pass
            return False
        return True

    def switch_plan(
        self,
        new_version,
        transfer_usage=True,
        invoice_now=True,
        component_fixed_charges_initial_units=None,
    ):
        from metering_billing.invoice import generate_invoice

        if component_fixed_charges_initial_units is None:
            component_fixed_charges_initial_units = []
        component_fixed_charges_initial_units = {
            d["metric"]: d["units"] for d in component_fixed_charges_initial_units
        }
        # when switching a plan, there's a few things we need to take into account:
        # 1. flat fees dont transfer. Just end them.
        # 2. what does it mean for usage to transfer? Does it just mean the billing records for the old plan are cancelled and new ones are created for the new plan with a start date the same as previously? In the case we used to charge for x but no longer do, then perhaps in that case we do charge? If we weren;t doing the whole reset frequency thing anymore it would be awesome because we could just switch which plan component it points at and have the already billed for be a part of that.
        now = now_utc()
        sr = SubscriptionRecord.objects.create(
            organization=self.organization,
            customer=self.customer,
            billing_plan=new_version,
            start_date=now + relativedelta(microseconds=1),
            end_date=self.end_date,
            auto_renew=self.auto_renew,
        )
        # current recurring_charge billing records must be canceled + billed
        for billing_record in self.billing_records.filter(
            recurring_charge__isnull=False, fully_billed=False
        ):
            # this is common enough that we made a method for it
            SubscriptionRecord._billing_record_cancel_protocol(
                billing_record, now, invoice_now=invoice_now
            )
        # and now we generate the new recurring_charge billing records
        for recurring_charge in new_version.recurring_charges.all():
            sr._create_recurring_charge_billing_records(recurring_charge)
        # same for component based billing records
        # so we're going to have to create a new billing record for each component, except if the metric coincides in the old plan and the new plan, then if transfer usage is true we have to do some wizardry to accomplish this
        # first a set of components we'll create from scratch... if we transfer usage from anywhere we'll remove it from this set
        pcs_to_create_charges_for = set(new_version.plan_components.all())
        # dict of metrics for convenience
        new_version_metrics_map = {
            x.billable_metric: x for x in pcs_to_create_charges_for
        }
        for billing_record in self.billing_records.filter(
            component__isnull=False, fully_billed=False
        ):
            component = billing_record.component
            # if not transferring usage, simple, just cancel the billing record same as above
            if not transfer_usage:
                SubscriptionRecord._billing_record_cancel_protocol(
                    billing_record, now, invoice_now=invoice_now
                )
            else:
                metric = component.billable_metric
                if metric in new_version_metrics_map:
                    # if the metric is in the new plan, we perform the surgery to switch the billing record to the new plan. Don't create from scratch.
                    transfer = SubscriptionRecord._check_should_transfer_cancel_if_not(
                        billing_record, now, invoice_now=invoice_now
                    )
                    if transfer:
                        new_component = new_version_metrics_map[metric]
                        pcs_to_create_charges_for.remove(new_component)
                        new_billing_records = sr._create_component_billing_records(
                            new_component,
                            override_start_date=billing_record.start_date,
                            ignore_prepaid=True,
                        )
                        override_billing_record = new_billing_records[0]
                        # heres the surgery... open to improvements... this allows us to keep
                        # info about what's been paid already though which is nice
                        billing_record.subscription = sr
                        billing_record.billing_plan = new_version
                        billing_record.component = override_billing_record.component
                        billing_record.start_date = override_billing_record.start_date
                        billing_record.end_date = override_billing_record.end_date
                        billing_record.unadjusted_duration_microseconds = (
                            override_billing_record.unadjusted_duration_microseconds
                        )
                        billing_record.invoicing_dates = (
                            override_billing_record.invoicing_dates
                        )
                        billing_record.next_invoicing_date = (
                            override_billing_record.next_invoicing_date
                        )
                        billing_record.fully_billed = (
                            override_billing_record.fully_billed
                        )
                        billing_record.save()

                        charge_records = (
                            billing_record.component_charge_records.all().order_by(
                                "start_date"
                            )
                        )
                        for k, component_charge_record in enumerate(charge_records):
                            new_component = override_billing_record.component
                            component_charge_record.component = new_component
                            component_charge_record.component_charge = (
                                new_component.charges.all().first()
                            )
                            if k == len(charge_records) - 1:
                                component_charge_record.end_date = (
                                    billing_record.end_date
                                )
                            component_charge_record.save()
                        override_billing_record.delete()
                else:
                    # if the metric is not in the new plan, we cancel the billing record
                    SubscriptionRecord._billing_record_cancel_protocol(
                        billing_record, now, invoice_now=invoice_now
                    )
        for pc in pcs_to_create_charges_for:
            metric = pc.billable_metric
            kwargs = {}
            if metric in component_fixed_charges_initial_units:
                kwargs["initial_units"] = component_fixed_charges_initial_units[metric]
            sr._create_component_billing_records(pc, **kwargs)
        self.end_date = now
        self.auto_renew = False
        self.save()
        generate_invoice([self, sr])
        return sr

    def calculate_earned_revenue_per_day(self):
        return_dict = {}
        for billing_record in self.billing_records.all():
            br_dict = billing_record.calculate_earned_revenue_per_day()
            for key in br_dict:
                if key not in return_dict:
                    return_dict[key] = br_dict[key]
                else:
                    return_dict[key] += br_dict[key]
        return return_dict

    def delete_subscription(self, delete_time=None):
        if delete_time is None:
            delete_time = now_utc()
        self.end_date = delete_time
        self.auto_renew = False
        for billing_record in self.billing_records.all():
            if billing_record.start_date >= delete_time:
                # straight up delete it
                billing_record.delete()
            else:
                # essentially all we have to do is set everythign as already billed
                # this means we won't generate invoices for it anymore
                billing_record.end_date = min(billing_record.end_date, delete_time)
                billing_record.fully_billed = True
                billing_record.save()
        for addon_subscription in self.addon_subscription_records.all():
            addon_subscription.delete_subscription(delete_time=delete_time)
        self.save()


class BillingRecord(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="billing_records"
    )
    billing_record_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False
    )
    subscription = models.ForeignKey(
        SubscriptionRecord, on_delete=models.CASCADE, related_name="billing_records"
    )
    # directly inherited from subscription
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="billing_records"
    )
    billing_plan = models.ForeignKey(
        PlanVersion, on_delete=models.CASCADE, related_name="billing_records"
    )
    # only one of these two
    component = models.ForeignKey(
        PlanComponent,
        on_delete=models.CASCADE,
        related_name="billing_records",
        null=True,
    )
    recurring_charge = models.ForeignKey(
        RecurringCharge,
        on_delete=models.CASCADE,
        related_name="billing_records",
        null=True,
    )
    # rest of the fields
    start_date = models.DateTimeField(
        help_text="The start of when this service started being provided."
    )
    end_date = models.DateTimeField(
        help_text="The date this service stopped being provided."
    )
    unadjusted_duration_microseconds = models.BigIntegerField(
        help_text="The duration of this service in microseconds, if it had been of its full intended length without considering anchoring + intermediate periods.",
        null=True,
    )
    invoicing_dates = ArrayField(models.DateTimeField(), default=list)
    next_invoicing_date = models.DateTimeField()
    fully_billed = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(component__isnull=True)
                    | models.Q(recurring_charge__isnull=True)
                ),
                name="only_one_of_component_or_recurring_charge",
            ),
            models.CheckConstraint(
                check=(
                    models.Q(component__isnull=False)
                    | (
                        models.Q(recurring_charge__isnull=False)
                        & models.Q(unadjusted_duration_microseconds__isnull=False)
                    )
                ),
                name="recurring_charge_requires_unadjusted_duration",
            ),
        ]

    def __str__(self):
        if self.component is not None:
            return f"[Component BR]: {str(self.component)} {self.invoicing_dates}"
        else:
            return (
                f"[Recurring BR]: {str(self.recurring_charge)} {self.invoicing_dates}"
            )

    def save(self, *args, **kwargs):
        new = self._state.adding is True
        self.invoicing_dates = sorted(self.invoicing_dates)
        if new:
            if len(self.invoicing_dates) == 0:
                self.invoicing_dates = [self.end_date]
            if self.next_invoicing_date is None:
                self.next_invoicing_date = self.invoicing_dates[0]
        super().save(*args, **kwargs)

    def get_usage_and_revenue(self):
        assert (
            self.component is not None
        ), "Can't call get_usage_and_revenue for a recurring charge."
        ccr = self.component_charge_records.order_by("-start_date").first()
        kwargs = {}
        if ccr is not None:
            kwargs["prepaid_units"] = ccr.units
        plan_component_summary = self.component.calculate_total_revenue(self, **kwargs)
        return plan_component_summary

    def calculate_recurring_charge_due(self, proration_end_date):
        assert (
            self.recurring_charge is not None
        ), "This is not a recurring charge billing record."
        proration_factor = (
            (min(proration_end_date, self.end_date) - self.start_date).total_seconds()
            * 10**6
            / self.unadjusted_duration_microseconds
        )
        prorated_amount = (
            self.recurring_charge.amount
            * self.subscription.quantity
            * convert_to_decimal(proration_factor)
        )
        full_amount = self.recurring_charge.amount * self.subscription.quantity
        if (
            self.subscription.flat_fee_behavior is not None
        ):  # this overrides other behavior
            if self.subscription.flat_fee_behavior == FLAT_FEE_BEHAVIOR.REFUND:
                return Decimal(0.0)
            elif self.subscription.flat_fee_behavior == FLAT_FEE_BEHAVIOR.CHARGE_FULL:
                return full_amount
            else:
                return prorated_amount
        else:  # dont worry about invoice timing here, thats the problem of the invoice
            if (
                self.recurring_charge.charge_behavior
                == RecurringCharge.ChargeBehaviorType.PRORATE
            ):
                return prorated_amount
            else:
                return full_amount

    def handle_invoicing(self, invoice_date):
        if self.next_invoicing_date < invoice_date:
            found_next = False
            for invoicing_date in sorted(self.invoicing_dates):
                if invoicing_date > invoice_date:
                    self.next_invoicing_date = invoicing_date
                    self.save()
                    found_next = True
                    break
            if not found_next:
                self.fully_billed = True
                self.next_invoicing_date = self.invoicing_dates[-1]
                self.save()
        else:
            # do nothing, we have an invociing date coming up. This invoice was likely from attaching a subscription or something
            pass

    def calculate_earned_revenue_per_day(self) -> dict:
        dates = dates_bwn_two_dts(self.start_date, self.end_date)
        rev_per_day = dict.fromkeys(dates, Decimal(0))
        if self.recurring_charge:
            for day in rev_per_day:
                if day == self.start_date.date():
                    end_of_day = datetime.datetime.combine(
                        day, datetime.time.max
                    ).replace(tzinfo=self.start_date.tzinfo)
                    duration_microseconds = convert_to_decimal(
                        (end_of_day - self.start_date).total_seconds() * 10**6
                    )
                elif day == self.end_date.date():
                    start_of_day = datetime.datetime.combine(
                        day, datetime.time.min
                    ).replace(tzinfo=self.end_date.tzinfo)
                    duration_microseconds = convert_to_decimal(
                        (self.end_date - start_of_day).total_seconds() * 10**6
                    )
                else:
                    duration_microseconds = 10**6 * 60 * 60 * 24
                rev_per_day[day] = convert_to_decimal(
                    self.recurring_charge.amount
                    * self.subscription.quantity
                    / self.unadjusted_duration_microseconds
                    * duration_microseconds
                )
        else:  # components
            component_rev_per_day = self.component.calculate_revenue_per_day(self)
            for period, d in component_rev_per_day.items():
                period = convert_to_date(period)
                revenue = d["revenue"]
                if period in rev_per_day:
                    rev_per_day[period] += revenue
        return rev_per_day

    def prepaid_already_invoiced(self):
        return self.line_items.filter(
            chargeable_item_type=CHARGEABLE_ITEM_TYPE.PREPAID_USAGE_CHARGE
        ).aggregate(Sum("base"))["base__sum"] or Decimal(0.0)

    def amt_already_invoiced(self):
        if self.recurring_charge:
            return self.line_items.filter(
                chargeable_item_type=CHARGEABLE_ITEM_TYPE.RECURRING_CHARGE
            ).aggregate(Sum("base"))["base__sum"] or Decimal(0.0)
        else:
            return self.line_items.filter(
                chargeable_item_type=CHARGEABLE_ITEM_TYPE.USAGE_CHARGE
            ).aggregate(Sum("base"))["base__sum"] or Decimal(0.0)

    def qty_already_invoiced(self):
        assert (
            self.recurring_charge is None
        ), "This is a recurring charge billing record, cannot use this function."
        return self.line_items.filter(
            chargeable_item_type=CHARGEABLE_ITEM_TYPE.USAGE_CHARGE
        ).aggregate(Sum("quantity"))["quantity__sum"] or Decimal(0.0)

    def cancel_billing_record(
        self, cancel_date=None, change_invoice_date_to_cancel_date=True
    ):
        now = now_utc()
        if cancel_date is None:
            cancel_date = now
        if cancel_date < self.end_date and self.end_date > now:
            # cant set a cancellation date after the end date, and if it already ended we cant change the end date
            self.end_date = cancel_date
        if change_invoice_date_to_cancel_date:
            # the first thing this means is that further invoicing dates after the cancel date and in the future are removed
            self.invoicing_dates = sorted(
                [x for x in self.invoicing_dates if x <= cancel_date or x < now]
                + [cancel_date]
            )
            # the second thing this means is that the next invoicing date will be the cancel date
            self.next_invoicing_date = cancel_date
        self.save()

    def calculate_prepay_usage_revenue(self, component_charge_record):
        # the main consideration here is 1. how to handle proration and 2. how much has been invoiced already
        # 1. how to handle proration // how much is actually owed
        component = component_charge_record.component
        component_charge = component_charge_record.component_charge
        if (
            component_charge.charge_behavior
            == ComponentFixedCharge.ChargeBehavior.PRORATE
        ):
            total_amt = Decimal(0.0)
            for component_charge_record in self.component_charge_records.all():
                total_microseconds = int(
                    (
                        component_charge_record.end_date
                        - component_charge_record.start_date
                    ).total_seconds()
                    * 10**6
                )
                unadjusted_microseconds = (
                    component_charge_record.billing_record.unadjusted_duration_microseconds
                )
                full_amt_due = component.tier_rating_function(
                    component_charge_record.units
                )
                total_amt += full_amt_due * total_microseconds / unadjusted_microseconds
        else:
            total_amt = component.tier_rating_function(component_charge_record.units)
        # 2. how much has been invoiced already
        amt_already_invoiced = self.prepaid_already_invoiced()
        # 3. how much is left to invoice
        amt_left_to_invoice = total_amt - amt_already_invoiced
        return amt_left_to_invoice


class ComponentChargeRecord(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="component_charge_records"
    )
    billing_record = models.ForeignKey(
        BillingRecord,
        on_delete=models.CASCADE,
        related_name="component_charge_records",
    )
    component_charge = models.ForeignKey(
        ComponentFixedCharge,
        on_delete=models.CASCADE,
        related_name="component_charge_records",
    )
    component = models.ForeignKey(
        PlanComponent, on_delete=models.CASCADE, related_name="component_charge_records"
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    units = models.DecimalField(
        max_digits=20, decimal_places=10, validators=[MinValueValidator(Decimal(0))]
    )
    fully_billed = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        assert (
            self.component == self.component_charge.component
        ), "Component must match component charge"
        assert (
            self.billing_record.component == self.component
        ), "Component must match billing record"
        assert (
            self.billing_record.start_date
            <= self.start_date
            <= self.end_date
            <= self.billing_record.end_date
        ), "Start and end dates must be within the billing record"
        super().save(*args, **kwargs)


class Analysis(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="historical_analyses"
    )
    analysis_name = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField()
    time_created = models.DateTimeField(default=now_utc)
    analysis_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    kpis = ArrayField(models.TextField(choices=ANALYSIS_KPI.choices), default=list)
    analysis_results = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        choices=EXPERIMENT_STATUS.choices,
        default=EXPERIMENT_STATUS.RUNNING,
        max_length=40,
    )

    def save(self, *args, **kwargs):
        self.kpis = sorted(list(set(self.kpis)))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.analysis_name} - {self.start_date}"


class Backtest(models.Model):
    """
    This model is used to store the results of a backtest.
    """

    backtest_name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="backtests"
    )
    time_created = models.DateTimeField(default=now_utc)
    backtest_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    kpis = models.JSONField(default=list)
    backtest_results = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        choices=EXPERIMENT_STATUS.choices,
        default=EXPERIMENT_STATUS.RUNNING,
        max_length=40,
    )

    def __str__(self):
        return f"{self.backtest_name} - {self.start_date}"


class BacktestSubstitution(models.Model):
    """
    This model is used to substitute a backtest for a live trading session.
    """

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="backtest_substitutions",
        null=True,
    )
    backtest = models.ForeignKey(
        Backtest, on_delete=models.CASCADE, related_name="backtest_substitutions"
    )
    original_plan = models.ForeignKey(
        PlanVersion, on_delete=models.CASCADE, related_name="+"
    )
    new_plan = models.ForeignKey(
        PlanVersion, on_delete=models.CASCADE, related_name="+"
    )

    def __str__(self):
        return f"{self.backtest}"


class PricingUnit(models.Model):
    """
    This model is used to store pricing units for a plan.
    """

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="pricing_units",
    )
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10)
    custom = models.BooleanField(default=False)

    def __str__(self):
        ret = f"{self.code}"
        if self.symbol:
            ret += f"({self.symbol})"
        return ret

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["organization", "code"], name="unique_code_per_org"
            ),
            UniqueConstraint(
                fields=["organization", "name"], name="unique_name_per_org"
            ),
        ]


class CustomPricingUnitConversion(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="custom_pricing_unit_conversions",
        null=True,
    )
    plan_version = models.ForeignKey(
        PlanVersion, on_delete=models.CASCADE, related_name="pricing_unit_conversions"
    )
    from_unit = models.ForeignKey(
        PricingUnit, on_delete=models.CASCADE, related_name="+"
    )
    from_qty = models.DecimalField(
        max_digits=20, decimal_places=10, validators=[MinValueValidator(0)]
    )
    to_unit = models.ForeignKey(PricingUnit, on_delete=models.CASCADE, related_name="+")
    to_qty = models.DecimalField(
        max_digits=20, decimal_places=10, validators=[MinValueValidator(0)]
    )


class AccountsReceivableDebtor(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="+"
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="debtors"
    )
    currency = models.ForeignKey(
        PricingUnit, on_delete=models.CASCADE, related_name="+"
    )
    created = models.DateTimeField(default=now_utc)


class AccountsReceivableTransaction(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="+"
    )
    debtor = models.ForeignKey(
        AccountsReceivableDebtor, on_delete=models.CASCADE, related_name="transactions"
    )
    timestamp = models.DateTimeField(default=now_utc)
    transaction_type = models.PositiveSmallIntegerField(
        ACCOUNTS_RECEIVABLE_TRANSACTION_TYPES.choices,
    )
    due = models.DateTimeField(null=True)
    amount = models.DecimalField(max_digits=20, decimal_places=10)
    related_txns = models.ManyToManyField("self")


class Tag(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="tags"
    )
    tag_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    tag_name = models.CharField(max_length=50)
    tag_group = models.CharField(choices=TAG_GROUP.choices, max_length=15)
    tag_hex = models.CharField(max_length=7, null=True)
    tag_color = models.CharField(max_length=20, null=True)

    def __str__(self):
        return f"{self.tag_name} [{self.tag_group}]"

    constraints = [
        UniqueConstraint(
            fields=["organization", "tag_name", "tag_group"],
            name="unique_with_tag_group",
        ),
    ]


class UsageAlert(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="usage_alerts"
    )
    usage_alert_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    metric = models.ForeignKey(
        Metric, on_delete=models.CASCADE, related_name="usage_alerts"
    )
    plan_version = models.ForeignKey(
        PlanVersion, on_delete=models.CASCADE, related_name="usage_alerts"
    )
    threshold = models.DecimalField(max_digits=20, decimal_places=10)

    class Meta:
        constraints = []

    def save(self, *args, **kwargs):
        if self.metric.metric_type != METRIC_TYPE.COUNTER:
            raise ValidationError(
                "Only counter metrics can be used for alerts at this time"
            )
        super(UsageAlert, self).save(*args, **kwargs)
        active_sr = SubscriptionRecord.objects.active().filter(
            organization=self.organization,
            billing_plan=self.plan_version,
        )
        for subscription_record in active_sr:
            UsageAlertResult.objects.create(
                organization=self.organization,
                alert=self,
                subscription_record=subscription_record,
                last_run_value=0,
                last_run_timestamp=now_utc(),
            )


class UsageAlertResult(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="alert_results"
    )
    alert = models.ForeignKey(
        UsageAlert, on_delete=models.CASCADE, related_name="alert_results"
    )
    subscription_record = models.ForeignKey(
        SubscriptionRecord, on_delete=models.CASCADE, related_name="alert_results"
    )
    last_run_value = models.DecimalField(max_digits=20, decimal_places=10)
    last_run_timestamp = models.DateTimeField(default=now_utc)
    triggered_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["organization", "alert", "subscription_record"],
                name="unique_alert_result_per_org",
            ),
        ]

    def refresh(self):
        # calculate the value for the alert
        # update the last_run_value and last_run_timestamp
        # save the object

        metric = self.alert.metric
        subscription_record = self.subscription_record
        now = now_utc()
        billing_record = subscription_record.billing_records.filter(
            start_date__lte=now,
            end_date__gt=now,
            component__billable_metric=metric,
        ).first()
        new_value = metric.get_billing_record_total_billable_usage(billing_record)
        if (
            new_value >= self.alert.threshold
            and self.last_run_value < self.alert.threshold
        ):
            # send alert
            usage_alert_webhook(
                self.alert, self, subscription_record, self.organization
            )
            self.triggered_count = self.triggered_count + 1
        self.last_run_value = new_value
        self.last_run_timestamp = now
        self.save()


class StripeCustomerIntegration(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="stripe_customer_links"
    )
    stripe_customer_id = models.TextField()
    created = models.DateTimeField(default=now_utc)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["organization", "stripe_customer_id"],
                name="unique_stripe_customer_id",
            ),
        ]


class BraintreeCustomerIntegration(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="braintree_customer_links"
    )
    braintree_customer_id = models.TextField()
    created = models.DateTimeField(default=now_utc)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["organization", "braintree_customer_id"],
                name="unique_braintree_customer_id",
            ),
        ]


class StripeOrganizationIntegration(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="stripe_organization_links"
    )
    stripe_account_id = models.TextField()
    created = models.DateTimeField(default=now_utc)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["organization", "stripe_account_id"],
                name="unique_stripe_account_id",
            ),
        ]


class BraintreeOrganizationIntegration(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="braintree_organization_links",
    )
    braintree_merchant_id = models.TextField()
    created = models.DateTimeField(default=now_utc)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["organization", "braintree_merchant_id"],
                name="unique_braintree_merchant_id",
            ),
        ]


class UnifiedCRMOrganizationIntegration(models.Model):
    class CRMProvider(models.IntegerChoices):
        SALESFORCE = (1, "salesforce")

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="unified_crm_organization_links",
    )
    crm_provider = models.IntegerField(choices=CRMProvider.choices)
    access_token = models.TextField()
    native_org_url = models.TextField()
    native_org_id = models.TextField()
    connection_id = models.TextField()
    created = models.DateTimeField(default=now_utc)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=[
                    "organization",
                    "crm_provider",
                ],
                name="unique_crm_provider",
            ),
        ]

    @staticmethod
    def get_crm_provider_from_label(label):
        mapping = {
            UnifiedCRMOrganizationIntegration.CRMProvider.SALESFORCE.label: UnifiedCRMOrganizationIntegration.CRMProvider.SALESFORCE.value,
        }
        return mapping.get(label, label)

    def perform_sync(self):
        if (
            self.crm_provider
            == UnifiedCRMOrganizationIntegration.CRMProvider.SALESFORCE
        ):
            self.perform_salesforce_sync()
        else:
            raise NotImplementedError("CRM type not supported")

    def perform_salesforce_sync(self):
        from metering_billing.views.crm_views import (
            sync_customers_with_salesforce,
            sync_invoices_with_salesforce,
        )

        sync_customers_with_salesforce(self.organization)
        sync_invoices_with_salesforce(self.organization)


class UnifiedCRMCustomerIntegration(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="unified_crm_customer_links",
    )
    crm_provider = models.IntegerField(
        choices=UnifiedCRMOrganizationIntegration.CRMProvider.choices
    )
    native_customer_id = models.TextField(null=True)
    unified_account_id = models.TextField()

    def __str__(self):
        return f"[{self.get_crm_provider_display()}] {self.native_customer_id} - {self.unified_account_id}"

    class Meta:
        constraints = [
            UniqueConstraint(
                condition=Q(native_customer_id__isnull=False),
                fields=["organization", "crm_provider", "native_customer_id"],
                name="unique_crm_customer_id_per_type",
            ),
        ]

    def get_crm_url(self):
        if (
            self.crm_provider
            == UnifiedCRMOrganizationIntegration.CRMProvider.SALESFORCE
        ):
            if self.native_customer_id is None:
                return None
            objectType = "Account"
            objectId = self.native_customer_id
            nativeOrgURL = self.organization.unified_crm_organization_links.get(
                crm_provider=self.crm_provider
            ).native_org_url
            return f"{nativeOrgURL}/lightning/r/{objectType}/{objectId}/view"
        else:
            raise NotImplementedError("CRM type not supported")


class UnifiedCRMInvoiceIntegration(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="unified_crm_invoice_links",
    )
    crm_provider = models.IntegerField(
        choices=UnifiedCRMOrganizationIntegration.CRMProvider.choices
    )
    native_invoice_id = models.TextField(null=True)
    unified_note_id = models.TextField()

    def get_crm_url(self):
        if (
            self.crm_provider
            == UnifiedCRMOrganizationIntegration.CRMProvider.SALESFORCE
        ):
            if self.native_invoice_id is None:
                return None
            objectType = "Note"
            objectId = self.native_invoice_id
            nativeOrgURL = self.organization.unified_crm_organization_links.get(
                crm_provider=self.crm_provider
            ).native_org_url
            return f"{nativeOrgURL}/lightning/r/{objectType}/{objectId}/view"
        else:
            raise NotImplementedError("CRM type not supported")
