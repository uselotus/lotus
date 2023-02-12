import collections
import datetime
import uuid
from collections import OrderedDict, namedtuple
from collections.abc import MutableMapping, MutableSequence
from decimal import ROUND_DOWN, ROUND_UP, Decimal

import pytz
from dateutil import parser
from dateutil.relativedelta import relativedelta
from django.db.models import Field, Model
from metering_billing.exceptions.exceptions import ServerError
from metering_billing.utils.enums import (
    METRIC_GRANULARITY,
    PLAN_DURATION,
    USAGE_CALC_GRANULARITY,
)

ModelType = type[Model]
Fields = list[Field]


def make_hashable(obj):
    if isinstance(obj, MutableSequence):
        return tuple(make_hashable(x) for x in obj)
    elif isinstance(obj, set):
        return frozenset(make_hashable(x) for x in obj)
    elif isinstance(obj, MutableMapping):
        return OrderedDict((make_hashable(k), make_hashable(v)) for k, v in obj.items())
    else:
        return obj


def convert_to_decimal(value):
    if value is None:
        return Decimal(0)
    return Decimal(value).quantize(Decimal(".0000000001"), rounding=ROUND_UP)


def convert_to_date(value):
    if isinstance(value, datetime.datetime):
        return value.date()
    elif isinstance(value, str):
        return convert_to_date(parser.parse(value))
    elif isinstance(value, datetime.date):
        return value
    else:
        raise ServerError(f"can't convert type {type(value)} into date")


def convert_to_datetime(value, date_behavior="min", tz=pytz.UTC):
    if isinstance(value, datetime.datetime):
        return value.replace(tzinfo=pytz.UTC)
    elif isinstance(value, str):
        return convert_to_datetime(parser.parse(value))
    elif isinstance(value, datetime.date):
        if date_behavior == "min":
            return date_as_min_dt(value, timezone=tz)
        elif date_behavior == "max":
            return date_as_max_dt(value, timezone=tz)
    else:
        raise ServerError(f"can't convert type {type(value)} into date")


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
    i = 0
    while start_date + relativedelta(days=i) <= end_date:
        yield start_date + relativedelta(days=i)
        i += 1


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
        while ret <= end_time:
            yield ret
            ret = start_time + k * rd
            k += 1


def now_plus_day():
    return datetime.datetime.now(datetime.timezone.utc) + relativedelta(days=+1)


def now_utc():
    return datetime.datetime.utcnow().replace(tzinfo=pytz.utc)


def now_utc_ts():
    return str(now_utc().timestamp())


def get_granularity_ratio(metric_granularity, proration_granularity, start_date):
    if (
        proration_granularity == METRIC_GRANULARITY.TOTAL
        or proration_granularity is None
    ):
        return 1
    granularity_dict = {
        METRIC_GRANULARITY.SECOND: {
            METRIC_GRANULARITY.SECOND: 1,
        },
        METRIC_GRANULARITY.MINUTE: {
            METRIC_GRANULARITY.SECOND: 60,
            METRIC_GRANULARITY.MINUTE: 1,
        },
        METRIC_GRANULARITY.HOUR: {
            METRIC_GRANULARITY.SECOND: 60 * 60,
            METRIC_GRANULARITY.MINUTE: 60,
            METRIC_GRANULARITY.HOUR: 1,
        },
        METRIC_GRANULARITY.DAY: {
            METRIC_GRANULARITY.SECOND: 24 * 60 * 60,
            METRIC_GRANULARITY.MINUTE: 24 * 60,
            METRIC_GRANULARITY.HOUR: 24,
            METRIC_GRANULARITY.DAY: 1,
        },
    }
    plus_month = start_date + relativedelta(months=1)
    days_in_month = (plus_month - start_date).days
    granularity_dict[METRIC_GRANULARITY.MONTH] = {
        METRIC_GRANULARITY.SECOND: days_in_month * 24 * 60 * 60,
        METRIC_GRANULARITY.MINUTE: days_in_month * 24 * 60,
        METRIC_GRANULARITY.HOUR: days_in_month * 24,
        METRIC_GRANULARITY.DAY: days_in_month,
        METRIC_GRANULARITY.MONTH: 1,
    }
    plus_quarter = start_date + relativedelta(months=3)
    days_in_quarter = (plus_quarter - start_date).days
    granularity_dict[METRIC_GRANULARITY.QUARTER] = {
        METRIC_GRANULARITY.SECOND: days_in_quarter * 24 * 60 * 60,
        METRIC_GRANULARITY.MINUTE: days_in_quarter * 24 * 60,
        METRIC_GRANULARITY.HOUR: days_in_quarter * 24,
        METRIC_GRANULARITY.DAY: days_in_quarter,
        METRIC_GRANULARITY.MONTH: 3,
        METRIC_GRANULARITY.QUARTER: 1,
    }
    plus_year = start_date + relativedelta(years=1)
    days_in_year = (plus_year - start_date).days
    granularity_dict[METRIC_GRANULARITY.YEAR] = {
        METRIC_GRANULARITY.SECOND: days_in_year * 24 * 60 * 60,
        METRIC_GRANULARITY.MINUTE: days_in_year * 24 * 60,
        METRIC_GRANULARITY.HOUR: days_in_year * 24,
        METRIC_GRANULARITY.DAY: days_in_year,
        METRIC_GRANULARITY.MONTH: 12,
        METRIC_GRANULARITY.QUARTER: 4,
        METRIC_GRANULARITY.YEAR: 1,
    }
    return granularity_dict[metric_granularity][proration_granularity]


def calculate_end_date(
    interval, start_date, timezone, day_anchor=None, month_anchor=None
):
    if interval == PLAN_DURATION.MONTHLY:
        end_date = date_as_max_dt(
            start_date + relativedelta(months=+1, days=-1), timezone
        )
        if day_anchor:
            tentative_end_date = date_as_max_dt(
                start_date + relativedelta(day=day_anchor, days=-1), timezone
            )
            if tentative_end_date > start_date:
                end_date = tentative_end_date
            else:
                end_date = date_as_max_dt(
                    start_date + relativedelta(months=1, day=day_anchor, days=-1),
                    timezone,
                )
    elif interval == PLAN_DURATION.QUARTERLY:
        end_date = date_as_max_dt(
            start_date + relativedelta(months=+3, days=-1), timezone
        )
        if day_anchor and not month_anchor:
            end_date = date_as_max_dt(
                start_date + relativedelta(months=3, day=day_anchor, days=-1), timezone
            )
            rd = relativedelta(end_date, start_date)
            if rd.months >= 3 and (
                rd.days > 0
                or rd.hours > 0
                or rd.minutes > 0
                or rd.seconds > 0
                or rd.microseconds > 0
            ):  # went too far
                end_date = date_as_max_dt(
                    start_date + relativedelta(months=2, day=day_anchor, days=-1),
                    timezone,
                )
        elif day_anchor and month_anchor:
            end_date = date_as_max_dt(
                start_date + relativedelta(month=month_anchor, day=day_anchor, days=-1),
                timezone,
            )
            rd = relativedelta(end_date, start_date)
            if rd.months >= 3 and (
                rd.days > 0
                or rd.hours > 0
                or rd.minutes > 0
                or rd.seconds > 0
                or rd.microseconds > 0
            ):  # went too far
                i = 12
                while rd.months >= 3:
                    end_date = date_as_max_dt(
                        start_date + relativedelta(months=i, day=day_anchor, days=-1),
                        timezone,
                    )
                    rd = relativedelta(end_date, start_date)
                    i -= 1
            elif end_date < start_date:
                old_end_date = end_date
                rd = relativedelta(end_date, old_end_date)
                i = 0
                while not (rd.months % 3 == 0 and rd.months > 0):
                    end_date = date_as_max_dt(
                        start_date + relativedelta(months=i, day=day_anchor, days=-1),
                        timezone,
                    )
                    rd = relativedelta(end_date, old_end_date)
                    i += 1
        elif month_anchor and not day_anchor:
            end_date = date_as_max_dt(
                start_date + relativedelta(month=month_anchor, days=-1), timezone
            )
            rd = relativedelta(end_date, start_date)
            if rd.months >= 3 and (
                rd.days > 0
                or rd.hours > 0
                or rd.minutes > 0
                or rd.seconds > 0
                or rd.microseconds > 0
            ):
                while rd.months >= 3:
                    end_date = date_as_max_dt(
                        end_date + relativedelta(months=-3), timezone
                    )
                    rd = relativedelta(end_date, start_date)
            elif end_date < start_date:
                while end_date < start_date:
                    end_date = date_as_max_dt(
                        end_date + relativedelta(months=3), timezone
                    )
    elif interval == PLAN_DURATION.YEARLY:
        end_date = date_as_max_dt(
            start_date + relativedelta(years=+1, days=-1), timezone
        )
        if day_anchor and not month_anchor:
            end_date = date_as_max_dt(
                start_date + relativedelta(years=1, day=day_anchor, days=-1), timezone
            )
            rd = relativedelta(end_date, start_date)
            if rd.years >= 1 and (
                rd.months > 0
                or rd.days > 0
                or rd.hours > 0
                or rd.minutes > 0
                or rd.seconds > 0
                or rd.microseconds > 0
            ):
                end_date = date_as_max_dt(
                    start_date + relativedelta(months=11, day=day_anchor, days=-1),
                    timezone,
                )
        elif day_anchor and month_anchor:
            end_date = date_as_max_dt(
                start_date
                + relativedelta(years=1, month=month_anchor, day=day_anchor, days=-1),
                timezone,
            )
            rd = relativedelta(end_date, start_date)
            if rd.years >= 1 and (
                rd.months > 0
                or rd.days > 0
                or rd.hours > 0
                or rd.minutes > 0
                or rd.seconds > 0
                or rd.microseconds > 0
            ):
                end_date = end_date + relativedelta(years=-1)
        elif month_anchor and not day_anchor:
            end_date = date_as_max_dt(
                start_date + relativedelta(years=1, month=month_anchor, days=-1),
                timezone,
            )
            rd = relativedelta(end_date, start_date)
            if rd.years >= 1 and (
                rd.months > 0
                or rd.days > 0
                or rd.hours > 0
                or rd.minutes > 0
                or rd.seconds > 0
                or rd.microseconds > 0
            ):
                end_date = end_date + relativedelta(years=-1)
    return end_date


def event_uuid():
    return "event_" + str(uuid.uuid4().hex)


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


def subscription_record_uuid():
    return "subsrec_" + str(uuid.uuid4().hex)


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


def customer_balance_adjustment_uuid():
    return "custbaladj_" + str(uuid.uuid4().hex)


def addon_uuid():
    return "addon_" + str(uuid.uuid4().hex)


def addon_version_uuid():
    return "addon_vrs_" + str(uuid.uuid4().hex)


def addon_sr_uuid():
    return "addon_sr_" + str(uuid.uuid4().hex)


def usage_alert_uuid():
    return "usgalert_" + str(uuid.uuid4().hex)


def random_uuid():
    return str(uuid.uuid4().hex)


def date_as_min_dt(date, timezone):
    if isinstance(timezone, pytz.BaseTzInfo):
        tz = timezone
    elif isinstance(timezone, str):
        if timezone not in pytz.all_timezones:
            raise ValueError(f"Invalid timezone: {timezone}")
        tz = pytz.timezone(timezone)
    else:
        raise ValueError(f"Invalid timezone: {timezone}")
    return datetime.datetime.combine(date, datetime.time.min).astimezone(tz)


def date_as_max_dt(date, timezone):
    if isinstance(timezone, pytz.BaseTzInfo):
        tz = timezone
    elif isinstance(timezone, str):
        if timezone not in pytz.all_timezones:
            raise ValueError(f"Invalid timezone: {timezone}")
        tz = pytz.timezone(timezone)
    else:
        raise ValueError(f"Invalid timezone: {timezone}")
    return datetime.datetime.combine(date, datetime.time.max).astimezone(tz)


def namedtuplefetchall(cursor):
    "Return all rows from a cursor as a namedtuple"
    desc = cursor.description
    nt_result = namedtuple("Result", [col[0] for col in desc])
    return [nt_result(*row) for row in cursor.fetchall()]
