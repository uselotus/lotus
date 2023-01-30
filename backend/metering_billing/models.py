import datetime
import itertools
import logging
import math
import uuid
from decimal import Decimal
from typing import Literal, Optional, TypedDict, Union

# import lotus_python
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Count, F, FloatField, Q, Sum
from django.db.models.constraints import CheckConstraint, UniqueConstraint
from django.db.models.functions import Cast, Coalesce
from django.utils.translation import gettext_lazy as _
from metering_billing.exceptions.exceptions import (
    AlignmentEngineFailure,
    ExternalConnectionFailure,
    ExternalConnectionInvalid,
    NotEditable,
    OverlappingPlans,
    ServerError,
)
from metering_billing.utils import (
    calculate_end_date,
    convert_to_date,
    convert_to_decimal,
    customer_uuid,
    date_as_min_dt,
    dates_bwn_two_dts,
    event_uuid,
    now_plus_day,
    now_utc,
    periods_bwn_twodates,
    product_uuid,
)
from metering_billing.utils.enums import (
    ACCOUNTS_RECEIVABLE_TRANSACTION_TYPES,
    BACKTEST_STATUS,
    CATEGORICAL_FILTER_OPERATORS,
    CHARGEABLE_ITEM_TYPE,
    CUSTOMER_BALANCE_ADJUSTMENT_STATUS,
    EVENT_TYPE,
    FLAT_FEE_BEHAVIOR,
    FLAT_FEE_BILLING_TYPE,
    INVOICE_CHARGE_TIMING_TYPE,
    INVOICING_BEHAVIOR,
    MAKE_PLAN_VERSION_ACTIVE_TYPE,
    METRIC_AGGREGATION,
    METRIC_GRANULARITY,
    METRIC_STATUS,
    METRIC_TYPE,
    NUMERIC_FILTER_OPERATORS,
    ORGANIZATION_SETTING_GROUPS,
    ORGANIZATION_SETTING_NAMES,
    PAYMENT_PROVIDERS,
    PLAN_DURATION,
    PLAN_STATUS,
    PLAN_VERSION_STATUS,
    PRICE_ADJUSTMENT_TYPE,
    PRODUCT_STATUS,
    REPLACE_IMMEDIATELY_TYPE,
    SUPPORTED_CURRENCIES,
    SUPPORTED_CURRENCIES_VERSION,
    TAG_GROUP,
    USAGE_BILLING_FREQUENCY,
    USAGE_CALC_GRANULARITY,
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

logger = logging.getLogger("django.server")
META = settings.META
SVIX_CONNECTOR = settings.SVIX_CONNECTOR


class Team(models.Model):
    name = models.CharField(max_length=100, blank=False, null=False)
    team_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    def __str__(self):
        return self.name


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
    payment_provider_ids = models.JSONField(default=dict, blank=True, null=True)
    created = models.DateField(default=now_utc)
    organization_type = models.PositiveSmallIntegerField(
        choices=OrganizationType.choices, default=OrganizationType.DEVELOPMENT
    )
    default_currency = models.ForeignKey(
        "PricingUnit",
        on_delete=models.SET_NULL,
        related_name="organizations",
        null=True,
        blank=True,
    )
    webhooks_provisioned = models.BooleanField(default=False)
    currencies_provisioned = models.IntegerField(default=0)
    subscription_filters_setting_provisioned = models.BooleanField(default=False)
    properties = models.JSONField(default=dict, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
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
    history = HistoricalRecords()

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
        for k, v in self.payment_provider_ids.items():
            if k not in PAYMENT_PROVIDERS:
                raise ExternalConnectionInvalid(
                    f"Payment provider {k} is not supported. Supported payment providers are: {PAYMENT_PROVIDERS}"
                )
        new = self.pk is None
        (
            prev_organization_type,
            new_organization_type,
        ) = self.organization_type, kwargs.get(
            "organization_type", self.organization_type
        )
        if prev_organization_type != new_organization_type and self.pk:
            raise NotEditable(
                "Organization type cannot be changed once an organization is created."
            )
        if self.team is None:
            self.team = Team.objects.create(name=self.organization_name)
        super(Organization, self).save(*args, **kwargs)
        if new:
            self.provision_currencies()
        if not self.default_currency:
            self.default_currency = PricingUnit.objects.get(
                organization=self, code="USD"
            )
            self.save()
        self.provision_subscription_filter_settings()

    def provision_subscription_filter_settings(self):
        if not self.subscription_filters_setting_provisioned:
            OrganizationSetting.objects.create(
                organization=self,
                setting_name=ORGANIZATION_SETTING_NAMES.SUBSCRIPTION_FILTER_KEYS,
                setting_values=[],
            )
            self.subscription_filters_setting_provisioned = True
            self.save()

    def update_subscription_filter_settings(self, filter_keys):
        from metering_billing.aggregation.billable_metrics import METRIC_HANDLER_MAP

        if not self.subscription_filters_setting_provisioned:
            self.provision_subscription_filter_settings()
        try:
            setting = self.settings.get(
                setting_name=ORGANIZATION_SETTING_NAMES.SUBSCRIPTION_FILTER_KEYS
            )
        except OrganizationSetting.DoesNotExist:
            self.subscription_filters_setting_provisioned = False
            self.save()
            self.provision_subscription_filter_settings()
            setting = self.settings.get(
                setting_name=ORGANIZATION_SETTING_NAMES.SUBSCRIPTION_FILTER_KEYS
            )
        current_setting_values = set(setting.setting_values)
        new_setting_values = set(filter_keys)
        combined = sorted(list(current_setting_values.union(new_setting_values)))
        setting.setting_values = combined
        setting.save()
        for metric in self.metrics.all():
            METRIC_HANDLER_MAP[metric.metric_type].create_continuous_aggregate(
                metric, refresh=True
            )

    def provision_webhooks(self):
        if SVIX_CONNECTOR is not None:
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
        new = not self.pk
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


class Customer(models.Model):
    """
    Customer Model

    This model represents a customer.

    Attributes:
        name (str): The name of the customer.
        customer_id (str): A :model:`metering_billing.Organization`'s internal designation for the customer.
        payment_provider_id (str): The id of the payment provider the customer is using.
        properties (dict): An extendable dictionary of properties, useful for filtering, etc.
    """

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
    customer_id = models.SlugField(
        max_length=50,
        default=customer_uuid,
        help_text="The id provided when creating the customer, we suggest matching with your internal customer id in your backend",
    )
    payment_provider = models.CharField(
        blank=True, choices=PAYMENT_PROVIDERS.choices, max_length=40, null=True
    )
    integrations = models.JSONField(default=dict, blank=True)
    properties = models.JSONField(
        default=dict, null=True, help_text="Extra metadata for the customer"
    )
    default_currency = models.ForeignKey(
        "PricingUnit",
        on_delete=models.SET_NULL,
        related_name="customers",
        null=True,
        blank=True,
        help_text="The currency the customer will be invoiced in",
    )
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
    history = HistoricalRecords()

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
        for k, v in self.integrations.items():
            if k not in PAYMENT_PROVIDERS:
                raise ExternalConnectionInvalid(
                    f"Payment provider {k} is not supported. Supported payment providers are: {PAYMENT_PROVIDERS}"
                )
            id = v.get("id")
            if id is None:
                raise ExternalConnectionInvalid(
                    f"Payment provider {k} id was not provided"
                )
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
        Event.objects.filter(
            organization=self.organization,
            cust_id=self.customer_id,
            customer__isnull=True,
        ).update(customer=self)

    def get_subscription_and_records(self):
        now_utc()
        active_subscription = self.subscriptions.active().first()
        if active_subscription:
            active_subscription_records = self.subscription_records.filter(
                next_billing_date__range=(
                    active_subscription.start_date,
                    active_subscription.end_date,
                ),
                fully_billed=False,
            )
        else:
            active_subscription_records = None
        return active_subscription, active_subscription_records

    def get_usage_and_revenue(self):
        customer_subscriptions = (
            Subscription.objects.active()
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
        sub, sub_records = self.get_subscription_and_records()
        if sub is not None and sub_records is not None:
            invs = generate_invoice(
                sub,
                sub_records,
                draft=True,
                charge_next_plan=True,
            )
            total += sum([inv.cost_due for inv in invs])
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
            .aggregate(unpaid_inv_amount=Sum("cost_due"))
            .get("unpaid_inv_amount")
        )
        total_amount_due = unpaid_invoice_amount_due or 0
        return total_amount_due


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
        if self.pk:
            prev_amount, new_amount = self.amount, kwargs.get("amount", self.amount)
            prev_price_unit, new_price_unit = self.pricing_unit, kwargs.get(
                "pricing_unit", self.pricing_unit
            )
            prev_created, new_created = self.created, kwargs.get(
                "created", self.created
            )
            prev_effective_at, new_effective_at = self.effective_at, kwargs.get(
                "effective_at", self.effective_at
            )
            (
                prev_parent_adjustment,
                new_parent_adjustment,
            ) = self.parent_adjustment, kwargs.get(
                "parent_adjustment", self.parent_adjustment
            )
            prev_expires_at, new_expires_at = self.expires_at, kwargs.get(
                "expires_at", self.expires_at
            )
            if (
                prev_amount != new_amount
                or prev_price_unit != new_price_unit
                or prev_created != new_created
                or prev_effective_at != new_effective_at
                or prev_parent_adjustment != new_parent_adjustment
                or prev_expires_at != new_expires_at
            ):
                raise NotEditable(
                    "Cannot update any fields in a balance adjustment other than status and description"
                )
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
        if not self.pricing_unit:
            self.pricing_unit = self.customer.organization.default_currency
        if not self.organization:
            self.organization = self.customer.organization
        if self.amount_paid is None or self.amount_paid == 0:
            self.amount_paid_currency = None
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
    def draw_down_amount(customer, amount, description="", pricing_unit=None):
        if not pricing_unit:
            pricing_unit = customer.organization.default_currency
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
        )
        am = amount
        for adj in adjs:
            remaining_balance = adj.get_remaining_balance()
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
    def get_pricing_unit_balance(customer, pricing_unit=None):
        if not pricing_unit:
            pricing_unit = customer.organization.default_currency
        now = now_utc()
        adjs = CustomerBalanceAdjustment.objects.filter(
            Q(expires_at__gte=now) | Q(expires_at__isnull=True),
            organization=customer.organization,
            customer=customer,
            pricing_unit=pricing_unit,
            amount__gt=0,
        )
        total_balance = 0
        for adj in adjs:
            remaining_balance = adj.get_remaining_balance()
            total_balance += remaining_balance
        return total_balance


class Event(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.SET_NULL, related_name="+", null=True, blank=True
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="+", null=True, blank=True
    )
    cust_id = models.CharField(max_length=50, blank=True)
    event_name = models.CharField(
        max_length=100,
        help_text="String name of the event, corresponds to definition in metrics",
    )
    time_created = models.DateTimeField(
        help_text="The time that the event occured, represented as a datetime in ISO 8601 in the UTC timezome."
    )
    properties = models.JSONField(
        default=dict,
        blank=True,
        help_text="Extra metadata on the event that can be filtered and queried on in the metrics. All key value pairs should have string keys and values can be either strings or numbers. Place subscription filters in this object to specify which subscription the event should be tracked under",
    )
    idempotency_id = models.SlugField(
        max_length=255,
        default=event_uuid,
        help_text="A unique identifier for the specific event being passed in. Passing in a unique id allows Lotus to make sure no double counting occurs. We recommend using a UUID4. You can use the same idempotency_id again after 45 days.",
        primary_key=True,
    )
    inserted_at = models.DateTimeField(default=now_utc)

    class Meta:
        managed = False
        db_table = "metering_billing_usageevent"
        unique_together = ("idempotency_id", "time_created")
        indexes = [
            models.Index(
                fields=["organization", "event_name", "customer", "time_created"]
            ),
        ]

    def __str__(self):
        return (
            str(self.event_name)[:6]
            + "-"
            + str(self.customer.customer_name)[:6]
            + "-"
            + str(self.time_created)[:10]
            + "-"
            + str(self.idempotency_id)[:6]
        )


class OldEvent(models.Model):
    """
    Event object. An explanation of the Event's fields follows:
    event_name: The type of event that occurred.
    time_created: The time at which the event occurred.
    customer: The customer that the event occurred to.
    idempotency_id: A unique identifier for the event.
    """

    organization = models.ForeignKey(
        Organization, on_delete=models.SET_NULL, related_name="+", null=True, blank=True
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="+", null=True, blank=True
    )
    cust_id = models.CharField(max_length=50, null=True, blank=True)
    event_name = models.CharField(
        max_length=200,
        null=False,
        help_text="String name of the event, corresponds to definition in metrics",
    )
    time_created = models.DateTimeField(
        help_text="The time that the event occured, represented as a datetime in ISO 8601 in the UTC timezome."
    )
    properties = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        help_text="Extra metadata on the event that can be filtered and queried on in the metrics. All key value pairs should have string keys and values can be either strings or numbers. Place subscription filters in this object to specify which subscription the event should be tracked under",
    )
    idempotency_id = models.SlugField(
        max_length=255,
        default=event_uuid,
        help_text="A unique identifier for the specific event being passed in. Passing in a unique id allows Lotus to make sure no double counting occurs. We recommend using a UUID4. You can use the same idempotency_id again after 7 days",
    )
    inserted_at = models.DateTimeField(default=now_utc)

    class Meta:
        ordering = ["time_created", "idempotency_id"]

    def __str__(self):
        return str(self.event_name) + "-" + str(self.idempotency_id)


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
        if self.status == METRIC_STATUS.ACTIVE and not self.mat_views_provisioned:
            self.provision_materialized_views()

    def get_aggregation_type(self):
        return self.aggregation_type

    def get_subscription_record_total_billable_usage(self, subscription_record):
        from metering_billing.aggregation.billable_metrics import METRIC_HANDLER_MAP

        handler = METRIC_HANDLER_MAP[self.metric_type]
        usage = handler.get_subscription_record_total_billable_usage(
            self, subscription_record
        )

        return usage

    def get_subscription_record_daily_billable_usage(self, subscription_record):
        from metering_billing.aggregation.billable_metrics import METRIC_HANDLER_MAP

        handler = METRIC_HANDLER_MAP[self.metric_type]
        usage = handler.get_subscription_record_daily_billable_usage(
            self, subscription_record
        )

        return usage

    def get_subscription_record_current_usage(self, subscription_record):
        from metering_billing.aggregation.billable_metrics import METRIC_HANDLER_MAP

        handler = METRIC_HANDLER_MAP[self.metric_type]
        usage = handler.get_subscription_record_current_usage(self, subscription_record)

        return usage

    def get_daily_total_usage(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        customer: Optional[Customer] = None,
        top_n: Optional[int] = None,
    ) -> dict[Union[Customer, Literal["Other"]], dict[datetime.date, Decimal]]:
        from metering_billing.aggregation.billable_metrics import METRIC_HANDLER_MAP

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

    def delete_materialized_views(self):
        from metering_billing.aggregation.billable_metrics import METRIC_HANDLER_MAP

        handler = METRIC_HANDLER_MAP[self.metric_type]
        handler.archive_metric(self)
        self.mat_views_provisioned = False
        self.save()


class UsageRevenueSummary(TypedDict):
    revenue: Decimal
    usage_qty: Decimal


class PriceTier(models.Model):
    class PriceTierType(models.IntegerChoices):
        FLAT = (1, _("Flat"))
        PER_UNIT = (2, _("Per Unit"))
        FREE = (3, _("Free"))

    class BatchRoundingType(models.IntegerChoices):
        ROUND_UP = (1, _("Round Up"))
        ROUND_DOWN = (2, _("Round Down"))
        ROUND_NEAREST = (3, _("Round Nearest"))
        NO_ROUNDING = (4, _("No Rounding"))

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

    def calculate_revenue(self, usage: float, prev_tier_end=False):
        # if division_factor is None:
        #     division_factor = len(usage_dict)
        revenue = 0
        discontinuous_range = (
            prev_tier_end != self.range_start and prev_tier_end is not None
        )
        # for usage in usage_dict.values():
        usage = convert_to_decimal(usage)
        usage_in_range = (
            self.range_start <= usage
            if discontinuous_range
            else self.range_start < usage or self.range_start == 0
        )
        if usage_in_range:
            if self.type == PriceTier.PriceTierType.FLAT:
                revenue += self.cost_per_batch
            elif self.type == PriceTier.PriceTierType.PER_UNIT:
                if self.range_end is not None:
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


class PlanComponent(models.Model):
    organization = models.ForeignKey(
        "Organization",
        on_delete=models.CASCADE,
        related_name="plan_components",
        null=True,
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

    def __str__(self):
        return str(self.billable_metric)

    def save(self, *args, **kwargs):
        if self.pricing_unit is None and self.plan_version is not None:
            self.pricing_unit = self.plan_version.pricing_unit
        super().save(*args, **kwargs)

    def calculate_total_revenue(self, subscription_record) -> UsageRevenueSummary:
        billable_metric = self.billable_metric
        usage_qty = billable_metric.get_subscription_record_total_billable_usage(
            subscription_record
        )
        revenue = 0
        tiers = self.tiers.all()
        for i, tier in enumerate(tiers):
            if i > 0:
                # this is for determining whether this is a continuous or discontinuous range
                prev_tier_end = tiers[i - 1].range_end
                tier_revenue = tier.calculate_revenue(
                    usage_qty, prev_tier_end=prev_tier_end
                )
            else:
                tier_revenue = tier.calculate_revenue(usage_qty)
            revenue += tier_revenue
        revenue = convert_to_decimal(revenue)
        return {"revenue": revenue, "usage_qty": usage_qty}

    def calculate_revenue_per_day(
        self, subscription_record
    ) -> dict[datetime.datetime, UsageRevenueSummary]:
        billable_metric = self.billable_metric
        usage_per_day = billable_metric.get_subscription_record_daily_billable_usage(
            subscription_record
        )
        results = {}
        for period in dates_bwn_two_dts(
            subscription_record.usage_start_date, subscription_record.end_date
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
        DRAFT = (1, _("Draft"))
        VOIDED = (2, _("Voided"))
        PAID = (3, _("Paid"))
        UNPAID = (4, _("Unpaid"))

    cost_due = models.DecimalField(
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
    external_payment_obj_id = models.CharField(max_length=100, blank=True, null=True)
    external_payment_obj_type = models.CharField(
        choices=PAYMENT_PROVIDERS.choices, max_length=40, blank=True, null=True
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invoices", null=True
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, null=True, related_name="invoices"
    )
    subscription = models.ForeignKey(
        "Subscription",
        on_delete=models.SET_NULL,
        null=True,
        related_name="invoices",
    )
    history = HistoricalRecords()

    class Meta:
        indexes = [
            models.Index(fields=["organization", "payment_status"]),
            models.Index(fields=["organization", "customer"]),
            models.Index(fields=["organization", "invoice_number"]),
            models.Index(fields=["organization", "invoice_id"]),
            models.Index(fields=["organization", "external_payment_obj_id"]),
            models.Index(fields=["organization", "subscription", "-issue_date"]),
        ]

    def __str__(self):
        return str(self.invoice_number)

    def save(self, *args, **kwargs):
        if not self.currency:
            self.currency = self.organization.default_currency

        ### Generate invoice number
        if not self.pk and self.payment_status != Invoice.PaymentStatus.DRAFT:
            today = now_utc().date()
            today_string = today.strftime("%y%m%d")
            next_invoice_number = "000001"
            last_invoice = (
                Invoice.objects.filter(
                    invoice_number__startswith=today_string,
                    organization=self.organization,
                )
                .order_by("invoice_number")
                .last()
            )
            if last_invoice:
                last_invoice_number = int(last_invoice.invoice_number[7:])
                next_invoice_number = "{0:06d}".format(last_invoice_number + 1)

            self.invoice_number = today_string + "-" + next_invoice_number
            # if not self.due_date:
            #     self.due_date = self.issue_date + datetime.timedelta(days=1)
        paid_before = self.payment_status == Invoice.PaymentStatus.PAID
        super().save(*args, **kwargs)
        paid_after = self.payment_status == Invoice.PaymentStatus.PAID
        if not paid_before and paid_after and self.cost_due > 0:
            invoice_paid_webhook(self, self.organization)


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
    subtotal = models.DecimalField(
        decimal_places=10, max_digits=20, default=Decimal(0.0)
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
    associated_subscription_record = models.ForeignKey(
        "SubscriptionRecord",
        on_delete=models.SET_NULL,
        null=True,
        related_name="line_items",
    )
    associated_plan_version = models.ForeignKey(
        "PlanVersion",
        on_delete=models.SET_NULL,
        null=True,
        related_name="line_items",
    )
    metadata = models.JSONField(default=dict, blank=True, null=True)

    def __str__(self):
        return self.name + " " + str(self.invoice.invoice_number) + f"[{self.subtotal}]"

    def save(self, *args, **kwargs):
        if not self.pricing_unit:
            self.pricing_unit = self.invoice.organization.default_currency
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


class PlanVersion(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="plan_versions",
    )
    description = models.TextField(null=True, blank=True)
    version = models.PositiveSmallIntegerField()
    flat_fee_billing_type = models.CharField(
        max_length=40, choices=FLAT_FEE_BILLING_TYPE.choices, null=True, blank=True
    )
    usage_billing_frequency = models.CharField(
        max_length=40, choices=USAGE_BILLING_FREQUENCY.choices, null=True, blank=True
    )
    plan = models.ForeignKey("Plan", on_delete=models.CASCADE, related_name="versions")
    status = models.CharField(max_length=40, choices=PLAN_VERSION_STATUS.choices)
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
    flat_rate = models.DecimalField(
        decimal_places=10,
        max_digits=20,
        default=Decimal(0),
        validators=[MinValueValidator(0)],
    )
    features = models.ManyToManyField(Feature, blank=True)
    price_adjustment = models.ForeignKey(
        "PriceAdjustment", on_delete=models.SET_NULL, null=True, blank=True
    )
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
    created_on = models.DateTimeField(default=now_utc)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="created_plan_versions",
        null=True,
        blank=True,
    )
    version_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    pricing_unit = models.ForeignKey(
        "PricingUnit",
        on_delete=models.SET_NULL,
        related_name="versions",
        null=True,
        blank=True,
    )
    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "version"], name="unique_plan_version"
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "status", "plan"]),
            models.Index(fields=["organization", "version_id"]),
        ]

    def __str__(self) -> str:
        return str(self.plan) + " v" + str(self.version)

    def num_active_subs(self):
        cnt = self.subscription_records.active().count()
        return cnt

    def save(self, *args, **kwargs):
        version_usage_billing_frequency = self.usage_billing_frequency
        plan_duration = self.plan.plan_duration
        if plan_duration == PLAN_DURATION.MONTHLY:
            if version_usage_billing_frequency == USAGE_BILLING_FREQUENCY.QUARTERLY:
                version_usage_billing_frequency = USAGE_BILLING_FREQUENCY.MONTHLY
            elif version_usage_billing_frequency == USAGE_BILLING_FREQUENCY.MONTHLY:
                version_usage_billing_frequency = USAGE_BILLING_FREQUENCY.END_OF_PERIOD
        elif plan_duration == PLAN_DURATION.QUARTERLY:
            if version_usage_billing_frequency == USAGE_BILLING_FREQUENCY.QUARTERLY:
                version_usage_billing_frequency = USAGE_BILLING_FREQUENCY.END_OF_PERIOD
        self.usage_billing_frequency = version_usage_billing_frequency
        if not self.pricing_unit:
            if self.organization.default_currency:
                self.pricing_unit = self.organization.default_currency
            else:
                self.pricing_unit = PricingUnit.objects.get(
                    organization=self.organization, code="USD"
                )
        super().save(*args, **kwargs)


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


class BasePlanManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(addon_spec__isnull=True)


class AddOnPlanManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(addon_spec__isnull=False)


class BillingFrequency(models.IntegerChoices):
    ONE_TIME = (1, _("one_time"))
    RECURRING = (2, _("recurring"))


class FlatFeeInvoicingBehaviorOnAttach(models.IntegerChoices):
    INVOICE_ON_ATTACH = (1, _("invoice_on_attach"))
    INVOICE_ON_SUBSCRIPTION_END = (2, _("invoice_on_subscription_end"))


class RecurringFlatFeeTiming(models.IntegerChoices):
    IN_ADVANCE = (1, _("in_advance"))
    IN_ARREARS = (2, _("in_arrears"))


class AddOnSpecification(models.Model):
    BillingFrequency = BillingFrequency
    FlatFeeInvoicingBehaviorOnAttach = FlatFeeInvoicingBehaviorOnAttach
    RecurringFlatFeeTiming = RecurringFlatFeeTiming

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
    recurring_flat_fee_timing = models.PositiveSmallIntegerField(
        choices=RecurringFlatFeeTiming.choices,
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=Q(
                    recurring_flat_fee_timing__isnull=True,
                    billing_frequency=BillingFrequency.ONE_TIME,
                )
                | Q(
                    recurring_flat_fee_timing__isnull=False,
                    billing_frequency=BillingFrequency.RECURRING,
                ),
                name="billing_frequency_one_time_recurring_flat_fee_timing_isnull",
            ),
        ]


class Plan(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="plans"
    )
    plan_name = models.CharField(max_length=100, help_text="Name of the plan")
    plan_duration = models.CharField(
        choices=PLAN_DURATION.choices,
        max_length=40,
        help_text="Duration of the plan",
        null=True,
    )
    display_version = models.ForeignKey(
        "PlanVersion",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
        help_text="The currently active version of the plan. Customers that get signed up for this plan will be assigned this version.",
    )
    parent_product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="product_plans",
        null=True,
        blank=True,
        help_text="The product that this plan belongs to",
    )
    status = models.CharField(
        choices=PLAN_STATUS.choices, max_length=40, default=PLAN_STATUS.ACTIVE
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
    parent_plan = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="child_plans",
        help_text="If you are using our plan templating feature to create a new plan, this field will be set to the plan that you are using as a template.",
    )
    target_customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custom_plans",
        help_text="If you are using our plan templating feature to create a new plan, this field will be set to the customer for which this plan is designed for. Keep in mind that this field and the parent_plan field are mutually necessary.",
    )
    addon_spec = models.OneToOneField(
        AddOnSpecification, on_delete=models.CASCADE, null=True, blank=True
    )
    tags = models.ManyToManyField("Tag", blank=True, related_name="plans")
    created_on = models.DateTimeField(default=now_utc, null=True)

    objects = BasePlanManager()
    addons = AddOnPlanManager()

    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        if not self.pk and self.target_customer:
            self.plan_name = (
                self.plan_name or "" + " - " + self.target_customer.customer_name or ""
            )
        if not self.created_on:
            self.created_on = now_utc()
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(Q(parent_plan__isnull=True) & Q(target_customer__isnull=True))
                | Q(parent_plan__isnull=False) & Q(target_customer__isnull=False),
                name="both_null_or_both_not_null",
            )
        ]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "plan_id"]),
        ]

    def __str__(self):
        return f"{self.plan_name}"

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

    def make_version_active(
        self, plan_version, make_active_type=None, replace_immediately_type=None
    ):
        self._handle_existing_versions(
            plan_version, make_active_type, replace_immediately_type
        )
        self.display_version = plan_version
        self.save()
        if plan_version.status != PLAN_VERSION_STATUS.ACTIVE:
            plan_version.status = PLAN_VERSION_STATUS.ACTIVE
            plan_version.save()

    def _handle_existing_versions(
        self, new_version, make_active_type, replace_immediately_type
    ):
        # To dos:
        # 1. make retiring plans update to new version
        # 2a. if on renewal, update active plan to be retiring w/ new version replacing
        # 2b. if grandfather, grandfather currently active plan
        # 2c. if immediataely, then go through immediate replacement flow
        if make_active_type in [
            MAKE_PLAN_VERSION_ACTIVE_TYPE.REPLACE_ON_ACTIVE_VERSION_RENEWAL,
            MAKE_PLAN_VERSION_ACTIVE_TYPE.GRANDFATHER_ACTIVE,
        ]:
            # 1
            replace_with_lst = [PLAN_VERSION_STATUS.RETIRING]
            # 2a
            if (
                make_active_type
                == MAKE_PLAN_VERSION_ACTIVE_TYPE.REPLACE_ON_ACTIVE_VERSION_RENEWAL
            ):
                replace_with_lst.append(PLAN_VERSION_STATUS.ACTIVE)
            now = now_utc()
            versions_to_replace = (
                self.versions.all()
                .filter(~Q(pk=new_version.pk), status__in=replace_with_lst)
                .annotate(
                    active_subscriptions=Count(
                        "subscription_record",
                        filter=Q(
                            subscription_record__start_date__lte=now,
                            subscription_record__end_date__gte=now,
                        ),
                        output_field=models.IntegerField(),
                    )
                )
            )
            inactive = versions_to_replace.filter(active_subscriptions=0)
            retiring = versions_to_replace.filter(active_subscriptions__gt=0)
            inactive.query.annotations.clear()
            retiring.query.annotations.clear()
            inactive.filter().update(status=PLAN_VERSION_STATUS.INACTIVE)
            retiring.filter().update(status=PLAN_VERSION_STATUS.RETIRING)
            # 2b
            if make_active_type == MAKE_PLAN_VERSION_ACTIVE_TYPE.GRANDFATHER_ACTIVE:
                prev_active = self.versions.all().get(
                    ~Q(pk=new_version.pk), status=PLAN_VERSION_STATUS.ACTIVE
                )
                if prev_active.num_active_subs() > 0:
                    prev_active.status = PLAN_VERSION_STATUS.GRANDFATHERED
                else:
                    prev_active.status = PLAN_VERSION_STATUS.INACTIVE
                prev_active.save()
        else:
            # 2c
            versions = (
                self.versions.all()
                .filter(
                    ~Q(pk=new_version.pk),
                    status__in=[
                        PLAN_VERSION_STATUS.ACTIVE,
                        PLAN_VERSION_STATUS.RETIRING,
                    ],
                )
                .prefetch_related("subscription_records")
            )
            versions.update(status=PLAN_VERSION_STATUS.INACTIVE, replace_with=None)
            for version in versions:
                for sub in version.subscription_records.active():
                    if (
                        replace_immediately_type
                        == REPLACE_IMMEDIATELY_TYPE.CHANGE_SUBSCRIPTION_PLAN
                    ):
                        sub.switch_subscription_bp(billing_plan=new_version)
                    else:
                        bill_usage = (
                            REPLACE_IMMEDIATELY_TYPE.END_CURRENT_SUBSCRIPTION_AND_BILL
                        )
                        sub.end_subscription_now(
                            bill_usage=bill_usage,
                            flat_fee_behavior=FLAT_FEE_BEHAVIOR.PRORATE,
                        )
                        Subscription.objects.create(
                            billing_plan=new_version,
                            organization=self.organization,
                            customer=sub.customer,
                            start_date=sub.end_date,
                            auto_renew=True,
                            is_new=False,
                        )


class ExternalPlanLink(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="external_plan_links",
    )
    plan = models.ForeignKey(
        Plan, on_delete=models.CASCADE, related_name="external_links"
    )
    source = models.CharField(choices=PAYMENT_PROVIDERS.choices, max_length=40)
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


class SubscriptionManager(models.Manager):
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


class Subscription(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="subscriptions", null=True
    )
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
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        null=False,
        related_name="subscriptions",
    )
    billing_cadence = models.CharField(
        choices=PLAN_DURATION.choices,
        max_length=20,
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    subscription_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    objects = SubscriptionManager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=Q(start_date__lte=F("end_date")),
                name="start_date_less_than_end_date",
            ),
            models.UniqueConstraint(
                fields=["customer", "start_date", "end_date"],
                name="unique_customer_start_end_date",
            ),
        ]
        indexes = [
            models.Index(fields=["-end_date"]),
            models.Index(fields=["organization", "customer", "start_date", "end_date"]),
        ]

    def __str__(self):
        return f"{self.customer.id} [{self.start_date}, {self.end_date}] - {self.subscription_id}"

    def save(self, *args, **kwargs):
        if not self.pk:
            overlapping_subscriptions = Subscription.objects.filter(
                Q(start_date__range=(self.start_date, self.end_date))
                | Q(end_date__range=(self.start_date, self.end_date)),
                organization=self.organization,
                customer=self.customer,
            )
            if overlapping_subscriptions.exists():
                logger.error(
                    "Overlapping subscriptions found. Subscription that was trying to be created had start date of %s and end date of %s, customer id %s, and organization id %s. Overlapping subscriptions: %s",
                    self.start_date,
                    self.end_date,
                    self.customer.id,
                    self.organization.id,
                    overlapping_subscriptions,
                )
                raise AlignmentEngineFailure(
                    "An unexpected error in the alignment engine has occurred. Please contact support."
                )
        super(Subscription, self).save(*args, **kwargs)

    def get_anchors(self):
        return self.day_anchor, self.month_anchor

    def handle_attach_plan(
        self,
        plan_day_anchor=None,
        plan_month_anchor=None,
        plan_start_date=None,
        plan_duration=None,
        plan_billing_frequency=None,
    ):
        if self.day_anchor is None:
            if plan_day_anchor is not None:
                self.day_anchor = plan_day_anchor
            else:
                self.day_anchor = plan_start_date.day
        if self.month_anchor is None:
            if plan_month_anchor is not None:
                self.month_anchor = plan_month_anchor
            elif plan_duration in [
                PLAN_DURATION.YEARLY,
                PLAN_DURATION.QUARTERLY,
            ]:
                self.month_anchor = plan_start_date.month
        if plan_billing_frequency in [USAGE_BILLING_FREQUENCY.END_OF_PERIOD, None]:
            if self.billing_cadence is None or self.billing_cadence == "":
                self.billing_cadence = plan_duration
            elif self.billing_cadence == PLAN_DURATION.QUARTERLY:
                if plan_duration == PLAN_DURATION.MONTHLY:
                    self.billing_cadence = PLAN_DURATION.MONTHLY
            elif self.billing_cadence == PLAN_DURATION.YEARLY:
                if plan_duration in [PLAN_DURATION.MONTHLY, PLAN_DURATION.QUARTERLY]:
                    self.billing_cadence = plan_duration
        else:
            if plan_billing_frequency == USAGE_BILLING_FREQUENCY.MONTHLY:
                self.billing_cadence = PLAN_DURATION.MONTHLY
            elif plan_billing_frequency == USAGE_BILLING_FREQUENCY.QUARTERLY:
                if self.billing_cadence in [PLAN_DURATION.YEARLY, None, ""]:
                    self.billing_cadence = PLAN_DURATION.QUARTERLY
        new_end_date = calculate_end_date(
            self.billing_cadence,
            self.start_date,
            day_anchor=self.day_anchor,
            month_anchor=self.month_anchor,
        )
        self.end_date = new_end_date
        self.save()

    def handle_remove_plan(self):
        active_sub_records = self.customer.subscription_records.active()

        active_subs_with_yearly_quarterly = active_sub_records.filter(
            billing_plan__plan__plan_duration__in=[
                PLAN_DURATION.YEARLY,
                PLAN_DURATION.QUARTERLY,
            ]
        )
        if active_sub_records.count() == 0:
            self.day_anchor = None
            self.month_anchor = None
            self.end_date = now_utc()
            self.save()
            return
        if active_subs_with_yearly_quarterly.count() == 0:
            self.month_anchor = None
        remaining_durations = active_sub_records.values_list(
            "billing_plan__plan__plan_duration", flat=True
        ).distinct()
        remaining_usage_billing_freqs = active_sub_records.values_list(
            "billing_plan__usage_billing_frequency", flat=True
        ).distinct()
        if (
            PLAN_DURATION.MONTHLY in remaining_durations
            or USAGE_BILLING_FREQUENCY.MONTHLY in remaining_usage_billing_freqs
        ):
            self.billing_cadence = PLAN_DURATION.MONTHLY
        elif (
            PLAN_DURATION.QUARTERLY in remaining_durations
            or USAGE_BILLING_FREQUENCY.QUARTERLY in remaining_usage_billing_freqs
        ):
            self.billing_cadence = PLAN_DURATION.QUARTERLY
        else:
            self.billing_cadence = PLAN_DURATION.YEARLY
        new_end_date = calculate_end_date(
            self.billing_cadence,
            self.start_date,
            day_anchor=self.day_anchor,
            month_anchor=self.month_anchor,
        )
        num_before = active_sub_records.filter(
            next_billing_date__lt=new_end_date
        ).count()
        if num_before == 0:
            self.end_date = new_end_date
        self.save()

    def get_subscription_records(self):
        return self.customer.subscription_records.active().filter(
            Q(last_billing_date__range=(self.start_date, self.end_date))
            | Q(end_date__range=(self.start_date, self.end_date))
            | Q(start_date__lte=self.start_date, end_date__gte=self.end_date),
        )

    def get_subscription_records_to_bill(self):
        return self.customer.subscription_records.filter(
            Q(last_billing_date__range=(self.start_date, self.end_date))
            | Q(end_date__range=(self.start_date, self.end_date)),
            fully_billed=False,
        )

    def get_new_sub_end_date(self):
        new_date = date_as_min_dt(self.end_date + relativedelta(days=1))
        return calculate_end_date(
            self.billing_cadence, new_date, self.day_anchor, self.month_anchor
        )


class SubscriptionRecordManager(models.Manager):
    def create_with_filters(self, *args, **kwargs):
        subscription_filters = kwargs.pop("subscription_filters", [])
        sr = self.model(**kwargs)
        sr.save(subscription_filters=subscription_filters)
        return sr

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
        return (
            super().get_queryset().filter(billing_plan__plan__addon_spec__isnull=True)
        )


class AddOnSubscriptionRecordManager(SubscriptionRecordManager):
    def get_queryset(self):
        return (
            super().get_queryset().filter(billing_plan__plan__addon_spec__isnull=False)
        )


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
        null=False,
        related_name="subscription_records",
        related_query_name="subscription_record",
        help_text="The plan associated with this subscription.",
    )
    usage_start_date = models.DateTimeField(null=True, blank=True)
    start_date = models.DateTimeField(
        help_text="The time the subscription starts. This will be a string in yyyy-mm-dd HH:mm:ss format in UTC time."
    )
    next_billing_date = models.DateTimeField(null=True, blank=True)
    last_billing_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(
        help_text="The time the subscription starts. This will be a string in yyyy-mm-dd HH:mm:ss format in UTC time."
    )
    unadjusted_duration_seconds = models.PositiveIntegerField(null=True, blank=True)
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
    filters = models.ManyToManyField(
        CategoricalFilter,
        blank=True,
        help_text="Add filter key, value pairs that define which events will be applied to this plan subscription.",
    )
    invoice_usage_charges = models.BooleanField(default=True)
    flat_fee_behavior = models.CharField(
        choices=FLAT_FEE_BEHAVIOR.choices,
        max_length=20,
        default=FLAT_FEE_BEHAVIOR.PRORATE,
    )
    fully_billed = models.BooleanField(
        default=False,
        help_text="Whether the subscription has been fully billed and finalized.",
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
    objects = SubscriptionRecordManager()
    addon_objects = AddOnSubscriptionRecordManager()
    base_objects = BaseSubscriptionRecordManager()
    history = HistoricalRecords()

    class Meta:
        constraints = [
            CheckConstraint(
                check=Q(start_date__lte=F("end_date")), name="end_date_gte_start_date"
            ),
        ]

    def __str__(self):
        addon = "[ADDON] " if self.billing_plan.plan.addon_spec else ""
        return f"{addon}{self.customer.customer_name}  {self.billing_plan.plan.plan_name} : {self.start_date.date()} to {self.end_date.date()}"

    def save(self, *args, **kwargs):
        new_filters = kwargs.pop("subscription_filters", [])
        now = now_utc()
        subscription = self.customer.subscriptions.active(self.start_date).first()
        if not subscription:
            raise ServerError(
                "Unexpected error: subscription date alignment engine failed."
            )
        if not self.end_date:
            day_anchor, month_anchor = subscription.get_anchors()
            self.end_date = calculate_end_date(
                self.billing_plan.plan.plan_duration,
                self.start_date,
                day_anchor=day_anchor,
                month_anchor=month_anchor,
            )
        if not self.unadjusted_duration_seconds:
            scheduled_end_date = calculate_end_date(
                self.billing_plan.plan.plan_duration,
                self.start_date,
            )
            self.unadjusted_duration_seconds = (
                scheduled_end_date - self.start_date
            ).total_seconds()
        if not self.next_billing_date or self.next_billing_date < now:
            if self.billing_plan.usage_billing_frequency in [
                USAGE_BILLING_FREQUENCY.END_OF_PERIOD,
                None,
            ]:
                self.next_billing_date = self.end_date
            else:
                num_months = (
                    1
                    if self.billing_plan.usage_billing_frequency
                    == USAGE_BILLING_FREQUENCY.MONTHLY
                    else 3
                )
                if self.last_billing_date:
                    self.next_billing_date = min(
                        self.end_date,
                        self.last_billing_date + relativedelta(months=num_months),
                    )
                else:
                    self.next_billing_date = min(
                        self.end_date,
                        self.start_date + relativedelta(months=num_months),
                    )
        if not self.usage_start_date:
            self.usage_start_date = self.start_date
        new = not self.pk
        if new:
            overlapping_subscriptions = SubscriptionRecord.objects.filter(
                Q(start_date__range=(self.start_date, self.end_date))
                | Q(end_date__range=(self.start_date, self.end_date)),
                organization=self.organization,
                customer=self.customer,
                billing_plan=self.billing_plan,
            )
            for subscription in overlapping_subscriptions:
                old_filters = subscription.filters.all()
                if (
                    len(old_filters) == 0
                    or len(new_filters) == 0
                    or set(old_filters) == set(new_filters)
                ):
                    raise OverlappingPlans(
                        f"Overlapping subscriptions with the same filters are not allowed. \n Plan: {self.billing_plan} \n Customer: {self.customer}. \n New dates: ({self.start_date, self.end_date}) \n New subscription_filters: {new_filters} \n Old dates: ({self.start_date, self.end_date}) \n Old subscription_filters: {list(old_filters)}"
                    )
        super(SubscriptionRecord, self).save(*args, **kwargs)
        for filter in new_filters:
            self.filters.add(filter)
        for filter in self.filters.all():
            if not filter.organization:
                filter.organization = self.organization
                filter.save()
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
        filters_dict = {}
        for filter in self.filters.all():
            filters_dict[filter.property_name] = filter.comparison_value[0]
        return filters_dict

    def amount_already_invoiced(self):
        billed_invoices = self.line_items.filter(
            ~Q(invoice__payment_status=Invoice.PaymentStatus.VOIDED)
            & ~Q(invoice__payment_status=Invoice.PaymentStatus.DRAFT),
            subtotal__isnull=False,
        ).aggregate(tot=Sum("subtotal"))["tot"]
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
        sub_dict["flat_amount_due"] = plan.flat_rate
        sub_dict["total_amount_due"] = (
            sub_dict["flat_amount_due"] + sub_dict["usage_amount_due"]
        )
        return sub_dict

    def end_subscription_now(
        self,
        bill_usage=True,
        flat_fee_behavior=FLAT_FEE_BEHAVIOR.CHARGE_FULL,
    ):
        now = now_utc()
        if self.end_date <= now:
            logger.info("Subscription already ended.")
            return
        self.flat_fee_behavior = flat_fee_behavior
        self.invoice_usage_charges = bill_usage
        self.auto_renew = False
        self.end_date = now
        self.save()

    def turn_off_auto_renew(self):
        self.auto_renew = False
        self.save()

    def switch_subscription_bp(
        self, new_version, invoicing_behavior=INVOICING_BEHAVIOR.INVOICE_NOW
    ):
        now = now_utc()
        SubscriptionRecord.objects.create(
            organization=self.organization,
            customer=self.customer,
            billing_plan=new_version,
            start_date=now,
            end_date=self.end_date,
            auto_renew=self.auto_renew,
            unadjusted_duration_seconds=self.unadjusted_duration_seconds,
        )
        self.end_date = now
        self.auto_renew = False
        self.save()

    def calculate_earned_revenue_per_day(self):
        return_dict = {}
        for period in periods_bwn_twodates(
            USAGE_CALC_GRANULARITY.DAILY, self.start_date, self.end_date
        ):
            period = convert_to_date(period)
            return_dict[period] = Decimal(0)
            return_dict[period] += convert_to_decimal(
                self.billing_plan.flat_rate
                / self.unadjusted_duration_seconds
                * 60
                * 60
                * 24
            )
        for component in self.billing_plan.plan_components.all():
            rev_per_day = component.calculate_revenue_per_day(self)
            for period, d in rev_per_day.items():
                period = convert_to_date(period)
                d["usage_qty"]
                revenue = d["revenue"]
                if period in return_dict:
                    return_dict[period] += revenue
        return return_dict


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
        choices=BACKTEST_STATUS.choices,
        default=BACKTEST_STATUS.RUNNING,
        max_length=40,
    )
    history = HistoricalRecords()

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
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.backtest}"


class OrganizationSetting(models.Model):
    """
    This model is used to store settings for an organization.
    """

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="settings"
    )
    setting_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    setting_name = models.CharField(
        choices=ORGANIZATION_SETTING_NAMES.choices, max_length=64
    )
    setting_values = models.JSONField(default=dict, blank=True)
    setting_group = models.CharField(
        choices=ORGANIZATION_SETTING_GROUPS.choices,
        blank=True,
        null=True,
        max_length=64,
    )
    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        super(OrganizationSetting, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.setting_name} - {self.setting_values}"

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=[
                    "organization",
                    "setting_name",
                    "setting_group",
                ],
                name="unique_with_group",
            ),
            UniqueConstraint(
                fields=[
                    "organization",
                    "setting_name",
                ],
                condition=Q(setting_group=None),
                name="unique_without_group",
            ),
        ]


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
        new_value = metric.get_subscription_record_total_billable_usage(
            subscription_record
        )
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
        self.save()
