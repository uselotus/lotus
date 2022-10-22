import datetime
import uuid

import pytz
from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Count, Q
from django.db.models.constraints import UniqueConstraint
from djmoney.models.fields import MoneyField
from metering_billing.utils import (
    calculate_end_date,
    dates_bwn_twodates,
    now_plus_day,
    now_utc,
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
    PRODUCT_STATUS,
    PRORATION_GRANULARITY,
    REPLACE_IMMEDIATELY_TYPE,
    SUBSCRIPTION_STATUS,
    USAGE_BILLING_TYPE,
)
from rest_framework_api_key.models import AbstractAPIKey
from simple_history.models import HistoricalRecords


class Organization(models.Model):
    company_name = models.CharField(max_length=100, blank=False, null=False)
    payment_provider_ids = models.JSONField(default=dict, blank=True, null=True)
    created = models.DateField(auto_now=True)
    payment_plan = models.CharField(
        max_length=40,
        choices=PAYMENT_PLANS.choices,
        default=PAYMENT_PLANS.SELF_HOSTED_FREE,
    )
    history = HistoricalRecords()

    def __str__(self):
        return self.company_name

    @property
    def users(self):
        return self.org_users

    def save(self, *args, **kwargs):
        for k, _ in self.payment_provider_ids.items():
            if k not in PAYMENT_PROVIDERS:
                raise ValueError(
                    f"Payment provider {k} is not supported. Supported payment providers are: {PAYMENT_PROVIDERS}"
                )
        super(Organization, self).save(*args, **kwargs)


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
    product_id = models.CharField(default=uuid.uuid4, max_length=100, unique=True)
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
        max_length=40, blank=True, null=False, default=uuid.uuid4
    )
    payment_providers = models.JSONField(default=dict, blank=True, null=True)
    properties = models.JSONField(default=dict, blank=True, null=True)
    balance = MoneyField(
        decimal_places=10, max_digits=20, default_currency="USD", default=0.0
    )
    history = HistoricalRecords()
    sources = models.JSONField(default=list, blank=True, null=True)

    def __str__(self) -> str:
        return str(self.name) + " " + str(self.customer_id)

    def get_billing_plan_name(self) -> str:
        subscription_set = Subscription.objects.filter(
            customer=self, status=SUBSCRIPTION_STATUS.ACTIVE
        )
        if subscription_set is None:
            return "None"
        return [str(sub.billing_plan) for sub in subscription_set]

    class Meta:
        unique_together = ("organization", "customer_id")

    def save(self, *args, **kwargs):
        if len(self.sources) > 0:
            assert isinstance(self.sources, list)
            for source in self.sources:
                assert (
                    source in PAYMENT_PROVIDERS or source == "lotus"
                ), f"Payment provider {source} is not supported. Supported payment providers are: {PAYMENT_PROVIDERS}"
        for k, v in self.payment_providers.items():
            if k not in PAYMENT_PROVIDERS:
                raise ValueError(
                    f"Payment provider {k} is not supported. Supported payment providers are: {PAYMENT_PROVIDERS}"
                )
            id = v.get("id")
            if id is None:
                raise ValueError(f"Payment provider {k} id was not provided")
            assert (
                k in self.sources
            ), f"Payment provider {k} in payment providers dict but not in sources"
        super(Customer, self).save(*args, **kwargs)


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
        max_length=200, null=False, blank=True, default=uuid.uuid4
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

    def get_aggregation_type(self):
        return self.aggregation_type

    def __str__(self):
        return self.billable_metric_name


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
    issue_date = models.DateTimeField(max_length=100, auto_now=True)
    invoice_pdf = models.FileField(upload_to="invoices/", null=True, blank=True)
    org_connected_to_cust_payment_provider = models.BooleanField(default=False)
    cust_connected_to_payment_provider = models.BooleanField(default=False)
    payment_status = models.CharField(max_length=40, choices=INVOICE_STATUS.choices)
    external_payment_obj_id = models.CharField(max_length=240, null=True, blank=True)
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

    def __str__(self):
        return str(self.name) + " " + str(self.organization.company_name)

    class Meta(AbstractAPIKey.Meta):
        verbose_name = "API Token"
        verbose_name_plural = "API Tokens"


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
    usage_billing_type = models.CharField(
        max_length=40, choices=USAGE_BILLING_TYPE.choices
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
    created_on = models.DateTimeField(default=now_utc)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_plan_versions",
        null=True,
        blank=True,
    )
    version_id = models.CharField(max_length=250, default=uuid.uuid4)
    history = HistoricalRecords()

    def __str__(self) -> str:
        return str(self.plan) + " v" + str(self.version)

    def num_active_subs(self):
        cnt = self.bp_subscriptions.filter(status=SUBSCRIPTION_STATUS.ACTIVE).count()
        return cnt

    class Meta:
        unique_together = ("organization", "version_id")


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
        Product, on_delete=models.CASCADE, related_name="product_plans"
    )
    status = models.CharField(
        choices=PLAN_STATUS.choices, max_length=40, default=PLAN_STATUS.ACTIVE
    )
    plan_id = models.CharField(default=uuid.uuid4, max_length=100, unique=True)
    created_on = models.DateTimeField(default=now_utc)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_plans",
        null=True,
        blank=True,
    )
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.plan_name}"

    def active_subs_by_version(self):
        versions = self.versions.all().prefetch_related("bp_subscriptions")
        versions_count = versions.annotate(
            active_subscriptions=Count(
                "bp_subscription",
                filter=Q(status=SUBSCRIPTION_STATUS.ACTIVE),
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

    def add_new_version(
        self, plan_version, make_active_type=None, replace_immediately_type=None
    ):
        # If plan version is active, then make sure to run the make evrsio nactvie subroutine
        if plan_version.status == PLAN_VERSION_STATUS.ACTIVE:
            self.make_version_active(
                plan_version, make_active_type, replace_immediately_type
            )
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
            self.versions.all().filter(
                ~Q(pk=new_version.pk), status__in=replace_with_lst
            ).update(replace_with=new_version, status=PLAN_VERSION_STATUS.RETIRING)
            # 2b
            if make_active_type == MAKE_PLAN_VERSION_ACTIVE_TYPE.GRANDFATHER_ACTIVE:
                self.versions.all().filter(status=PLAN_VERSION_STATUS.ACTIVE).update(
                    status=PLAN_VERSION_STATUS.GRANDFATHERED
                )
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
                        == REPLACE_IMMEDIATELY_TYPE.END_CURRENT_SUBSCRIPTION
                    ):
                        sub.end_subscription_and_start_new(billing_plan=new_version)
                    else:  # change_subscription_plan
                        sub.switch_subscription_bp(billing_plan=new_version)


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
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_STATUS.choices,
        default=SUBSCRIPTION_STATUS.NOT_STARTED,
    )
    auto_renew = models.BooleanField(default=True)
    auto_renew_billing_plan = models.ForeignKey(
        PlanVersion,
        related_name="+",
        on_delete=models.CASCADE,
        null=True,
    )
    is_new = models.BooleanField(default=True)
    subscription_id = models.CharField(
        max_length=100, null=False, blank=True, default=uuid.uuid4
    )
    prorated_flat_costs_dict = models.JSONField(default=dict, blank=True, null=True)
    flat_fee_already_billed = models.DecimalField(
        decimal_places=10, max_digits=20, default=0.0, blank=True, null=True
    )
    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        if not self.end_date:
            self.end_date = calculate_end_date(
                self.billing_plan.plan.plan_duration, self.start_date
            )
        flat_cost_dict = self.prorated_flat_costs_dict
        today = datetime.date.today()
        dates_bwn = list(dates_bwn_twodates(self.start_date, self.end_date))
        for day in dates_bwn:
            if day >= today:
                flat_cost_dict[str(day)] = float(
                    self.billing_plan.flat_rate.amount
                ) / len(dates_bwn)
        super(Subscription, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.customer.name}  {self.billing_plan.plan.plan_name} : {self.start_date} to {self.end_date}"

    class Meta:
        unique_together = ("organization", "subscription_id")


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
    time_created = models.DateTimeField(default=datetime.datetime.now)
    backtest_id = models.CharField(
        max_length=100, null=False, blank=True, default=uuid.uuid4, unique=True
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
