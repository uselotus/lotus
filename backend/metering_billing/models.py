import datetime
import uuid

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import DateTimeRangeField
from django.db import models
from django.db.models import Func, Q
from django.db.models.constraints import UniqueConstraint
from djmoney.models.fields import MoneyField
from metering_billing.utils import (
    AGGREGATION_TYPES,
    BACKTEST_KPI_TYPES,
    BACKTEST_STATUS_TYPES,
    CATEGORICAL_FILTER_OPERATORS,
    INTERVAL_TYPES,
    INVOICE_STATUS_TYPES,
    METRIC_TYPES,
    NUMERIC_FILTER_OPERATORS,
    PAYMENT_PLANS,
    PAYMENT_PROVIDERS,
    PLAN_STATUS,
    SUB_STATUS_TYPES,
    dates_bwn_twodates,
    now_plus_day,
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
            customer=self, status=SUB_STATUS_TYPES.ACTIVE
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
        choices=AGGREGATION_TYPES.choices,
        default=AGGREGATION_TYPES.COUNT,
        blank=False,
        null=False,
    )
    metric_type = models.CharField(
        max_length=20,
        choices=METRIC_TYPES.choices,
        default=METRIC_TYPES.AGGREGATION,
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


class BillingPlan(models.Model):
    """
    Billing_ID: Id for this specific plan
    time_created: self-explanatory
    interval: determines whether plan charges weekly, monthly, or yearly
    flat_rate: amount to charge every week, month, or year (depending on choice of interval)
    billable_metrics: a json containing a list of billable_metrics objects
    """

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=False,
        related_name="org_billing_plans",
    )
    time_created = models.DateTimeField(auto_now=True)
    interval = models.CharField(
        max_length=10,
        choices=INTERVAL_TYPES.choices,
    )
    billing_plan_id = models.CharField(max_length=255, default=uuid.uuid4, unique=True)
    flat_rate = MoneyField(decimal_places=10, max_digits=20, default_currency="USD")
    pay_in_advance = models.BooleanField()
    name = models.CharField(max_length=200)
    description = models.CharField(max_length=256, default=" ", blank=True)
    components = models.ManyToManyField(PlanComponent, null=True, blank=True)
    features = models.ManyToManyField(Feature, null=True, blank=True)
    scheduled_for_deletion = models.BooleanField(default=False)
    replacement_billing_plan = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL
    )
    status = models.CharField(
        max_length=20,
        choices=PLAN_STATUS.choices,
        default=PLAN_STATUS.ACTIVE,
    )
    history = HistoricalRecords()

    def __str__(self) -> str:
        return str(self.name)

    class Meta:
        unique_together = ("organization", "billing_plan_id")

    def calculate_end_date(self, start_date):
        if self.interval == INTERVAL_TYPES.WEEK:
            return start_date + relativedelta(weeks=+1) - relativedelta(days=+1)
        elif self.interval == INTERVAL_TYPES.MONTH:
            return start_date + relativedelta(months=+1) - relativedelta(days=+1)
        elif self.interval == INTERVAL_TYPES.YEAR:
            return start_date + relativedelta(years=+1) - relativedelta(days=+1)
        else:
            raise ValueError("End date not calculated correctly")


class TsTzRange(Func):
    function = "TSTZRANGE"
    output_field = DateTimeRangeField()


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
        BillingPlan,
        on_delete=models.CASCADE,
        null=False,
        related_name="bp_subscriptions",
        related_query_name="bp_subscription",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=SUB_STATUS_TYPES.choices,
        default=SUB_STATUS_TYPES.NOT_STARTED,
    )
    auto_renew = models.BooleanField(default=True)
    auto_renew_billing_plan = models.ForeignKey(
        BillingPlan,
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
            self.end_date = self.billing_plan.calculate_end_date(self.start_date)
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
        return f"{self.customer.name}  {self.billing_plan.name} : {self.start_date} to {self.end_date}"

    class Meta:
        unique_together = ("organization", "subscription_id")


class Invoice(models.Model):
    cost_due = MoneyField(
        decimal_places=10, max_digits=20, default_currency="USD", default=0.0
    )
    issue_date = models.DateTimeField(max_length=100, auto_now=True)
    invoice_pdf = models.FileField(upload_to="invoices/", null=True, blank=True)
    org_connected_to_cust_payment_provider = models.BooleanField(default=False)
    cust_connected_to_payment_provider = models.BooleanField(default=False)
    payment_status = models.CharField(
        max_length=40, choices=INVOICE_STATUS_TYPES.choices
    )
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
        choices=BACKTEST_STATUS_TYPES.choices,
        default=BACKTEST_STATUS_TYPES.RUNNING,
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
        BillingPlan, on_delete=models.CASCADE, related_name="+"
    )
    new_plan = models.ForeignKey(
        BillingPlan, on_delete=models.CASCADE, related_name="+"
    )
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.backtest}"
