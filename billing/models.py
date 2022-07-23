from operator import mod
from django.db import models
import uuid
from model_utils import Choices
from django.utils.translation import gettext_lazy as _


# Create your models here.

# Customer Model, Attempt 1
class Customer(models.Model):
    """
    Customer object. An explanation of the Customer's fields follows:
    first_name: self-explanatory
    last_name: self-explanatory
    billing_id: internal billing system identifier
    system_id: customer's id within the users backend system
    billing_address: currently set to null, but we will need to set this to an "address" object later
    email_address: self-explanatory
    phone_number: self-explanatory
    balance: An amount of money that the customer owes the company.
             If the number is positive, the customer owes money to the company,
             if negative, then the company owes money to the customer.
    time_created: The time at which the customer object was created
    default_payment_source: The customer's payment method. Currently set to a string,
                            but will probably need to be a full-on 'payment' object in the future.
    discount: The discount that applies to this customer, if any. Will need a "discount" object in the future.
    invoice_prefix: A prefix string to put on the customer's invoice, so that we may generate unique invoice numbers
    invoice_settings: The customer's default invoice settings
    next_invoice_sequence: Suffix of the customer's next invoice number (i.e. counting number for invoices)
    preferred_locales: Customer's preferred languages, ordered by preference
    subscriptions: Customer's current subscriptions. Need to make into a list or array of subscription objects
    tax: Tax details for the customer. Will need to expand on later.
    tax_exempt: String that takes 1 of 3 values:
                1. none
                2. exempt
                3. reverse

    tax_ids: Customer's tax IDs.
    test_clock: ID of test_clock this customer belongs to

    """

    first_name = models.CharField(max_length=30)  # 30 characters is arbitrary
    last_name = models.CharField(max_length=30)
    billing_id = models.CharField(
        max_length=100, blank=True, unique=True, default=uuid.uuid4
    )
    system_id = models.CharField(max_length=100, unique=True)
    # billing_address = null
    email_address = models.CharField(max_length=30)  # 30 chars is arbitrary
    phone_number = models.CharField(max_length=30)
    # balance = MoneyField(
    #     decimal_places=2,
    #     default=0,
    #     default_currency="USD",
    #     max_digits=11,
    # )

    time_created: models.DateField = models.DateTimeField(auto_now_add=True)
    default_payment_source = models.CharField(
        max_length=60
    )  # 60 characters is arbitrary,
    # discount = null
    invoice_prefix = models.CharField(max_length=30)  # 30 chars is arbitrary
    # invoice_settings = null
    next_invoice_sequence = models.CharField(max_length=30)  # 30 chars arbitrary
    # preferred_locales = ArrayField(
    #     models.CharField(max_length=30), blank=True, size=3
    # )  # I think 3 is the number of languages, not sure
    # subscriptions = ArrayField(null, size=10)
    # tax = null
    tax_exempt = models.CharField(max_length=30)


class Event(models.Model):
    """ """

    id: models.AutoField = (
        "id",
        models.AutoField(
            auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
        ),
    )
    customer: models.ForeignKey = models.ForeignKey(Customer, on_delete=models.CASCADE)
    event_name = models.CharField(max_length=200)
    time_created: models.DateField = models.DateTimeField(auto_now_add=True)

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
    object = "plan"
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
