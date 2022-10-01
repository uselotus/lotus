import email
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


class AGGREGATION_TYPES(object):
    COUNT = "count"
    SUM = "sum"
    MAX = "max"
    UNIQUE = "unique"
    LAST = "last"


AGGREGATION_CHOICES = Choices(
    (AGGREGATION_TYPES.COUNT, _("Count")),
    (AGGREGATION_TYPES.SUM, _("Sum")),
    (AGGREGATION_TYPES.MAX, _("Max")),
    (AGGREGATION_TYPES.UNIQUE, _("Unique")),
    (AGGREGATION_TYPES.LAST, _("Last")),
)

SUPPORTED_PAYMENT_PROVIDERS = Choices(
    ("stripe", _("Stripe")),
)


class EVENT_TYPES(object):
    AGGREGATION = "aggregation"
    STATEFUL = "stateful"


EVENT_CHOICES = Choices(
    (EVENT_TYPES.AGGREGATION, _("Aggregatable")),
    (EVENT_TYPES.STATEFUL, _("State Logging")),
)


class INTERVAL_TYPES(object):
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


INTERVAL_CHOICES = Choices(
    (INTERVAL_TYPES.WEEK, _("Week")),
    (INTERVAL_TYPES.MONTH, _("Month")),
    (INTERVAL_TYPES.YEAR, _("Year")),
)


class STATEFUL_AGG_PERIOD_TYPES(object):
    DAY = "day"
    HOUR = "hour"


STATEFUL_AGG_PERIOD_CHOICES = Choices(
    (STATEFUL_AGG_PERIOD_TYPES.DAY, _("Day")),
    (STATEFUL_AGG_PERIOD_TYPES.HOUR, _("Hour")),
)


class Organization(models.Model):
    PAYMENT_PLANS = Choices(
        ("self_hosted_free", _("Self-Hosted Free")),
        ("cloud", _("Cloud")),
        ("self_hosted_enterprise", _("Self-Hosted Enterprise")),
    )
    company_name = models.CharField(max_length=100, default=" ")
    stripe_id = models.CharField(max_length=110, blank=True, null=True)
    payment_provider_ids = models.JSONField(default=dict, blank=True, null=True)
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
    email = models.EmailField(unique=True)


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
    email = models.EmailField(max_length=100, blank=True, null=True)
    customer_id = models.CharField(max_length=40)
    currency = models.CharField(max_length=3, default="USD")
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
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_CHOICES,
        default=EVENT_CHOICES.aggregation,
        blank=False,
        null=False,
    )
    stateful_aggregation_period = models.CharField(
        max_length=20,
        choices=STATEFUL_AGG_PERIOD_CHOICES,
        blank=True,
        null=True,
    )
    billable_metric_name = models.CharField(
        max_length=200, null=False, blank=True, default=""
    )

    def default_name(self):
        if self.event_type == EVENT_CHOICES.aggregation:
            name = "[agg]"
        elif self.event_type == EVENT_CHOICES.stateful:
            name = "[state]"
        name += " " + self.aggregation_type + " of"
        if self.property_name not in ["", " ", None]:
            name += " " + self.property_name + " of"
        name += " " + self.event_name
        if self.stateful_aggregation_period:
            name += " per " + self.stateful_aggregation_period
        return name[:200]

    def save(self, *args, **kwargs):
        if self.billable_metric_name in ["", " ", None]:
            self.billable_metric_name = self.default_name()
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ("organization", "billable_metric_name")
        constraints = [
            UniqueConstraint(
                fields=[
                    "organization",
                    "event_name",
                    "aggregation_type",
                    "property_name",
                    "event_type",
                    "stateful_aggregation_period",
                ],
                name="unique_with_property_name_and_sap",
            ),
            UniqueConstraint(
                fields=[
                    "organization",
                    "event_name",
                    "aggregation_type",
                    "event_type",
                    "stateful_aggregation_period",
                ],
                condition=Q(property_name=None),
                name="unique_without_property_name_with_sap",
            ),
            UniqueConstraint(
                fields=[
                    "organization",
                    "event_name",
                    "aggregation_type",
                    "event_type",
                    "property_name",
                ],
                condition=Q(stateful_aggregation_period=None),
                name="unique_with_property_name_without_sap",
            ),
            UniqueConstraint(
                fields=["organization", "event_name", "aggregation_type", "event_type"],
                condition=Q(stateful_aggregation_period=None) & Q(property_name=None),
                name="unique_without_property_name_without_sap",
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
    cost_per_batch = MoneyField(
        decimal_places=10, max_digits=20, default_currency="USD", blank=True, null=True
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
    currency: self-explanatory
    interval: determines whether plan charges weekly, monthly, or yearly
    flat_rate: amount to charge every week, month, or year (depending on choice of interval)
    billable_metrics: a json containing a list of billable_metrics objects
    """

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=False)
    time_created = models.DateTimeField(auto_now=True)
    currency = models.CharField(max_length=30, default="USD")  # 30 is arbitrary
    interval = models.CharField(
        max_length=5,
        choices=INTERVAL_CHOICES,
    )
    billing_plan_id = models.CharField(max_length=255, default=uuid.uuid4, unique=True)
    flat_rate = MoneyField(decimal_places=10, max_digits=20, default_currency="USD")
    pay_in_advance = models.BooleanField()
    name = models.CharField(max_length=200, unique=True)
    description = models.CharField(max_length=256, default=" ", blank=True)
    components = models.ManyToManyField(PlanComponent, null=True, blank=True)
    features = models.ManyToManyField(Feature, null=True, blank=True)
    scheduled_for_deletion = models.BooleanField(default=False)
    replacement_billing_plan = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL
    )

    def __str__(self) -> str:
        return str(self.name)

    class Meta:
        unique_together = ("organization", "billing_plan_id")

    def calculate_end_date(self, start_date):
        if self.interval == "week":
            return start_date + relativedelta(weeks=+1) - relativedelta(days=+1)
        elif self.interval == "month":
            return start_date + relativedelta(months=+1) - relativedelta(days=+1)
        elif self.interval == "year":
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

    class SUB_STATUS_TYPES(object):
        ACTIVE = "active"
        ENDED = "ended"
        NOT_STARTED = "not_started"
        CANCELED = "canceled"

    SUB_STATUS_CHOICES = Choices(
        (SUB_STATUS_TYPES.ACTIVE, _("Active")),
        (SUB_STATUS_TYPES.ENDED, _("Ended")),
        (SUB_STATUS_TYPES.NOT_STARTED, _("Not Started")),
        (SUB_STATUS_TYPES.CANCELED, _("Canceled")),
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
    subscription_uid = models.CharField(
        max_length=100, null=False, blank=True, default=uuid.uuid4
    )

    def save(self, *args, **kwargs):
        if not self.end_date:
            self.end_date = self.billing_plan.calculate_end_date(self.start_date)
        super(Subscription, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.customer.name}  {self.billing_plan.name} : {self.start_date} to {self.end_date}"

    class Meta:
        unique_together = ("organization", "subscription_uid")


class Invoice(models.Model):
    class INVOICE_STATUS_TYPES(object):
        # REQUIRES_PAYMENT_METHOD = "requires_payment_method"
        # REQUIRES_ACTION = "requires_action"
        # PROCESSING = "processing"
        # SUCCEEDED = "succeeded"
        DRAFT = "draft"
        PAID = "paid"
        UNPAID = "unpaid"

    INVOICE_STATUS_CHOICES = Choices(
        (INVOICE_STATUS_TYPES.DRAFT, _("Draft")),
        (INVOICE_STATUS_TYPES.PAID, _("Paid")),
        (INVOICE_STATUS_TYPES.UNPAID, _("Unpaid")),
    )

    cost_due = MoneyField(
        decimal_places=10, max_digits=20, default_currency="USD", default=0.0
    )
    issue_date = models.DateTimeField(max_length=100, auto_now=True)
    invoice_pdf = models.FileField(upload_to="invoices/", null=True, blank=True)
    org_connected_to_cust_payment_provider = models.BooleanField(default=False)
    cust_connected_to_payment_provider = models.BooleanField(default=False)
    payment_status = models.CharField(max_length=40, choices=INVOICE_STATUS_CHOICES)
    external_payment_obj_id = models.CharField(max_length=240, null=True, blank=True)
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
