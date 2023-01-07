from django.db import models
from django.utils.translation import gettext_lazy as _


class INVOICE_STATUS(models.TextChoices):
    DRAFT = ("draft", _("Draft"))
    VOIDED = ("voided", _("Voided"))
    PAID = ("paid", _("Paid"))
    UNPAID = ("unpaid", _("Unpaid"))


class PAYMENT_PLANS(models.TextChoices):
    SELF_HOSTED_FREE = ("self_hosted_free", _("Self-Hosted Free"))
    CLOUD = ("cloud", _("Cloud"))
    SELF_HOSTED_ENTERPRISE = ("self_hosted_enterprise", _("Self-Hosted Enterprise"))


class PRICE_TIER_TYPE(models.TextChoices):
    FLAT = ("flat", _("Flat"))
    PER_UNIT = ("per_unit", _("Per Unit"))
    FREE = ("free", _("Free"))


class BATCH_ROUNDING_TYPE(models.TextChoices):
    ROUND_UP = ("round_up", _("Round Up"))
    ROUND_DOWN = ("round_down", _("Round Down"))
    ROUND_NEAREST = ("round_nearest", _("Round Nearest"))
    NO_ROUNDING = ("no_rounding", _("No Rounding"))


class METRIC_AGGREGATION(models.TextChoices):
    COUNT = ("count", _("Count"))
    SUM = ("sum", _("Sum"))
    MAX = ("max", _("Max"))
    UNIQUE = ("unique", _("Unique"))
    LATEST = ("latest", _("Latest"))
    AVERAGE = ("average", _("Average"))


class PRICE_ADJUSTMENT_TYPE(models.TextChoices):
    PERCENTAGE = ("percentage", _("Percentage"))
    FIXED = ("fixed", _("Fixed"))
    PRICE_OVERRIDE = ("price_override", _("Price Override"))


class PAYMENT_PROVIDERS(models.TextChoices):
    STRIPE = ("stripe", _("Stripe"))


class METRIC_TYPE(models.TextChoices):
    COUNTER = ("counter", _("Counter"))
    STATEFUL = ("stateful", _("Stateful"))
    RATE = ("rate", _("Rate"))
    CUSTOM = ("custom", _("Custom"))


class CUSTOMER_BALANCE_ADJUSTMENT_STATUS(models.TextChoices):
    ACTIVE = ("active", _("Active"))
    INACTIVE = ("inactive", _("Inactive"))


class METRIC_GRANULARITY(models.TextChoices):
    SECOND = ("seconds", _("Second"))
    MINUTE = ("minutes", _("Minute"))
    HOUR = ("hours", _("Hour"))
    DAY = ("days", _("Day"))
    MONTH = ("months", _("Month"))
    QUARTER = ("quarters", _("Quarter"))
    YEAR = ("years", _("Year"))
    TOTAL = ("total", _("Total"))


class EVENT_TYPE(models.TextChoices):
    DELTA = ("delta", _("Delta"))
    TOTAL = ("total", _("Total"))


class PLAN_DURATION(models.TextChoices):
    MONTHLY = ("monthly", _("Monthly"))
    QUARTERLY = ("quarterly", _("Quarterly"))
    YEARLY = ("yearly", _("Yearly"))


class USAGE_BILLING_FREQUENCY(models.TextChoices):
    MONTHLY = ("monthly", _("Monthly"))
    QUARTERLY = ("quarterly", _("Quarterly"))
    END_OF_PERIOD = ("end_of_period", _("End of Period"))


class COMPONENT_RESET_FREQUENCY(models.TextChoices):
    WEEKLY = ("weekly", _("Weekly"))
    MONTHLY = ("monthly", _("Monthly"))
    QUARTERLY = ("quarterly", _("Quarterly"))
    NONE = ("none", _("None"))


class FLAT_FEE_BILLING_TYPE(models.TextChoices):
    IN_ARREARS = ("in_arrears", _("In Arrears"))
    IN_ADVANCE = ("in_advance", _("In Advance"))


class USAGE_CALC_GRANULARITY(models.TextChoices):
    DAILY = ("day", _("Daily"))
    TOTAL = ("total", _("Total"))


class NUMERIC_FILTER_OPERATORS(models.TextChoices):
    GTE = ("gte", _("Greater than or equal to"))
    GT = ("gt", _("Greater than"))
    EQ = ("eq", _("Equal to"))
    LT = ("lt", _("Less than"))
    LTE = ("lte", _("Less than or equal to"))


class CATEGORICAL_FILTER_OPERATORS(models.TextChoices):
    ISIN = ("isin", _("Is in"))
    ISNOTIN = ("isnotin", _("Is not in"))


class SUBSCRIPTION_STATUS(models.TextChoices):
    ACTIVE = ("active", _("Active"))
    ENDED = ("ended", _("Ended"))
    NOT_STARTED = ("not_started", _("Not Started"))


class PLAN_VERSION_STATUS(models.TextChoices):
    ACTIVE = ("active", _("Active"))
    RETIRING = ("retiring", _("Retiring"))
    GRANDFATHERED = ("grandfathered", _("Grandfathered"))
    ARCHIVED = ("archived", _("Archived"))
    INACTIVE = ("inactive", _("Inactive"))


class PLAN_STATUS(models.TextChoices):
    ACTIVE = ("active", _("Active"))
    ARCHIVED = ("archived", _("Archived"))
    EXPERIMENTAL = ("experimental", _("Experimental"))


class BACKTEST_KPI(models.TextChoices):
    TOTAL_REVENUE = ("total_revenue", _("Total Revenue"))


class BACKTEST_STATUS(models.TextChoices):
    RUNNING = ("running", _("Running"))
    COMPLETED = ("completed", _("Completed"))
    FAILED = ("failed", _("Failed"))


class PRODUCT_STATUS(models.TextChoices):
    ACTIVE = ("active", _("Active"))
    ARCHIVED = ("archived", _("Archived"))


class METRIC_STATUS(models.TextChoices):
    ACTIVE = ("active", _("Active"))
    ARCHIVED = ("archived", _("Archived"))


class MAKE_PLAN_VERSION_ACTIVE_TYPE(models.TextChoices):
    REPLACE_IMMEDIATELY = ("replace_immediately", _("Replace Immediately"))
    REPLACE_ON_ACTIVE_VERSION_RENEWAL = (
        "replace_on_active_version_renewal",
        _("Replace on Active Version Renewal"),
    )
    GRANDFATHER_ACTIVE = ("grandfather_active", _("Grandfather Active"))


class REPLACE_IMMEDIATELY_TYPE(models.TextChoices):
    END_CURRENT_SUBSCRIPTION_AND_BILL = (
        "end_current_subscription_and_bill",
        _("End Current Subscription and Bill"),
    )
    END_CURRENT_SUBSCRIPTION_DONT_BILL = (
        "end_current_subscription_dont_bill",
        _("End Current Subscription and Don't Bill"),
    )
    CHANGE_SUBSCRIPTION_PLAN = (
        "change_subscription_plan",
        _("Change Subscription Plan"),
    )


class ORGANIZATION_STATUS(models.TextChoices):
    ACTIVE = ("Active", _("Active"))
    INVITED = ("Invited", _("Invited"))


class WEBHOOK_TRIGGER_EVENTS(models.TextChoices):
    INVOICE_CREATED = ("invoice.created", _("invoice.created"))
    INVOICE_PAID = ("invoice.paid", _("invoice.paid"))


class FLAT_FEE_BEHAVIOR(models.TextChoices):
    REFUND = ("refund", _("Refund"))
    PRORATE = ("prorate", _("Prorate"))
    CHARGE_FULL = ("charge_full", _("Charge Full"))


class USAGE_BEHAVIOR(models.TextChoices):
    TRANSFER_TO_NEW_SUBSCRIPTION = (
        "transfer_to_new_subscription",
        _("Transfer to New Subscription"),
    )
    KEEP_SEPARATE = ("keep_separate", _("Keep Separate"))


class INVOICING_BEHAVIOR(models.TextChoices):
    ADD_TO_NEXT_INVOICE = ("add_to_next_invoice", _("Add to Next Invoice"))
    INVOICE_NOW = ("invoice_now", _("Invoice Now"))


class CHARGEABLE_ITEM_TYPE(models.TextChoices):
    USAGE_CHARGE = ("usage_charge", _("Usage Charge"))
    RECURRING_CHARGE = ("recurring_charge", _("Recurring Charge"))
    ONE_TIME_CHARGE = ("one_time_charge", _("One Time Charge"))
    PLAN_ADJUSTMENT = ("plan_adjustment", _("Plan Adjustment"))
    CUSTOMER_ADJUSTMENT = ("customer_adjustment", _("Customer Adjustment"))
    TAX = ("tax", _("Tax"))


SUPPORTED_CURRENCIES = [
    ("US Dollar", "USD", "$"),
    ("Euro", "EUR", "€"),
    ("Pound", "GBP", "£"),
    ("Yuan", "CNY", "¥"),
    ("Australian Dollar", "AUD", "A$"),
    ("Canadian Dollar", "CAD", "C$"),
    ("Swiss Franc", "CHF", "CHF"),
    ("Hong Kong Dollar", "HKD", "HK$"),
    ("Singapore Dollar", "SGD", "S$"),
    ("Swedish Krona", "SEK", "kr"),
    ("Norwegian Krone", "NOK", "kr"),
    ("New Zealand Dollar", "NZD", "NZ$"),
    ("Mexican Peso", "MXN", "$"),
    ("South African Rand", "ZAR", "R"),
    ("Brazilian Real", "BRL", "R$"),
    ("Danish Krone", "DKK", "kr"),
]
SUPPORTED_CURRENCIES_VERSION = 1


class ACCOUNTS_RECEIVABLE_TRANSACTION_TYPES(models.IntegerChoices):
    INVOICE = (1, _("Invoice"))
    RECEIPT = (2, _("Receipt"))
    ADJUSTMENT = (3, _("Adjustment"))
    REVERSAL = (4, _("Reversal"))


class USAGE_BILLING_BEHAVIOR(models.TextChoices):
    BILL_FULL = ("bill_full", _("Bill Full"))
    BILL_NONE = ("bill_none", _("Bill None"))


class ORGANIZATION_SETTING_NAMES(models.TextChoices):
    GENERATE_CUSTOMER_IN_STRIPE_AFTER_LOTUS = (
        "generate_customer_after_creating_in_lotus",
        _("Generate in Stripe after Lotus"),
    )
    SUBSCRIPTION_FILTERS = ("subscription_filters", _("Subscription Filters"))


class TAG_GROUP(models.TextChoices):
    PLAN = ("plan", _("Plan"))
