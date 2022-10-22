import collections
import datetime
from datetime import timezone
from decimal import ROUND_DOWN, ROUND_UP, Decimal

import pytz
from dateutil.relativedelta import relativedelta
from django.utils.translation import gettext_lazy as _
from metering_billing.utils.enums import PLAN_DURATION, REVENUE_CALC_GRANULARITY


def convert_to_decimal(value):
    return Decimal(value).quantize(Decimal(".0000000001"), rounding=ROUND_UP)


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


def periods_bwn_twodates(granularity, start_date, end_date):
    start_time = datetime.datetime.combine(
        start_date, datetime.time.min, tzinfo=datetime.timezone.utc
    )
    end_time = datetime.datetime.combine(
        end_date, datetime.time.max, tzinfo=datetime.timezone.utc
    )
    rd = relativedelta(start_time, end_time)
    if granularity == REVENUE_CALC_GRANULARITY.TOTAL:
        periods_btwn = 0
    # elif granularity == REVENUE_CALC_GRANULARITY.HOUR:
    #     periods_btwn = (
    #         rd.years * 365 * 24 + rd.months * 30 * 24 + rd.days * 24 + rd.hours
    #     )
    elif granularity == REVENUE_CALC_GRANULARITY.DAILY:
        periods_btwn = rd.years * 365 + rd.months * 30 + rd.days
    # elif granularity == REVENUE_CALC_GRANULARITY.WEEK:
    #     periods_btwn = rd.years * 52 + rd.months * 4 + rd.weeks
    # elif granularity == REVENUE_CALC_GRANULARITY.MONTH:
    #     periods_btwn = rd.years * 12 + rd.months
    periods_btwn = abs(periods_btwn)
    for n in range(periods_btwn + 1):
        if granularity == REVENUE_CALC_GRANULARITY.TOTAL:
            yield start_time
        # elif granularity == REVENUE_CALC_GRANULARITY.HOUR:
        #     yield start_time + relativedelta(hours=n)
        elif granularity == REVENUE_CALC_GRANULARITY.DAILY:
            yield start_time + relativedelta(days=n)
        # elif granularity == REVENUE_CALC_GRANULARITY.WEEK:
        #     yield start_time + relativedelta(weeks=n)
        # elif granularity == REVENUE_CALC_GRANULARITY.MONTH:
        #     yield start_time + relativedelta(months=n)


def now_plus_day():
    return datetime.datetime.now(datetime.timezone.utc) + relativedelta(days=+1)


def dates_bwn_twodates(start_date, end_date):
    days_btwn = (end_date - start_date).days
    for n in range(days_btwn + 1):
        yield start_date + relativedelta(days=n)


def now_utc():
    return datetime.datetime.utcnow().replace(tzinfo=pytz.utc)


def calculate_end_date(interval, start_date):
    if interval == PLAN_DURATION.MONTH:
        return start_date + relativedelta(months=+1) - relativedelta(days=+1)
    elif interval == PLAN_DURATION.YEAR:
        return start_date + relativedelta(years=+1) - relativedelta(days=+1)
