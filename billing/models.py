from email.mime import base
from operator import mod
from django.db import models
import uuid
from model_utils import Choices
from djmoney.models.fields import MoneyField
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _
from moneyed import Money
from rest_framework_api_key.models import AbstractAPIKey
from dateutil.relativedelta import relativedelta
from dateutil.parser import isoparse
from django.contrib.postgres.fields import ArrayField
import jsonfield

# Create your models here.


class Customer(models.Model):

    """
    Customer Model

    This model represents a customer.

    Attributes:
        name (str): The name of the customer.
        company_name (str): The company name of the customer.
        customer_id (str): The external id of the customer in the backend system.
        billing_id (str): The billing id of the customer, internal to Lotus.
    """

    name = models.CharField(max_length=100)
    company_name = models.CharField(max_length=30, default=" ")
    customer_id = models.CharField(max_length=40, unique=True)
    billing_id = models.CharField(max_length=40, default=uuid.uuid4)
    billing_configuration = models.JSONField(default=dict, blank=True)

    balance = MoneyField(
        default=0, max_digits=10, decimal_places=2, default_currency="USD"
    )  # balance in currency that a customer currently has during this billing period, negative means they owe money, postive is a credit towards their invoice
    currency = models.CharField(max_length=3, default="USD")

    def __str__(self) -> str:
        return str(self.name) + " " + str(self.customer_id)


class Event(models.Model):
    """
    Event object. An explanation of the Event's fields follows:
    event_name: The type of event that occurred.
    time_created: The time at which the event occurred.
    customer: The customer that the event occurred to.
    idempotency_id: A unique identifier for the event.
    """

    customer: models.ForeignKey = models.ForeignKey(
        Customer, on_delete=models.CASCADE, null=False
    )
    event_name = models.CharField(max_length=200, null=False)
    time_created: models.DateTimeField = models.DateTimeField()
    properties: models.JSONField = models.JSONField(default=dict)
    idempotency_id: models.CharField = models.CharField(max_length=255, unique=True)

    class Meta:
        ordering = ["idempotency_id"]

    def __str__(self):
        return str(self.event_name) + "-" + str(self.idempotency_id)


class BillableMetric(models.Model):
    class AGGREGATION_TYPES(object):
        COUNT = "count"
        SUM = "sum"
        MAX = "max"

    AGGREGATION_CHOICES = Choices(
        (AGGREGATION_TYPES.COUNT, _("Count")),
        (AGGREGATION_TYPES.SUM, _("Sum")),
        (AGGREGATION_TYPES.MAX, _("Max")),
    )

    event_name = models.CharField(max_length=200, null=False)
    property_name = models.CharField(max_length=200, null=True)
    aggregation_type = models.CharField(
        max_length=10,
        choices=AGGREGATION_CHOICES,
        default=AGGREGATION_CHOICES.count,
    )

    def get_aggregation_type(self):
        return self.aggregation_type


class BillingPlan(models.Model):
    """
    Billing_ID: Id for this specific plan
    time_created: self-explanatory
    currency: self-explanatory
    interval: determines whether plan charges weekly, monthly, or yearly
    base_rate: amount to charge every week, month, or year (depending on choice of interval)
    billable_metrics: a json containing a list of billable_metrics objects
    """

    plan_id = models.CharField(
        max_length=36, blank=True, unique=True, default=uuid.uuid4
    )

    time_created: models.DateTimeField = models.DateTimeField(auto_now=True)
    currency = models.CharField(max_length=30, default="USD")  # 30 is arbitrary

    INTERVAL_CHOICES = Choices(
        ("week", _("Week")),
        ("month", _("Month")),
        ("year", _("Year")),
    )

    interval = models.CharField(
        max_length=5,
        choices=INTERVAL_CHOICES,
        default=INTERVAL_CHOICES.month,
    )

    base_rate = MoneyField(
        decimal_places=2, max_digits=8, default_currency="USD", default=0.0
    )
    pay_in_advance = models.BooleanField(default=False)
    # Need to figure out how to make this a list of BillableMetrics
    billable_metric = models.ForeignKey(
        BillableMetric, on_delete=models.CASCADE, null=True, blank=True
    )
    starter_metric_quatity = models.IntegerField(default=0, null=True, blank=True)
    metric_amount = MoneyField(
        decimal_places=10, max_digits=14, default_currency="USD", null=True, blank=True
    )
    name = models.CharField(max_length=200, default=" ")
    description = models.CharField(max_length=256, default=" ", blank=True)

    def subscription_end_date(self, start_date):
        start_date_parsed = start_date
        if self.interval == "week":
            return start_date_parsed + relativedelta(weeks=+1)
        elif self.interval == "month":
            return start_date_parsed + relativedelta(months=+1)
        elif self.interval == "year":
            return start_date_parsed + relativedelta(years=+1)
        else:
            return None

    def get_usage_cost_count_aggregation(self, num_events):
        return max(0, self.metric_amount * (self.starter_metric_quantity - num_events))

    def __str__(self) -> str:
        return str(self.name) + ":" + str(self.plan_id)


class Subscription(models.Model):
    """
    Subscription object. An explanation of the Subscription's fields follows:
    customer: The customer that the subscription belongs to.
    plan_name: The name of the plan that the subscription is for.
    start_date: The date at which the subscription started.
    end_date: The date at which the subscription will end.
    status: The status of the subscription, active or ended.

    """

    STATUSES = Choices(
        ("active", _("Active")),
        ("ended", _("Ended")),
    )

    id = models.CharField(primary_key=True, max_length=36, default=uuid.uuid4)

    customer: models.ForeignKey = models.ForeignKey(Customer, on_delete=models.CASCADE)
    billing_plan = models.ForeignKey(BillingPlan, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField(auto_now=True)
    status = models.CharField(max_length=6, choices=STATUSES, default=STATUSES.active)

    def __str__(self):
        return str(self.customer) + " " + str(self.billing_plan)


class Invoice(models.Model):

    id = models.CharField(primary_key=True, max_length=36, default=uuid.uuid4)
    cost_due = MoneyField(
        max_digits=10, decimal_places=2, null=True, default_currency="USD"
    )
    currency = models.CharField(max_length=10, default="USD")
    issue_date = models.DateTimeField(max_length=100, auto_now=True)

    customer_name = models.CharField(max_length=100)
    customer_billing_id = models.CharField(max_length=40)

    invoice_pdf = models.FileField(upload_to="invoices/", null=True, blank=True)

    subscription = models.ForeignKey(Subscription, on_delete=models.PROTECT)

    line_items = ArrayField(base_field=models.JSONField(), null=True, blank=True)


class User(AbstractUser):

    company_name = models.CharField(max_length=200, default=" ")


class APIToken(AbstractAPIKey):

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=200, default="latest_token")

    def __str__(self):
        return str(self.name) + " " + str(self.user)

    class Meta:
        verbose_name = "API Token"
        verbose_name_plural = "API Tokens"
