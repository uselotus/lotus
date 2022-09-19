import uuid

from dateutil.parser import isoparse
from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import DateTimeRangeField
from django.db import models
from django.db.models import Func, Q
from django.db.models.constraints import UniqueConstraint
from django.db.models.signals import post_save
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
    stripe_id = models.CharField(max_length=110, blank=True, null=True)
    webhook_url = models.JSONField(default=dict, blank=True, null=True)
    created = models.DateField(auto_now=True)
    payment_plan = models.CharField(
        max_length=40, choices=PAYMENT_PLANS, default=PAYMENT_PLANS.self_hosted_free
    )

    def __str__(self):
        return self.company_name


class Alert(models.Model):
    type = models.CharField(max_length=20, default="webhook")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    webhook_url = models.CharField(max_length=300, blank=True, null=True)
    name = models.CharField(max_length=100, default=" ")


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
        customer_id (str): A :model:`metering_billing.Organization`'s internal designation for the customer.
        currency (str): The currency the customer is paying in.
        payment_provider_id (str): The id of the payment provider the customer is using.
        properties (dict): An extendable dictionary of properties, useful for filtering, etc.
        balance (:obj:`djmoney.models.fields.MoneyField`): The outstanding balance of the customer.
    """

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=False)
    name = models.CharField(max_length=100)
    customer_id = models.CharField(max_length=40)
    currency = models.CharField(max_length=3, default="USD")
    payment_provider_id = models.CharField(max_length=50, null=True, blank=True)
    properties = models.JSONField(default=dict, blank=True, null=True)
    balance = MoneyField(
        decimal_places=10, max_digits=20, default_currency="USD", default=0.0
    )
    currency = models.CharField(max_length=3, default="USD")

    payment_provider_id = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self) -> str:
        return str(self.name) + " " + str(self.customer_id)

    def get_billing_plan_name(self) -> str:
        subscription_set = Subscription.objects.filter(customer=self, status="active")
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


class BillableMetric(models.Model):
    class AGGREGATION_TYPES(object):
        COUNT = "count"
        SUM = "sum"
        MAX = "max"
        UNIQUE = "unique"

    AGGREGATION_CHOICES = Choices(
        (AGGREGATION_TYPES.COUNT, _("Count")),
        (AGGREGATION_TYPES.SUM, _("Sum")),
        (AGGREGATION_TYPES.MAX, _("Max")),
        (AGGREGATION_TYPES.UNIQUE, _("Unique")),
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

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=[
                    "organization",
                    "event_name",
                    "aggregation_type",
                    "property_name",
                ],
                name="unique_with_property_name",
            ),
            UniqueConstraint(
                fields=["organization", "event_name", "aggregation_type"],
                condition=Q(property_name=None),
                name="unique_without_property_name",
            ),
        ]

    def get_aggregation_type(self):
        return self.aggregation_type


class PlanComponent(models.Model):
    billable_metric = models.ForeignKey(BillableMetric, on_delete=models.CASCADE)

    free_metric_quantity = models.DecimalField(
        decimal_places=10, max_digits=20, default=0.0
    )
    cost_per_metric = MoneyField(
        decimal_places=10, max_digits=20, default_currency="USD"
    )
    metric_amount_per_cost = models.DecimalField(
        decimal_places=10, max_digits=20, default=1.0
    )

    def __str__(self):
        return str(self.billable_metric)


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
    time_created = models.DateTimeField(auto_now=True)
    currency = models.CharField(max_length=30, default="USD")  # 30 is arbitrary
    interval = models.CharField(
        max_length=5,
        choices=INTERVAL_CHOICES,
    )
    billing_plan_id = models.CharField(
        max_length=255, default=uuid.uuid4(), unique=True
    )
    flat_rate = MoneyField(decimal_places=10, max_digits=20, default_currency="USD")
    pay_in_advance = models.BooleanField()
    name = models.CharField(max_length=200, unique=True)
    description = models.CharField(max_length=256, default=" ", blank=True)
    components = models.ManyToManyField(PlanComponent, blank=True)

    def subscription_end_date(self, start_date):
        start_date_parsed = start_date
        if self.interval == "week":
            return start_date_parsed + relativedelta(weeks=+1) - relativedelta(days=+1)
        elif self.interval == "month":
            return start_date_parsed + relativedelta(months=+1) - relativedelta(days=+1)
        elif self.interval == "year":
            return start_date_parsed + relativedelta(years=+1) - relativedelta(days=+1)
        else:  # fix!!! should not work
            print("none")
            return None

    def __str__(self) -> str:
        return str(self.name)

    class Meta:
        unique_together = ("organization", "billing_plan_id")


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

    class SUB_STATUS_TYPES(object):
        ACTIVE = "active"
        ENDED = "ended"
        NOT_STARTED = "not_started"

    SUB_STATUS_CHOICES = Choices(
        (SUB_STATUS_TYPES.ACTIVE, _("Active")),
        (SUB_STATUS_TYPES.ENDED, _("Ended")),
        (SUB_STATUS_TYPES.NOT_STARTED, _("Not Started")),
    )
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=False)
    billing_plan = models.ForeignKey(BillingPlan, on_delete=models.CASCADE, null=False)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=SUB_STATUS_CHOICES,
        default=SUB_STATUS_CHOICES.not_started,
    )
    auto_renew = models.BooleanField(default=True)
    is_new = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.customer.name}  {self.billing_plan.name} : {self.start_date} to {self.end_date}"


class Invoice(models.Model):
    class INVOICE_STATUS_TYPES(object):
        ORG_NOT_CONNECTED_TO_STRIPE = "organization_not_connected_to_stripe"
        CUST_NOT_CONNECTED_TO_STRIPE = "customer_not_connected_to_stripe"
        REQUIRES_PAYMENT_METHOD = "requires_payment_method"
        REQUIRES_ACTION = "requires_action"
        PROCESSING = "processing"
        SUCCEEDED = "succeeded"

    INVOICE_STATUS_CHOICES = Choices(
        (INVOICE_STATUS_TYPES.REQUIRES_PAYMENT_METHOD, _("Requires Payment Method")),
        (INVOICE_STATUS_TYPES.REQUIRES_ACTION, _("Requires Action")),
        (INVOICE_STATUS_TYPES.PROCESSING, _("Processing")),
        (INVOICE_STATUS_TYPES.SUCCEEDED, _("Succeeded")),
        (
            INVOICE_STATUS_TYPES.ORG_NOT_CONNECTED_TO_STRIPE,
            _("Organization Not Connected to Stripe"),
        ),
        (
            INVOICE_STATUS_TYPES.CUST_NOT_CONNECTED_TO_STRIPE,
            _("Customer Not Connected to Stripe"),
        ),
    )

    cost_due = MoneyField(
        decimal_places=10, max_digits=20, default_currency="USD", default=0.0
    )
    issue_date = models.DateTimeField(max_length=100, auto_now=True)
    invoice_pdf = models.FileField(upload_to="invoices/", null=True, blank=True)
    status = models.CharField(max_length=40, choices=INVOICE_STATUS_CHOICES)
    payment_intent_id = models.CharField(max_length=240, null=True, blank=True)
    line_items = models.JSONField()
    organization = models.JSONField()
    customer = models.JSONField()
    subscription = models.JSONField()


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
