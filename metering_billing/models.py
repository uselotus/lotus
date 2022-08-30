import uuid

from dateutil.parser import isoparse
from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import (
    ArrayField,
    DateTimeRangeField,
    RangeBoundary,
    RangeOperators,
)
from django.db import models
from django.db.models import Func, Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from model_utils import Choices
from rest_framework_api_key.models import AbstractAPIKey


class Organization(models.Model):
    PAYMENT_PLANS = Choices(
        ("self_hosted_free", _("Self-Hosted Free")),
        ("cloud", _("Cloud")),
        ("self_hosted_enterprise", _("Self-Hosted Enterprise")),
    )
    company_name = models.CharField(max_length=100, default=" ")
    stripe_id = models.CharField(max_length=110, default="", blank=True, null=True)
    created = models.DateField(auto_now=True)
    payment_plan = models.CharField(
        max_length=40, choices=PAYMENT_PLANS, default=PAYMENT_PLANS.self_hosted_free
    )


class User(AbstractUser):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, null=True, blank=True
    )


class Customer(models.Model):

    """
    Customer Model

    This model represents a customer.

    Attributes:
        name (str): The name of the customer.
        customer_id (str): The external id of the customer in the backend system.
        billing_id (str): The billing id of the customer, internal to Lotus.
    """

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=False)
    name = models.CharField(max_length=100)
    customer_id = models.CharField(max_length=40, unique=True)
    billing_id = models.CharField(max_length=40, default=uuid.uuid4)

    # balance (in cents) in currency that a customer currently has during this billing period, negative means they owe money, postive is a credit towards their invoice
    balance = MoneyField(
        default=0, max_digits=10, decimal_places=2, default_currency="USD"
    )
    currency = models.CharField(max_length=3, default="USD")

    payment_provider_id = models.CharField(max_length=50, null=True, blank=True)

    properties = models.JSONField(default=dict, blank=True, null=True)

    def __str__(self) -> str:
        return str(self.name) + " " + str(self.customer_id)

    def get_billing_plan_name(self) -> str:
        subscription_object = Subscription.objects.filter(customer=self).first()
        if subscription_object is None:
            return "None"
        return subscription_object.billing_plan.get_plan_name()


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

    def __str__(self):
        if self.aggregation_type == self.AGGREGATION_TYPES.COUNT:
            return str(self.aggregation_type) + " of " + str(self.event_name)
        else:
            return (
                str(self.aggregation_type)
                + " of "
                + str(self.property_name)
                + " : "
                + str(self.event_name)
            )

    def get_aggregation_type(self):
        return self.aggregation_type


class BillingPlan(models.Model):
    """
    Billing_ID: Id for this specific plan
    time_created: self-explanatory
    currency: self-explanatory
    interval: determines whether plan charges weekly, monthly, or yearly
    flat_rate: amount to charge every week, month, or year (depending on choice of interval)
    billable_metrics: a json containing a list of billable_metrics objects
    """

    class INTERVAL_TYPES(object):
        WEEK = "week"
        MONTH = "month"
        YEAR = "year"

    INTERVAL_CHOICES = Choices(
        (INTERVAL_TYPES.WEEK, _("Week")),
        (INTERVAL_TYPES.MONTH, _("Month")),
        (INTERVAL_TYPES.YEAR, _("Year")),
    )

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=False)
    plan_id = models.CharField(
        max_length=36, blank=True, unique=True, default=uuid.uuid4
    )
    time_created = models.DateTimeField(auto_now=True)
    currency = models.CharField(max_length=30, default="USD")  # 30 is arbitrary
    interval = models.CharField(
        max_length=5,
        choices=INTERVAL_CHOICES,
        default=INTERVAL_CHOICES.month,
    )
    flat_rate = MoneyField(
        decimal_places=2, max_digits=8, default_currency="USD", default=0.0
    )
    pay_in_advance = models.BooleanField(default=False)
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
        else:  # fix!!! should not work
            print("none")
            return None

    def get_plan_name(self):
        return self.name

    def __str__(self) -> str:
        return str(self.name) + ":" + str(self.plan_id)


class PlanComponent(models.Model):
    billing_plan = models.ForeignKey(BillingPlan, on_delete=models.CASCADE)
    billable_metric = models.ForeignKey(BillableMetric, on_delete=models.CASCADE)

    free_metric_quantity = models.IntegerField(default=0)
    cost_per_metric = MoneyField(
        decimal_places=10, max_digits=14, default_currency="USD"
    )
    metric_amount_per_cost = models.IntegerField(default=1)

    def __str__(self):
        return str(self.billable_metric)


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

    class STATUS_TYPES(object):
        ACTIVE = "active"
        ENDED = "ended"
        NOT_STARTED = "not_started"

    STATUS_CHOICES = Choices(
        (STATUS_TYPES.ACTIVE, _("Active")),
        (STATUS_TYPES.ENDED, _("Ended")),
        (STATUS_TYPES.NOT_STARTED, _("Not Started")),
    )
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=False)
    billing_plan = models.ForeignKey(
        BillingPlan, on_delete=models.CASCADE, related_name="current_plan", null=False
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_CHOICES.not_started
    )
    auto_renew = models.BooleanField(default=True)
    next_plan = models.ForeignKey(
        BillingPlan,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="next_plan",
    )

    class Meta:
        constraints = [
            ExclusionConstraint(
                name="exclude_overlapping_subscriptions",
                expressions=(
                    (
                        TsTzRange("start_date", "end_date", RangeBoundary()),
                        RangeOperators.OVERLAPS,
                    ),
                    ("organization", RangeOperators.EQUAL),
                    ("customer", RangeOperators.EQUAL),
                    ("billing_plan", RangeOperators.EQUAL),
                )
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.next_plan:
            self.next_plan = self.billing_plan

        super(Subscription, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.customer.name}  {self.billing_plan.name} : {self.start_date} to {self.end_date}"


class Invoice(models.Model):
    class STATUS_TYPES(object):
        ISSUED = "issued"
        NOT_SENT = "not_sent"
        FULFILLED = "fulfilled"

    STATUS_CHOICES = Choices(
        (STATUS_TYPES.ISSUED, _("Issued")),
        (STATUS_TYPES.FULFILLED, _("Fullfilled")),
        (STATUS_TYPES.NOT_SENT, _("Not Sent")),
    )

    cost_due = models.IntegerField(default=0)
    issue_date = models.DateTimeField(max_length=100, auto_now=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=False)
    invoice_pdf = models.FileField(upload_to="invoices/", null=True, blank=True)
    subscription = models.ForeignKey(Subscription, on_delete=models.PROTECT)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_CHOICES.not_sent
    )
    line_items = ArrayField(base_field=models.JSONField(), null=True, blank=True)


class APIToken(AbstractAPIKey):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="api_keys"
    )
    name = models.CharField(max_length=200, default="latest_token")

    def __str__(self):
        return str(self.name) + " " + str(self.organization.name)

    class Meta(AbstractAPIKey.Meta):
        verbose_name = "API Token"
        verbose_name_plural = "API Tokens"
