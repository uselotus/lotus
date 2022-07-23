from operator import mod
from django.db import models
import uuid
from model_utils import Choices
from djmoney.models.fields import MoneyField
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField


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

    company_name = models.CharField(max_length=30)

    def __init__(self: _Self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)


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
    id: self-explanatory
    active: if true, the plan can be used for new purchases, false otherwise
    aggregate_usage: Specifies a usage aggregation strategy for plans of usage_type=metered.
                     Allowed values are:
                     sum
                     last_during_period
                     last_ever
                     max.

                     Defaults to sum.
    amount: The unit amount in cents to be charged, represented as a whole integer if possible.
            Only set if billing_scheme=per_unit.
    amount_decimal: The unit amount in cents to be charged, represented as a decimal string with
                    at most 12 decimal places. Only set if billing_scheme=per_unit.
    billing_scheme: Describes how to compute the price per period. Either per_unit or tiered.
    time_created: Time at which the object was created. Measured in seconds since the Unix epoch.
    interval: The frequency at which a subscription is billed. One of day, week, month or year.
    interval_count: The number of intervals (specified in the interval attribute) between subscription billings. For example, interval=month and interval_count=3 bills every 3 months.
    livemode: True if Customer object exists in live mode, False if Customer object exists in test mode
    metadata: Set of key-value pairs that you can attach to an object. This can be useful for storing additional information about the object in a structured format.
    tiers: Each element represents a pricing tier. This parameter requires billing_scheme to be set to tiered. See also the documentation for billing_scheme. This field is not included by default. To include it in the response, expand the tiers field
    tiers_mode: Defines if the tiering price should be graduated or volume based. In volume-based tiering, the maximum quantity within a period determines the per unit price. In graduated tiering, pricing can change as the quantity grows.
    transform_usage: Apply a transformation to the reported usage or set quantity before computing the amount billed. Cannot be combined with tiers.
    trial_period_days: Default number of trial days when subscribing a customer to this plan using trial_from_plan=true.
    usage_type: Configures how the quantity per period should be determined. Can be either metered or licensed. licensed automatically bills the quantity set when adding it to a subscription. metered aggregates the total usage based on usage records. Defaults to licensed.
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
    active = models.BooleanField()
    amount = models.IntegerField()
    amount_decimal = models.DecimalField(decimal_places=2, max_digits=11)
    billing_scheme = models.CharField(max_length=30)
    time_created = models.TimeField()
    currency = "usd"

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

    interval_count = models.IntegerField()
    # metadata = null
    nickname = models.CharField(max_length=30)  # 30 chars is arbitrary
    product = models.CharField(max_length=30)  # 30 chars is arbitrary
    tiers_mode = models.CharField(max_length=30)  # 30 chars is arbitrary
    # transform_usage = null
    trial_period_days = models.IntegerField()

    class possible_usage_types(models.TextChoices):
        LICENSED = "LI", _("Licensed")
        METERED = "ME", _("Metered")

    usage_type = models.CharField(
        max_length=2,
        choices=possible_usage_types.choices,
        default=possible_usage_types.METERED,
    )
