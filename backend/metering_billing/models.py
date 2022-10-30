import datetime
import uuid
from decimal import Decimal
from typing import TypedDict

from dateutil import parser
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Count, Q
from django.db.models.constraints import UniqueConstraint
from djmoney.models.fields import MoneyField
from metering_billing.invoice import generate_invoice
from metering_billing.utils import (
    btst_uuid,
    calculate_end_date,
    convert_to_decimal,
    cust_uuid,
    dates_bwn_two_dts,
    metric_uuid,
    now_plus_day,
    now_utc,
    periods_bwn_twodates,
    plan_uuid,
    prod_uuid,
    subs_uuid,
    vers_uuid,
)
from metering_billing.utils.enums import (
    BACKTEST_STATUS,
    CATEGORICAL_FILTER_OPERATORS,
    FLAT_FEE_BILLING_TYPE,
    INVOICE_STATUS,
    MAKE_PLAN_VERSION_ACTIVE_TYPE,
    METRIC_AGGREGATION,
    METRIC_TYPE,
    NUMERIC_FILTER_OPERATORS,
    PAYMENT_PLANS,
    PAYMENT_PROVIDERS,
    PLAN_DURATION,
    PLAN_STATUS,
    PLAN_VERSION_STATUS,
    PRICE_ADJUSTMENT_TYPE,
    PRODUCT_STATUS,
    PRORATION_GRANULARITY,
    REPLACE_IMMEDIATELY_TYPE,
    REVENUE_CALC_GRANULARITY,
    SUBSCRIPTION_STATUS,
    USAGE_BILLING_FREQUENCY,
)
from rest_framework_api_key.models import AbstractAPIKey
from simple_history.models import HistoricalRecords
from sqlalchemy import ForeignKey


class Organization(models.Model):
    company_name = models.CharField(max_length=100, blank=False, null=False)
    payment_provider_ids = models.JSONField(default=dict, blank=True, null=True)
    created = models.DateField(default=now_utc)
    payment_plan = models.CharField(
        max_length=40,
        choices=PAYMENT_PLANS.choices,
        default=PAYMENT_PLANS.SELF_HOSTED_FREE,
    )
    history = HistoricalRecords()

    def __str__(self):
        return self.company_name

    def save(self, *args, **kwargs):
        for k, _ in self.payment_provider_ids.items():
            if k not in PAYMENT_PROVIDERS:
                raise ValueError(
                    f"Payment provider {k} is not supported. Supported payment providers are: {PAYMENT_PROVIDERS}"
                )
        super(Organization, self).save(*args, **kwargs)

    @property
    def users(self):
        return self.org_users


class Alert(models.Model):
    type = models.CharField(max_length=20, default="webhook")
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="org_alerts"
    )
    webhook_url = models.CharField(max_length=300, blank=True, null=True)
    name = models.CharField(max_length=100, default=" ")
    history = HistoricalRecords()


class User(AbstractUser):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="org_users",
    )
    email = models.EmailField(unique=True)
    history = HistoricalRecords()


class Product(models.Model):
    """
    This model is used to store the products that are available to be purchased.
    """

    name = models.CharField(max_length=100, null=False, blank=False)
    description = models.TextField(null=True, blank=True)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="org_products"
    )
    product_id = models.CharField(default=prod_uuid, max_length=100, unique=True)
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
        Organization, on_delete=models.CASCADE, null=False, related_name="org_customers"
    )
    name = models.CharField(max_length=100)
    email = models.EmailField(max_length=100, blank=True, null=True)
    customer_id = models.CharField(
        max_length=50, blank=True, null=False, default=cust_uuid
    )
    integrations = models.JSONField(default=dict, blank=True, null=True)
    properties = models.JSONField(default=dict, blank=True, null=True)
    balance = MoneyField(
        decimal_places=10, max_digits=20, default_currency="USD", default=0.0
    )
    history = HistoricalRecords()

    class Meta:
        unique_together = ("organization", "customer_id")

    def __str__(self) -> str:
        return str(self.name) + " " + str(self.customer_id)

    def save(self, *args, **kwargs):
        for k, v in self.integrations.items():
            if k not in PAYMENT_PROVIDERS:
                raise ValueError(
                    f"Payment provider {k} is not supported. Supported payment providers are: {PAYMENT_PROVIDERS}"
                )
            id = v.get("id")
            if id is None:
                raise ValueError(f"Payment provider {k} id was not provided")
        super(Customer, self).save(*args, **kwargs)

    def get_billing_plan_names(self) -> str:
        subscription_set = Subscription.objects.filter(
            customer=self, status=SUBSCRIPTION_STATUS.ACTIVE
        )
        if subscription_set is None:
            return "None"
        return [str(sub.billing_plan) for sub in subscription_set]

    def get_usage_and_revenue(self):
        customer_subscriptions = (
            Subscription.objects.filter(
                customer=self,
                status=SUBSCRIPTION_STATUS.ACTIVE,
                organization=self.organization,
            )
            .prefetch_related("billing_plan__components")
            .prefetch_related("billing_plan__components__billable_metric")
            .select_related("billing_plan")
        )
        subscription_usages = {"subscriptions": []}
        for subscription in customer_subscriptions:
            sub_dict = subscription.get_usage_and_revenue()
            del sub_dict["components"]
            sub_dict["billing_plan_name"] = subscription.billing_plan.plan.plan_name
            subscription_usages["subscriptions"].append(sub_dict)

        return subscription_usages


class Event(models.Model):
    """
    Event object. An explanation of the Event's fields follows:
    event_name: The type of event that occurred.
    time_created: The time at which the event occurred.
    customer: The customer that the event occurred to.
    idempotency_id: A unique identifier for the event.
    """

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, null=False, related_name="+"
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, null=False, related_name="+"
    )
    event_name = models.CharField(max_length=200, null=False)
    time_created = models.DateTimeField()
    properties = models.JSONField(default=dict, blank=True, null=True)
    idempotency_id = models.CharField(max_length=255, unique=True)

    class Meta:
        ordering = ["time_created", "idempotency_id"]

    def __str__(self):
        return str(self.event_name) + "-" + str(self.idempotency_id)


class NumericFilter(models.Model):
    property_name = models.CharField(max_length=100)
    operator = models.CharField(max_length=10, choices=NUMERIC_FILTER_OPERATORS.choices)
    comparison_value = models.FloatField()


class CategoricalFilter(models.Model):
    property_name = models.CharField(max_length=100)
    operator = models.CharField(
        max_length=10, choices=CATEGORICAL_FILTER_OPERATORS.choices
    )
    comparison_value = models.JSONField()


class BillableMetric(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=False,
        related_name="org_billable_metrics",
    )
    event_name = models.CharField(max_length=200, null=False)
    property_name = models.CharField(max_length=200, blank=True, null=True)
    aggregation_type = models.CharField(
        max_length=10,
        choices=METRIC_AGGREGATION.choices,
        default=METRIC_AGGREGATION.COUNT,
        blank=False,
        null=False,
    )
    metric_type = models.CharField(
        max_length=20,
        choices=METRIC_TYPE.choices,
        default=METRIC_TYPE.AGGREGATION,
        blank=False,
        null=False,
    )
    billable_metric_name = models.CharField(
        max_length=200, null=False, blank=True, default=metric_uuid
    )
    numeric_filters = models.ManyToManyField(NumericFilter, blank=True)
    categorical_filters = models.ManyToManyField(CategoricalFilter, blank=True)
    properties = models.JSONField(default=dict, blank=True, null=True)
    history = HistoricalRecords()

    class Meta:
        unique_together = ("organization", "billable_metric_name")
        constraints = [
            UniqueConstraint(
                fields=[
                    "organization",
                    "event_name",
                    "aggregation_type",
                    "property_name",
                    "metric_type",
                ],
                name="unique_with_property_name",
            ),
            UniqueConstraint(
                fields=[
                    "organization",
                    "event_name",
                    "aggregation_type",
                    "metric_type",
                ],
                condition=Q(property_name=None),
                name="unique_without_property_name",
            ),
        ]

    def __str__(self):
        return self.billable_metric_name

    def get_aggregation_type(self):
        return self.aggregation_type

    def get_usage(
        self,
        query_start_date,
        query_end_date,
        granularity,
        customer=None,
        billable_only=False,
    ) -> dict[Customer.name, dict[datetime.datetime, float]]:
        from metering_billing.billable_metrics import METRIC_HANDLER_MAP

        handler = METRIC_HANDLER_MAP[self.metric_type](self)

        usage = handler.get_usage(
            granularity=granularity,
            start_date=query_start_date,
            end_date=query_end_date,
            customer=customer,
            billable_only=billable_only,
        )

        return usage


class UsageRevenueSummary(TypedDict):
    revenue: Decimal
    usage_qty: Decimal


class PlanComponent(models.Model):
    billable_metric = models.ForeignKey(
        BillableMetric, on_delete=models.CASCADE, related_name="+"
    )
    free_metric_units = models.DecimalField(
        decimal_places=10, max_digits=20, default=0.0, blank=True, null=True
    )
    cost_per_batch = models.DecimalField(
        decimal_places=10, max_digits=20, blank=True, null=True
    )
    metric_units_per_batch = models.DecimalField(
        decimal_places=10, max_digits=20, blank=True, null=True
    )
    max_metric_units = models.DecimalField(
        decimal_places=10, max_digits=20, blank=True, null=True
    )

    def __str__(self):
        return str(self.billable_metric)

    def calculate_revenue(
        self,
        customer,
        plan_start_date,
        plan_end_date,
        revenue_granularity=REVENUE_CALC_GRANULARITY.TOTAL,
    ) -> dict[datetime.datetime, UsageRevenueSummary]:
        assert isinstance(
            revenue_granularity, REVENUE_CALC_GRANULARITY
        ), "revenue_granularity must be part of REVENUE_CALC_GRANULARITY enum"
        if type(plan_start_date) == str:
            plan_start_date = parser.parse(plan_start_date)
        if type(plan_end_date) == str:
            plan_end_date = parser.parse(plan_end_date)

        billable_metric = self.billable_metric
        usage = billable_metric.get_usage(
            plan_start_date,
            plan_end_date,
            revenue_granularity,
            customer=customer,
            billable_only=True,
        )

        usage = usage.get(customer.name, {})

        period_revenue_dict = {
            period: {}
            for period in periods_bwn_twodates(
                revenue_granularity, plan_start_date, plan_end_date
            )
        }
        free_units_usage_left = self.free_metric_units
        remainder_billable_units = 0
        for period in period_revenue_dict:
            period_usage = usage.get(period, 0)
            qty = convert_to_decimal(period_usage)
            period_revenue_dict[period] = {"usage_qty": qty, "revenue": 0}
            if (
                self.cost_per_batch == 0
                or self.cost_per_batch is None
                or self.metric_units_per_batch == 0
                or self.metric_units_per_batch is None
            ):
                continue
            else:
                billable_units = max(
                    qty - free_units_usage_left + remainder_billable_units, 0
                )
                billable_batches = billable_units // self.metric_units_per_batch
                remainder_billable_units = (
                    billable_units - billable_batches * self.metric_units_per_batch
                )
                free_units_usage_left = max(0, free_units_usage_left - qty)
                if billable_metric.metric_type == METRIC_TYPE.STATEFUL:
                    usage_revenue = (
                        billable_batches
                        * self.cost_per_batch
                        / len(period_revenue_dict)
                    )
                else:
                    usage_revenue = billable_batches * self.cost_per_batch
                period_revenue_dict[period]["revenue"] = convert_to_decimal(
                    usage_revenue
                )
                if billable_metric.metric_type == METRIC_TYPE.STATEFUL:
                    free_units_usage_left = self.free_metric_units
                    remainder_billable_units = 0
        return period_revenue_dict


class Feature(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, null=False, related_name="org_features"
    )
    feature_name = models.CharField(max_length=200, null=False)
    feature_description = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        unique_together = ("organization", "feature_name")

    def __str__(self):
        return str(self.feature_name)


class Invoice(models.Model):
    cost_due = MoneyField(
        decimal_places=10, max_digits=20, default_currency="USD", default=0.0
    )
    issue_date = models.DateTimeField(max_length=100, default=now_utc)
    invoice_pdf = models.FileField(upload_to="invoices/", null=True, blank=True)
    org_connected_to_cust_payment_provider = models.BooleanField(default=False)
    cust_connected_to_payment_provider = models.BooleanField(default=False)
    payment_status = models.CharField(max_length=40, choices=INVOICE_STATUS.choices)
    external_payment_obj = models.JSONField(default=dict, blank=True, null=True)
    external_payment_obj_id = models.CharField(max_length=200, blank=True, null=True)
    external_payment_obj_type = models.CharField(
        choices=PAYMENT_PROVIDERS.choices, max_length=40, null=True, blank=True
    )
    line_items = models.JSONField()
    organization = models.JSONField()
    customer = models.JSONField()
    subscription = models.JSONField()
    history = HistoricalRecords()


class APIToken(AbstractAPIKey):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="org_api_keys"
    )
    name = models.CharField(max_length=200, default="latest_token")

    class Meta(AbstractAPIKey.Meta):
        verbose_name = "API Token"
        verbose_name_plural = "API Tokens"

    def __str__(self):
        return str(self.name) + " " + str(self.organization.company_name)


class OrganizationInviteToken(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="user_invite_token"
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="org_invite_token",
    )
    email = models.EmailField()
    token = models.CharField(max_length=250, default=uuid.uuid4)
    expire_at = models.DateTimeField(default=now_plus_day, null=False, blank=False)


class PlanVersion(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=False,
        related_name="org_plan_versions",
    )
    description = models.CharField(max_length=200, null=True, blank=True)
    version = models.PositiveSmallIntegerField()
    flat_fee_billing_type = models.CharField(
        max_length=40, choices=FLAT_FEE_BILLING_TYPE.choices
    )
    usage_billing_frequency = models.CharField(
        max_length=40, choices=USAGE_BILLING_FREQUENCY.choices
    )
    proration_granularity = models.CharField(
        max_length=40, choices=PRORATION_GRANULARITY.choices, null=True, blank=True
    )
    plan = models.ForeignKey("Plan", on_delete=models.CASCADE, related_name="versions")
    status = models.CharField(max_length=40, choices=PLAN_VERSION_STATUS.choices)
    replace_with = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True
    )
    flat_rate = MoneyField(decimal_places=10, max_digits=20, default_currency="USD")
    components = models.ManyToManyField(PlanComponent, blank=True)
    features = models.ManyToManyField(Feature, blank=True)
    price_adjustment = models.ForeignKey(
        "PriceAdjustment", on_delete=models.CASCADE, null=True, blank=True
    )
    created_on = models.DateTimeField(default=now_utc)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_plan_versions",
        null=True,
        blank=True,
    )
    version_id = models.CharField(max_length=250, default=vers_uuid)
    history = HistoricalRecords()

    class Meta:
        unique_together = ("organization", "version_id")

    def __str__(self) -> str:
        return str(self.plan) + " v" + str(self.version)

    def num_active_subs(self):
        cnt = self.bp_subscriptions.filter(status=SUBSCRIPTION_STATUS.ACTIVE).count()
        return cnt


class PriceAdjustment(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="org_price_adjustments"
    )
    price_adjustment_name = models.CharField(max_length=200, null=False)
    price_adjustment_description = models.CharField(
        max_length=200, blank=True, null=True
    )
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
                str(self.price_adjustment_amount)
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


class Plan(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="org_plans"
    )
    plan_name = models.CharField(max_length=100, null=False, blank=False)
    plan_duration = models.CharField(choices=PLAN_DURATION.choices, max_length=40)
    display_version = models.ForeignKey(
        "PlanVersion", on_delete=models.CASCADE, related_name="+", null=True, blank=True
    )
    parent_product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="product_plans",
        null=True,
        blank=True,
    )
    status = models.CharField(
        choices=PLAN_STATUS.choices, max_length=40, default=PLAN_STATUS.ACTIVE
    )
    plan_id = models.CharField(default=plan_uuid, max_length=100, unique=True)
    created_on = models.DateTimeField(default=now_utc)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_plans",
        null=True,
        blank=True,
    )
    parent_plan = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="child_plans",
    )
    target_customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="custom_plans",
    )
    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(Q(parent_plan__isnull=True) & Q(target_customer__isnull=True))
                | Q(parent_plan__isnull=False) & Q(target_customer__isnull=False),
                name="both_null_or_both_not_null",
            )
        ]

    def __str__(self):
        return f"{self.plan_name}"

    def active_subs_by_version(self):
        versions = self.versions.all().prefetch_related("bp_subscriptions")
        versions_count = versions.annotate(
            active_subscriptions=Count(
                "bp_subscription",
                filter=Q(bp_subscription__status=SUBSCRIPTION_STATUS.ACTIVE),
                output_field=models.IntegerField(),
            )
        )
        return versions_count

    def version_numbers(self):
        return self.versions.all().values_list("version", flat=True)

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
            print("grandfathering", make_active_type)
            # 1
            replace_with_lst = [PLAN_VERSION_STATUS.RETIRING]
            # 2a
            if (
                make_active_type
                == MAKE_PLAN_VERSION_ACTIVE_TYPE.REPLACE_ON_ACTIVE_VERSION_RENEWAL
            ):
                replace_with_lst.append(PLAN_VERSION_STATUS.ACTIVE)
            self.versions.all().filter(
                ~Q(pk=new_version.pk), status__in=replace_with_lst
            ).update(replace_with=new_version, status=PLAN_VERSION_STATUS.RETIRING)
            # 2b
            if make_active_type == MAKE_PLAN_VERSION_ACTIVE_TYPE.GRANDFATHER_ACTIVE:
                self.versions.all().filter(
                    ~Q(pk=new_version.pk), status=PLAN_VERSION_STATUS.ACTIVE
                ).update(status=PLAN_VERSION_STATUS.GRANDFATHERED)
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
                .prefetch_related("bp_subscriptions")
            )
            versions.update(status=PLAN_VERSION_STATUS.INACTIVE, replace_with=None)
            for version in versions:
                for sub in version.bp_subscriptions.filter(
                    status=SUBSCRIPTION_STATUS.ACTIVE
                ):
                    if (
                        replace_immediately_type
                        == REPLACE_IMMEDIATELY_TYPE.CHANGE_SUBSCRIPTION_PLAN
                    ):
                        sub.switch_subscription_bp(billing_plan=new_version)
                    else:
                        sub.end_subscription_now(
                            bill=replace_immediately_type
                            == REPLACE_IMMEDIATELY_TYPE.END_CURRENT_SUBSCRIPTION_AND_BILL
                        )
                        Subscription.objects.create(
                            billing_plan=new_version,
                            organization=self.organization,
                            customer=sub.customer,
                            start_date=sub.end_date,
                            status=SUBSCRIPTION_STATUS.ACTIVE,
                            auto_renew=True,
                            is_new=False,
                        )


class Subscription(models.Model):
    """
    Subscription object. An explanation of the Subscription's fields follows:
    customer: The customer that the subscription belongs to.
    plan_name: The name of the plan that the subscription is for.
    start_date: The date at which the subscription started.
    end_date: The date at which the subscription will end.
    status: The status of the subscription, active or ended.
    """

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=False,
        related_name="org_subscriptions",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        null=False,
        related_name="customer_subscriptions",
    )
    billing_plan = models.ForeignKey(
        PlanVersion,
        on_delete=models.CASCADE,
        null=False,
        related_name="bp_subscriptions",
        related_query_name="bp_subscription",
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_STATUS.choices,
        default=SUBSCRIPTION_STATUS.NOT_STARTED,
    )
    auto_renew = models.BooleanField(default=True)
    is_new = models.BooleanField(default=True)
    subscription_id = models.CharField(
        max_length=100, null=False, blank=True, default=subs_uuid
    )
    prorated_flat_costs_dict = models.JSONField(default=dict, blank=True, null=True)
    flat_fee_already_billed = models.DecimalField(
        decimal_places=10, max_digits=20, default=0.0, blank=True, null=True
    )
    history = HistoricalRecords()

    class Meta:
        unique_together = ("organization", "subscription_id")

    def __str__(self):
        return f"{self.customer.name}  {self.billing_plan.plan.plan_name} : {self.start_date.date()} to {self.end_date.date()}"

    def save(self, *args, **kwargs):
        if not self.end_date:
            self.end_date = calculate_end_date(
                self.billing_plan.plan.plan_duration, self.start_date
            )
        if self.status == SUBSCRIPTION_STATUS.ACTIVE:
            flat_fee_dictionary = self.prorated_flat_costs_dict
            today = now_utc().date()
            dates_bwn = list(dates_bwn_two_dts(self.start_date, self.end_date))
            for day in dates_bwn:
                if isinstance(day, datetime.datetime):
                    day = day.date()
                if day >= today:
                    flat_fee_dictionary[str(day)] = {
                        "plan_version_id": self.billing_plan.version_id,
                        "amount": float(self.billing_plan.flat_rate.amount)
                        / len(dates_bwn),
                    }
        super(Subscription, self).save(*args, **kwargs)

    def get_usage_and_revenue(self):
        sub_dict = {}
        sub_dict["components"] = []
        # set up the billing plan for this subscription
        plan = self.billing_plan
        # set up other details of the subscription
        plan_start_date = self.start_date
        plan_end_date = self.end_date
        # extract other objects that we need when calculating usage
        customer = self.customer
        plan_components_qs = plan.components.all()
        # For each component of the plan, calculate usage/revenue
        for plan_component in plan_components_qs:
            plan_component_summary = plan_component.calculate_revenue(
                customer,
                plan_start_date,
                plan_end_date,
            )
            sub_dict["components"].append((plan_component.pk, plan_component_summary))
        sub_dict["usage_revenue_due"] = Decimal(0)
        for component_pk, component_dict in sub_dict["components"]:
            for date, date_dict in component_dict.items():
                sub_dict["usage_revenue_due"] += date_dict["revenue"]
        sub_dict["flat_revenue_due"] = plan.flat_rate.amount
        sub_dict["total_revenue_due"] = (
            sub_dict["flat_revenue_due"] + sub_dict["usage_revenue_due"]
        )
        return sub_dict

    def end_subscription_now(self, bill=True):
        if self.status != SUBSCRIPTION_STATUS.ACTIVE:
            raise Exception(
                "Subscription needs to be active to end it. Subscription status is {}".format(
                    self.status
                )
            )
        if bill:
            generate_invoice(self)
        self.turn_off_auto_renew()
        self.end_date = now_utc()
        self.status = SUBSCRIPTION_STATUS.ENDED
        self.save()

    def turn_off_auto_renew(self):
        self.auto_renew = False
        self.save()

    def switch_subscription_bp(self, new_version):
        self.billing_plan = new_version
        self.save()
        if new_version.flat_fee_billing_type == FLAT_FEE_BILLING_TYPE.IN_ADVANCE:
            new_sub_daily_cost_dict = self.prorated_flat_costs_dict
            prorated_cost = sum(d["amount"] for d in new_sub_daily_cost_dict.values())
            due = prorated_cost - self.customer.balance - self.flat_fee_already_billed
            if due < 0:
                self.customer.balance = abs(due)
            elif due > 0:
                generate_invoice(self, draft=False, issue_date=now_utc(), amount=due)
                self.flat_fee_already_billed += due
                self.save()
                self.customer.balance = 0
            self.customer.save()


class Backtest(models.Model):
    """
    This model is used to store the results of a backtest.
    """

    backtest_name = models.CharField(max_length=100, null=False, blank=False)
    start_date = models.DateField(null=False, blank=False)
    end_date = models.DateField(null=False, blank=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, null=False, related_name="org_backtests"
    )
    time_created = models.DateTimeField(default=now_utc)
    backtest_id = models.CharField(
        max_length=100, null=False, blank=True, default=btst_uuid, unique=True
    )
    kpis = models.JSONField(default=list)
    backtest_results = models.JSONField(default=dict, null=True, blank=True)
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
