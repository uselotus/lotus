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
    if isinstance(value, datetime.datetime):
        return value.date()
    elif isinstance(value, str):
        return convert_to_date(parser.parse(value))
    elif isinstance(value, datetime.date):
        return value
    else:
        raise Exception(f"can't convert type {type(value)} into date")


def convert_to_datetime(value, date_behavior="min"):
    if isinstance(value, datetime.datetime):
        return value.replace(tzinfo=pytz.UTC)
    elif isinstance(value, str):
        return convert_to_datetime(parser.parse(value))
    elif isinstance(value, datetime.date):
        if date_behavior == "min":
            return date_as_min_dt(value)
        elif date_behavior == "max":
            return date_as_max_dt(value)
    else:
        raise Exception(f"can't convert type {type(value)} into date")


def make_all_decimals_floats(data):
    if isinstance(data, list):
        return [make_all_decimals_floats(x) for x in data]
    elif isinstance(data, (dict, collections.OrderedDict)):
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
    elif isinstance(data, (dict, collections.OrderedDict)):
        return {
            make_all_dates_times_strings(key): make_all_dates_times_strings(val)
            for key, val in data.items()
        }
    elif isinstance(data, (datetime.date, datetime.datetime)):
        return str(data)
    else:
        return data


def make_all_datetimes_dates(data):
    if isinstance(data, list):
        return [make_all_datetimes_dates(x) for x in data]
    elif isinstance(data, (dict, collections.OrderedDict)):
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


def periods_bwn_twodates(
    granularity, start_time, end_time, truncate_to_granularity=False
):
    start_time = convert_to_datetime(start_time, date_behavior="min")
    end_time = convert_to_datetime(end_time, date_behavior="max")
    rd = relativedelta(start_time, end_time)
    if (
        granularity == USAGE_CALC_GRANULARITY.TOTAL
        or granularity == METRIC_GRANULARITY.TOTAL
        or granularity is None
    ):
        yield start_time
    else:
        if granularity == METRIC_GRANULARITY.SECOND:
            rd = relativedelta(seconds=+1)
            normalize_rd = relativedelta(microsecond=0)
        elif granularity == METRIC_GRANULARITY.MINUTE:
            normalize_rd = relativedelta(second=0, microsecond=0)
            rd = relativedelta(minutes=+1)
        elif granularity == METRIC_GRANULARITY.HOUR:
            normalize_rd = relativedelta(minute=0, second=0, microsecond=0)
            rd = relativedelta(hours=+1)
        elif (
            granularity == USAGE_CALC_GRANULARITY.DAILY
            or granularity == METRIC_GRANULARITY.DAY
        ):
            normalize_rd = relativedelta(hour=0, minute=0, second=0, microsecond=0)
            rd = relativedelta(days=+1)
        elif granularity == METRIC_GRANULARITY.MONTH:
            normalize_rd = relativedelta(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            rd = relativedelta(months=+1)
        elif granularity == METRIC_GRANULARITY.QUARTER:
            cur_quarter = (start_time.month - 1) // 3
            normalize_rd = relativedelta(
                month=cur_quarter * 4, day=1, hour=0, minute=0, second=0, microsecond=0
            )
            rd = relativedelta(months=+3)
        elif granularity == METRIC_GRANULARITY.YEAR:
            normalize_rd = relativedelta(
                month=1, day=1, hour=0, minute=0, second=0, microsecond=0
            )
            rd = relativedelta(years=+1)
        k = 1
        start_time = (
            start_time + normalize_rd if truncate_to_granularity else start_time
        )
        end_time = end_time + normalize_rd if truncate_to_granularity else end_time
        ret = start_time
        while ret < end_time:
            yield ret
            ret = start_time + k * rd
            k += 1


def now_plus_day():
    return datetime.datetime.now(datetime.timezone.utc) + relativedelta(days=+1)


def now_utc():
    return datetime.datetime.utcnow().replace(tzinfo=pytz.utc)


def now_utc_ts():
    return str(now_utc().timestamp())


def calculate_end_date(interval, start_date):
    if interval == PLAN_DURATION.MONTHLY:
        return start_date + relativedelta(months=+1)
    elif interval == PLAN_DURATION.QUARTERLY:
        return start_date + relativedelta(months=+3)
    elif interval == PLAN_DURATION.YEARLY:
        return start_date + relativedelta(years=+1)


def product_uuid():
    return "prod_" + str(uuid.uuid4().hex)


def customer_uuid():
    return "cust_" + str(uuid.uuid4().hex)


def metric_uuid():
    return "metric_" + str(uuid.uuid4().hex)


def plan_version_uuid():
    return "plnvrs_" + str(uuid.uuid4().hex)


def plan_uuid():
    return "plan_" + str(uuid.uuid4().hex)


def subscription_uuid():
    return "subs_" + str(uuid.uuid4().hex)


def backtest_uuid():
    return "btst_" + str(uuid.uuid4().hex)


def invoice_uuid():
    return "inv_" + str(uuid.uuid4().hex)


def organization_uuid():
    return "org_" + str(uuid.uuid4().hex)


def webhook_secret_uuid():
    return "whsec_" + str(uuid.uuid4().hex)


def webhook_endpoint_uuid():
    return "whend_" + str(uuid.uuid4().hex)


def date_as_min_dt(date):
    return datetime.datetime.combine(date, datetime.time.min, tzinfo=pytz.UTC)


def date_as_max_dt(date):
    return datetime.datetime.combine(date, datetime.time.max, tzinfo=pytz.UTC)
