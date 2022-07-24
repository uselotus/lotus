from operator import mod
from django.db import models
import uuid
from model_utils import Choices
from djmoney.models.fields import MoneyField
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
import jsonfield

# Create your models here.

# Customer Model, Attempt 1
class Customer(models.Model):
    """
    Customer object. An explanation of the Customer's fields follows:
    first_name: self-explanatory
    last_name: self-explanatory
    billing_id: internal billing system identifier
    external_id: customer's id within the users backend system
    billing_address: currently set to null, but we will need to set this to an "address" object later
    company_name: self-explanatory
    email_address: self-explanatory
    phone_number: self-explanatory
    """

    first_name = models.CharField(max_length=30)  # 30 characters is arbitrary
    last_name = models.CharField(max_length=30)

    company_name = models.CharField(max_length=30, default=" ")

    # # auto generated when I typed "__init__, not sure what all this stuff is"


#    def __init__(self: _Self, *args, **kwargs) -> None:
#        super().__init__(*args, **kwargs)


class Event(models.Model):
    """
    Event object. An explanation of the Event's fields follows:
    event_name: The type of event that occurred.
    time_created: The time at which the event occurred.
    customer: The customer that the event occurred to.
    idempotency_id: A unique identifier for the event.
    """

    idempotency_id: models.AutoField = (
        "id",
        models.AutoField(primary_key=True, serialize=False, verbose_name="ID"),
    )
    customer: models.ForeignKey = models.ForeignKey(Customer, on_delete=models.CASCADE)
    event_name = models.CharField(max_length=200)
    time_created: models.CharField = models.CharField(max_length=100)
    properties: models.JSONField = models.JSONField(default=dict)

    def __str__(self):
        return str(self.event_type)


class BillingPlan(models.Model):
    """
    AGGREGATION_CHOICES: TODO
    Billing_ID: Id for this specific plan
    time_created: self-explanatory
    currency: self-explanatory
    interval: determines whether plan charges weekly, monthly, or yearly
    base_rate: amount to charge every week, month, or year (depending on choice of interval)
    billable_metrics: a json containing a list of billable_metrics objects
    """

    class AGGREGATION_TYPES(object):
        COUNT = "count"
        SUM = "sum"
        MAX = "max"

    AGGREGATION_CHOICES = Choices(
        (AGGREGATION_TYPES.COUNT, _("Count")),
        (AGGREGATION_TYPES.SUM, _("Sum")),
        (AGGREGATION_TYPES.MAX, _("Max")),
    )

    billing_id = models.CharField(
        max_length=36, blank=True, unique=True, default=uuid.uuid4
    )

    time_created = models.TimeField()
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

    # these are somewhat arbitrary, gotta look into these later
    base_rate = MoneyField(
        decimal_places=2, max_digits=8, default_currency="USD", default=0.0
    )

    # we may need to specify that the json will contain
    # BillableMetrics objects, but I'm not sure
    billable_metrics = jsonfield.JSONField(default=list)

    description = models.CharField(max_length=256, default=" ")
