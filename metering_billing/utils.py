import collections
import datetime
from datetime import timezone
from decimal import ROUND_DOWN, ROUND_UP, Decimal
from enum import Enum

from dateutil import parser
from dateutil.relativedelta import relativedelta
from django.utils.translation import gettext_lazy as _
from model_utils import Choices


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

PAYMENT_PLANS = Choices(
    ("self_hosted_free", _("Self-Hosted Free")),
    ("cloud", _("Cloud")),
    ("self_hosted_enterprise", _("Self-Hosted Enterprise")),
)


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


class PAYMENT_PROVIDERS(object):
    STRIPE = "stripe"


SUPPORTED_PAYMENT_PROVIDERS = Choices(
    (PAYMENT_PROVIDERS.STRIPE, _("Stripe")),
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


class RevenueCalcGranularity(Enum):
    DAILY = "day"
    TOTAL = None


rev_calc_to_agg_keyword = {
    "daily": "date",
    "monthly": "month",
    "yearly": "year",
}

stateful_agg_period_to_agg_keyword = {
    "day": "date",
    "hour": "hour",
}


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


def convert_to_decimal(value):
    return Decimal(value).quantize(Decimal(".0000000001"), rounding=ROUND_UP)


def make_all_decimals_floats(json):
    if type(json) in [dict, collections.OrderedDict]:
        for key, value in json.items():
            if isinstance(value, dict) or isinstance(value, collections.OrderedDict):
                make_all_decimals_floats(value)
            elif isinstance(value, list):
                for item in value:
                    make_all_decimals_floats(item)
            elif isinstance(value, Decimal):
                json[key] = float(value)
    if isinstance(json, list):
        for item in json:
            make_all_decimals_floats(item)


def make_all_dates_times_strings(json):
    if type(json) in [
        dict,
        list,
        datetime.datetime,
        datetime.date,
        collections.OrderedDict,
    ]:
        for key, value in json.items():
            if isinstance(value, dict) or isinstance(value, collections.OrderedDict):
                make_all_dates_times_strings(value)
            elif isinstance(value, list):
                for item in value:
                    make_all_dates_times_strings(item)
            elif isinstance(value, datetime.datetime) or isinstance(
                value, datetime.date
            ):
                json[key] = str(value)


def make_all_datetimes_dates(json):
    if type(json) in [
        dict,
        list,
        datetime.datetime,
        collections.OrderedDict,
    ]:
        for key, value in json.items():
            if isinstance(value, dict) or isinstance(value, collections.OrderedDict):
                make_all_dates_times_strings(value)
            elif isinstance(value, list):
                for item in value:
                    make_all_dates_times_strings(item)
            elif isinstance(value, datetime.datetime):
                json[key] = value.date()


def years_bwn_twodates(start_date, end_date):
    years_btwn = relativedelta(end_date, start_date).years
    for n in range(years_btwn + 1):
        yield (start_date + relativedelta(years=n)).year


def months_bwn_twodates(start_date, end_date):
    months_btwn = (
        12 * relativedelta(end_date, start_date).years
        + relativedelta(end_date, start_date).months
    )
    for n in range(months_btwn + 1):
        next_date = start_date + relativedelta(months=n)
        yield (next_date.year, next_date.month)


def dates_bwn_twodates(start_date, end_date):
    days_btwn = (end_date - start_date).days
    for n in range(days_btwn + 1):
        yield start_date + relativedelta(days=n)


def hours_bwn_twodates(start_date, end_date):
    start_time = datetime.datetime.combine(
        start_date, datetime.time.min, tzinfo=timezone.utc
    )
    end_time = datetime.datetime.combine(
        end_date, datetime.time.max, tzinfo=timezone.utc
    )
    hours_btwn = abs(relativedelta(start_time, end_time).hours)
    for n in range(hours_btwn + 1):
        yield start_date + relativedelta(hours=n)


def turn_decimal_into_cents(amount):
    """
    Turn a decimal into cents.
    """
    return int(amount.quantize(Decimal(".01"), rounding=ROUND_DOWN) * Decimal(100))
