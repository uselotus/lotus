import collections
import datetime
import uuid
from datetime import timezone
from decimal import ROUND_DOWN, ROUND_UP, Decimal

import pytz
from dateutil import parser
from dateutil.relativedelta import relativedelta
from django.utils.translation import gettext_lazy as _
from metering_billing.utils.enums import (
    METRIC_GRANULARITY,
    PLAN_DURATION,
    USAGE_CALC_GRANULARITY,
)
from numpy import isin


def convert_to_decimal(value):
    return Decimal(value).quantize(Decimal(".0000000001"), rounding=ROUND_UP)

def convert_to_date(value):
    if isinstance(value, datetime.date):
        return value
    elif isinstance(value, datetime.datetime):
        return value.date()
    elif isinstance(value, str):
        return convert_to_date(parser.parse(value))
    else:
        raise Exception(f"can't convert type {type(value)} into date")

def make_all_decimals_floats(data):
    if isinstance(data, list):
        return [make_all_decimals_floats(x) for x in data]
    elif isinstance(data, dict) or isinstance(data, collections.OrderedDict):
        return {
            make_all_decimals_floats(key): make_all_decimals_floats(val)
            for key, val in data.items()
        }
    elif isinstance(data, Decimal):
        return float(data)
    else:
        return data


def make_all_dates_times_strings(data):
    if isinstance(data, list):
        return [make_all_dates_times_strings(x) for x in data]
    elif isinstance(data, dict) or isinstance(data, collections.OrderedDict):
        return {
            make_all_dates_times_strings(key): make_all_dates_times_strings(val)
            for key, val in data.items()
        }
    elif isinstance(data, datetime.date) or isinstance(data, datetime.datetime):
        return str(data)
    else:
        return data


def make_all_datetimes_dates(data):
    if isinstance(data, list):
        return [make_all_datetimes_dates(x) for x in data]
    elif isinstance(data, dict) or isinstance(data, collections.OrderedDict):
        return {
            make_all_datetimes_dates(key): make_all_datetimes_dates(val)
            for key, val in data.items()
        }
    elif isinstance(data, datetime.datetime):
        return data.date()
    else:
        return data


def years_bwn_twodates(start_date, end_date):
    years_btwn = relativedelta(end_date, start_date).years
    for n in range(years_btwn + 1):
        yield (start_date + relativedelta(years=n)).year


def months_bwn_two_dates(start_date, end_date):
    months_btwn = (
        12 * relativedelta(end_date, start_date).years
        + relativedelta(end_date, start_date).months
    )
    for n in range(months_btwn + 1):
        next_date = start_date + relativedelta(months=n)
        yield (next_date.year, next_date.month)


def dates_bwn_two_dts(start_date, end_date):
    if isinstance(start_date, datetime.datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime.datetime):
        end_date = end_date.date()
    days_btwn = (end_date - start_date).days
    for n in range(days_btwn + 1):
        yield start_date + relativedelta(days=n)


def hours_bwn_twodates(start_date, end_date):
    start_time = date_as_min_dt(start_date)
    end_time = date_as_max_dt(end_date)
    hours_btwn = abs(relativedelta(start_time, end_time).hours)
    for n in range(hours_btwn + 1):
        yield start_date + relativedelta(hours=n)


def decimal_to_cents(amount):
    """
    Turn a decimal into cents.
    """
    return int(amount.quantize(Decimal(".01"), rounding=ROUND_DOWN) * Decimal(100))


def periods_bwn_twodates(granularity, start_date, end_date):
    start_time = date_as_min_dt(start_date)
    end_time = date_as_max_dt(end_date)
    rd = relativedelta(start_time, end_time)
    if (
        granularity == USAGE_CALC_GRANULARITY.TOTAL
        or granularity == METRIC_GRANULARITY.TOTAL
    ):
        periods_btwn = 0
    elif granularity == METRIC_GRANULARITY.HOUR:
        periods_btwn = (
            rd.years * 365 * 24 + rd.months * 30 * 24 + rd.days * 24 + rd.hours
        )
    elif (
        granularity == USAGE_CALC_GRANULARITY.DAILY
        or granularity == METRIC_GRANULARITY.DAY
    ):
        periods_btwn = rd.years * 365 + rd.months * 30 + rd.days
    elif granularity == METRIC_GRANULARITY.WEEK:
        periods_btwn = rd.years * 52 + rd.months * 4 + rd.weeks
    elif granularity == METRIC_GRANULARITY.MONTH:
        periods_btwn = rd.years * 12 + rd.months
    periods_btwn = abs(periods_btwn)
    for n in range(periods_btwn + 1):
        if (
            granularity == USAGE_CALC_GRANULARITY.TOTAL
            or granularity == METRIC_GRANULARITY.TOTAL
        ):
            res = start_time
        elif granularity == METRIC_GRANULARITY.HOUR:
            res = start_time + relativedelta(hours=n)
        elif (
            granularity == USAGE_CALC_GRANULARITY.DAILY
            or granularity == METRIC_GRANULARITY.DAY
        ):
            res = start_time + relativedelta(days=n)
        elif granularity == METRIC_GRANULARITY.WEEK:
            res = start_time + relativedelta(weeks=n)
        elif granularity == METRIC_GRANULARITY.MONTH:
            res = start_time + relativedelta(months=n)
        if res <= end_time:
            yield res


def now_plus_day():
    return datetime.datetime.now(datetime.timezone.utc) + relativedelta(days=+1)


def now_utc():
    return datetime.datetime.utcnow().replace(tzinfo=pytz.utc)


def now_utc_ts():
    return str(now_utc().timestamp())


def calculate_end_date(interval, start_date):
    if interval == PLAN_DURATION.MONTHLY:
        return start_date + relativedelta(months=+1) - relativedelta(days=+1)
    elif interval == PLAN_DURATION.QUARTERLY:
        return start_date + relativedelta(months=+3) - relativedelta(days=+1)
    elif interval == PLAN_DURATION.YEARLY:
        return start_date + relativedelta(years=+1) - relativedelta(days=+1)


def product_uuid():
    return "prod_" + str(uuid.uuid4())


def customer_uuid():
    return "cust_" + str(uuid.uuid4())


def metric_uuid():
    return "metric_" + str(uuid.uuid4())


def plan_version_uuid():
    return "plnvrs_" + str(uuid.uuid4())


def plan_uuid():
    return "plan_" + str(uuid.uuid4())


def subscription_uuid():
    return "subs_" + str(uuid.uuid4())


def backtest_uuid():
    return "btst_" + str(uuid.uuid4())


def invoice_uuid():
    return "inv_" + str(uuid.uuid4())


def organization_uuid():
    return "org_" + str(uuid.uuid4())


def date_as_min_dt(date):
    return datetime.datetime.combine(date, datetime.time.min, tzinfo=pytz.UTC)


def date_as_max_dt(date):
    return datetime.datetime.combine(date, datetime.time.max, tzinfo=pytz.UTC)
