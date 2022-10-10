import datetime
import uuid

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import DateTimeRangeField
from django.db import models
from django.db.models import Func, Q
from django.db.models.constraints import UniqueConstraint
from djmoney.models.fields import MoneyField
from rest_framework_api_key.models import AbstractAPIKey
from simple_history.models import HistoricalRecords

from metering_billing.utils import (
    AGGREGATION_CHOICES,
    CATEGORICAL_FILTER_OPERATOR_CHOICES,
    INTERVAL_CHOICES,
    INTERVAL_TYPES,
    INVOICE_STATUS_CHOICES,
    METRIC_TYPE_CHOICES,
    NUMERIC_FILTER_OPERATOR_CHOICES,
    PAYMENT_PLANS,
    SUB_STATUS_CHOICES,
    SUB_STATUS_TYPES,
    SUPPORTED_PAYMENT_PROVIDERS,
    dates_bwn_twodates,
)


class Organization(models.Model):
    company_name = models.CharField(max_length=100, default=" ")
    payment_provider_ids = models.JSONField(default=dict, blank=True, null=True)
    created = models.DateField(auto_now=True)
    payment_plan = models.CharField(
        max_length=40, choices=PAYMENT_PLANS, default=PAYMENT_PLANS.self_hosted_free
    )
    history = HistoricalRecords()

    def __str__(self):
        return self.company_name

    def save(self, *args, **kwargs):
        for k, _ in self.payment_provider_ids.items():
            if k not in SUPPORTED_PAYMENT_PROVIDERS:
                raise ValueError(
                    f"Payment provider {k} is not supported. Supported payment providers are: {SUPPORTED_PAYMENT_PROVIDERS}"
                )
        super(Organization, self).save(*args, **kwargs)


class Alert(models.Model):
    type = models.CharField(max_length=20, default="webhook")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    webhook_url = models.CharField(max_length=300, blank=True, null=True)
    name = models.CharField(max_length=100, default=" ")
    history = HistoricalRecords()


class User(AbstractUser):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, null=True, blank=True
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

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=False)
    name = models.CharField(max_length=100)
    email = models.EmailField(max_length=100, blank=True, null=True)
    customer_id = models.CharField(max_length=40)
    payment_provider = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        choices=SUPPORTED_PAYMENT_PROVIDERS,
    )
    payment_provider_id = models.CharField(max_length=50, null=True, blank=True)
    properties = models.JSONField(default=dict, blank=True, null=True)
    balance = MoneyField(
        decimal_places=10, max_digits=20, default_currency="USD", default=0.0
    )
    billing_address = models.CharField(max_length=500, blank=True, null=True)
    history = HistoricalRecords()

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


class Event(models.Model):
    """
    Event object. An explanation of the Event's fields follows:
    event_name: The type of event that occurred.
    time_created: The time at which the event occurred.
    customer: The customer that the event occurred to.
    idempotency_id: A unique identifier for the event.
    """

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=False)
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
    operator = models.CharField(max_length=10, choices=NUMERIC_FILTER_OPERATOR_CHOICES)
    comparison_value = models.FloatField()


class CategoricalFilter(models.Model):
    property_name = models.CharField(max_length=100)
    operator = models.CharField(
        max_length=10, choices=CATEGORICAL_FILTER_OPERATOR_CHOICES
    )
    comparison_value = models.JSONField()


class BillableMetric(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=False)
    event_name = models.CharField(max_length=200, null=False)
    property_name = models.CharField(max_length=200, blank=True, null=True)
    aggregation_type = models.CharField(
        max_length=10,
        choices=AGGREGATION_CHOICES,
        default=AGGREGATION_CHOICES.count,
        blank=False,
        null=False,
    )
    metric_type = models.CharField(
        max_length=20,
        choices=METRIC_TYPE_CHOICES,
        default=METRIC_TYPE_CHOICES.aggregation,
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
    billable_metric = models.ForeignKey(BillableMetric, on_delete=models.CASCADE)
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
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=False)
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

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=False)
    time_created = models.DateTimeField(auto_now=True)
    interval = models.CharField(
        max_length=5,
        choices=INTERVAL_CHOICES,
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

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=False)
    billing_plan = models.ForeignKey(
        BillingPlan,
        related_name="current_billing_plan",
        on_delete=models.CASCADE,
        null=False,
    )
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=SUB_STATUS_CHOICES,
        default=SUB_STATUS_CHOICES.not_started,
    )
    auto_renew = models.BooleanField(default=True)
    auto_renew_billing_plan = models.ForeignKey(
        BillingPlan,
        related_name="next_billing_plan",
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
    payment_status = models.CharField(max_length=40, choices=INVOICE_STATUS_CHOICES)
    external_payment_obj_id = models.CharField(max_length=240, null=True, blank=True)
    external_payment_obj_type = models.CharField(
        choices=SUPPORTED_PAYMENT_PROVIDERS, max_length=40, null=True, blank=True
    )
    line_items = models.JSONField()
    organization = models.JSONField()
    customer = models.JSONField()
    subscription = models.JSONField()
    history = HistoricalRecords()


class APIToken(AbstractAPIKey):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="api_keys"
    )
    name = models.CharField(max_length=200, default="latest_token")

    def __str__(self):
        return str(self.name) + " " + str(self.organization.company_name)

    class Meta(AbstractAPIKey.Meta):
        verbose_name = "API Token"
        verbose_name_plural = "API Tokens"
