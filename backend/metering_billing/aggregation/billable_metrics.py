import abc
import datetime
import logging
from collections import namedtuple
from decimal import Decimal
from typing import Literal, Optional, TypedDict, Union

import sqlparse
from dateutil.relativedelta import relativedelta
from django.apps import apps
from django.db import connection
from jinja2 import Template
from metering_billing.exceptions import MetricValidationFailed
from metering_billing.utils import (
    convert_to_date,
    dates_bwn_two_dts,
    get_granularity_ratio,
    namedtuplefetchall,
    now_utc,
)
from metering_billing.utils.enums import (
    METRIC_AGGREGATION,
    METRIC_GRANULARITY,
    METRIC_TYPE,
    ORGANIZATION_SETTING_NAMES,
    PLAN_DURATION,
)

from .counter_query_templates import COUNTER_TOTAL_PER_DAY
from .gauge_query_templates import GAUGE_DELTA_TOTAL_PER_DAY, GAUGE_TOTAL_TOTAL_PER_DAY
from .rate_query_templates import RATE_TOTAL_PER_DAY

logger = logging.getLogger("django.server")

Metric = apps.get_app_config("metering_billing").get_model(model_name="Metric")
Customer = apps.get_app_config("metering_billing").get_model(model_name="Customer")
Event = apps.get_app_config("metering_billing").get_model(model_name="Event")
SubscriptionRecord = apps.get_app_config("metering_billing").get_model(
    model_name="SubscriptionRecord"
)
Organization = apps.get_app_config("metering_billing").get_model(
    model_name="Organization"
)


class UsageRevenueSummary(TypedDict):
    revenue: Decimal
    usage_qty: Decimal


class MetricHandler(abc.ABC):
    @abc.abstractmethod
    def get_current_usage(
        self,
        subscription: SubscriptionRecord,
    ) -> float:
        """This method will be used to calculate how much usage a customer currently has on a subscription. THough there are cases where get_usage and get_current_usage will be the same, there are cases where they will not. For example, if your billable metric is Gauge with a Max aggregation, then your usage over some period will be the max over past readings, but your current usage will be the latest reading."""
        pass

    @abc.abstractmethod
    def get_earned_usage_per_day(
        self,
        start: datetime.date,
        end: datetime.date,
        customer: Customer,
        proration: Optional[METRIC_GRANULARITY] = None,
    ) -> dict[datetime.datetime, float]:
        """This method will be used when calculating a concept known as "earned revenue" which is very important in accounting. It essentially states that revenue is "earned" not when someone pays, but when you deliver the goods/services at a previously agreed upon price. To accurately calculate accounting metrics, we will need to be able to tell for a given susbcription, where each cent of revenue came from, and the first step for that is to calculate how much billable usage was delivered each day. This method will be used to calculate that.

        Similar to the get current usage method above, this might often look extremely similar to the get usage method, bu there's cases where it can differ quite a bit. For example, if your billable metric is Counter with a Unique aggregation, then your usage per day would naturally make sense to be the number of unique values seen on that day, but you only "earn" from the first time a unique value is seen, so you would attribute the earned usage to that day.
        """
        pass

    @staticmethod
    @abc.abstractmethod
    def validate_data(data) -> dict:
        """We will use this method when validating post requests to create a billable metric. You should validate the data of the billable metric and return the validated data (can be changed if you want)."""
        pass

    @staticmethod
    @abc.abstractmethod
    def create_metric(validated_data: Metric) -> Metric:
        """We will use this method when creating a billable metric. You should create the metric and return it. This is a great time to create all the other queries you we want to keep track of in order to optimize the usage"""
        from metering_billing.models import CategoricalFilter, Metric, NumericFilter

        # edit custom name and pop filters + properties
        num_filter_data = validated_data.pop("numeric_filters", [])
        cat_filter_data = validated_data.pop("categorical_filters", [])
        bm = Metric.objects.create(**validated_data, mat_views_provisioned=True)

        # get filters
        for num_filter in num_filter_data:
            try:
                nf, _ = NumericFilter.objects.get_or_create(
                    **num_filter, organization=bm.organization
                )
            except NumericFilter.MultipleObjectsReturned:
                nf = NumericFilter.objects.filter(
                    **num_filter, organization=bm.organization
                ).first()
            bm.numeric_filters.add(nf)
        for cat_filter in cat_filter_data:
            try:
                cf, _ = CategoricalFilter.objects.get_or_create(
                    **cat_filter, organization=bm.organization
                )
            except CategoricalFilter.MultipleObjectsReturned:
                cf = CategoricalFilter.objects.filter(
                    **cat_filter, organization=bm.organization
                ).first()
            bm.categorical_filters.add(cf)
        assert bm is not None
        bm.refresh_materialized_views()
        return bm

    @staticmethod
    @abc.abstractmethod
    def get_subscription_record_total_billable_usage(
        metric: Metric, subscription_record: SubscriptionRecord
    ) -> Decimal:
        """This method returns the total quantity of usage that a subscription record should be billed for. This is very straightforward and should simply return a number that will then be used to calculate the amount due."""
        pass

    @staticmethod
    @abc.abstractmethod
    def get_subscription_record_current_usage(
        metric: Metric, subscription_record: SubscriptionRecord
    ) -> Decimal:
        """This method returns the current usage of a susbcription record. The result from this method will be used to calculate whether the customer has access to the event represented by the metric. It sounds similar, but there are some key subtleties to note:
        Counter: In this case, subscription record current_usage and total_billable_usage are the same.
        Gauge: These metrics are not billed on a per-event bases, but on the peak usage within some specified granularity period. That means that the billable usage is the normalized peak usage, where the current usage is the value of the underlying state at the time of the request.
        Rate: Even though the billable usage would be the maximum rate over teh subscription_record period, the current usage is simply the current rate.
        """
        pass

    @staticmethod
    @abc.abstractmethod
    def get_subscription_record_daily_billable_usage(
        metric: Metric, subscription_record: SubscriptionRecord
    ) -> dict[datetime.date, Decimal]:
        """This method should return the same quantity as get_subscription_record_total_billable_usage, but split up per day. This allows for calculations of the amount due per day, which is useful for prorating and accounting integrations."""
        pass

    @staticmethod
    @abc.abstractmethod
    def get_daily_total_usage(
        metric: Metric,
        start_date: datetime.date,
        end_date: datetime.date,
        customer: Optional[Customer],
        top_n: Optional[int],
        query_template,
    ) -> dict[Union[Customer, Literal["Other"]], dict[datetime.date, Decimal]]:
        """
        This method just returns the usage of the metric in that day, without worrying about whether it's billable, prorations, etc. Typically used for visualization purposes only and not in any billing runs. Can optionally include a customer to get a single customers usage. Can also incldue top_n, which will group the usage of the non top_n customers into a field called Other.
        """
        from metering_billing.models import Customer, Organization, OrganizationSetting

        organization = Organization.objects.prefetch_related("settings").get(
            id=metric.organization.id
        )
        all_results = {}
        injection_dict = {
            "query_type": metric.usage_aggregation_type,
            "filter_properties": {},
            "customer_id": customer.id if customer else None,
            "top_n": top_n if top_n else "ALL",
            "property_name": metric.property_name,
            "event_name": metric.event_name,
            "organization_id": organization.id,
            "numeric_filters": [
                (x.property_name, x.operator, x.comparison_value)
                for x in metric.numeric_filters.all()
            ],
            "categorical_filters": [
                (x.property_name, x.operator, x.comparison_value)
                for x in metric.categorical_filters.all()
            ],
            "lookback_qty": 1,
            "lookback_units": metric.granularity,
        }
        injection_dict["start_date"] = start_date
        injection_dict["end_date"] = end_date
        injection_dict["cagg_name"] = (
            ("org_" + organization.organization_id.hex)[:22]
            + "___"
            + ("metric_" + metric.metric_id.hex)[:22]
            + "___"
            + (
                "cumsum"
                if metric.metric_type == METRIC_TYPE.GAUGE
                else (
                    "day" if metric.metric_type == METRIC_TYPE.COUNTER else "rate_cagg"
                )
            )
        )
        try:
            sf_setting = organization.settings.get(
                setting_name=ORGANIZATION_SETTING_NAMES.SUBSCRIPTION_FILTER_KEYS
            )
            groupby = sf_setting.setting_values
        except OrganizationSetting.DoesNotExist:
            organization.provision_subscription_filter_settings()
            groupby = []
        injection_dict["group_by"] = groupby
        query = Template(query_template).render(**injection_dict)
        with connection.cursor() as cursor:
            cursor.execute(query)
            results = namedtuplefetchall(cursor)
        all_results = {}
        for result in results:
            if result.customer_id not in all_results:
                all_results[result.customer_id] = {}
            time = convert_to_date(result.time_bucket)
            all_results[result.customer_id][time] = result.usage_qty or Decimal(0)
        customer_ids_minus_other = set(all_results.keys()) - {-1}
        customers = Customer.objects.filter(id__in=customer_ids_minus_other)
        all_results_with_customer_objects = {}
        for customer in customers:
            all_results_with_customer_objects[customer] = all_results[customer.id]
        if -1 in all_results:
            all_results_with_customer_objects["Other"] = all_results[-1]
        return all_results_with_customer_objects


class CounterHandler(MetricHandler):
    @staticmethod
    def _allowed_usage_aggregation_types() -> list[METRIC_AGGREGATION]:
        return [
            METRIC_AGGREGATION.UNIQUE,
            METRIC_AGGREGATION.SUM,
            METRIC_AGGREGATION.COUNT,
            METRIC_AGGREGATION.AVERAGE,
            METRIC_AGGREGATION.MAX,
        ]

    @staticmethod
    def _prepare_injection_dict(
        metric: Metric,
        subscription_record: SubscriptionRecord,
        organization: Organization,
    ) -> dict:
        from metering_billing.models import OrganizationSetting

        injection_dict = {
            "query_type": metric.usage_aggregation_type,
            "filter_properties": {},
            "customer_id": subscription_record.customer.id,
        }
        try:
            sf_setting = organization.settings.get(
                setting_name=ORGANIZATION_SETTING_NAMES.SUBSCRIPTION_FILTER_KEYS
            )
            groupby = sf_setting.setting_values
        except OrganizationSetting.DoesNotExist:
            organization.provision_subscription_filter_settings()
            groupby = []
        injection_dict["group_by"] = groupby
        for filter in subscription_record.filters.all():
            injection_dict["filter_properties"][
                filter.property_name
            ] = filter.comparison_value[0]
        return injection_dict

    @staticmethod
    def _get_total_usage_per_day_not_unique(
        metric: Metric,
        subscription_record: SubscriptionRecord,
        organization: Organization,
    ) -> list[namedtuple]:
        from metering_billing.aggregation.counter_query_templates import (
            COUNTER_CAGG_TOTAL,
        )

        organization = Organization.objects.prefetch_related("settings").get(
            id=metric.organization.id
        )
        # prepare dictionary for injection
        injection_dict = CounterHandler._prepare_injection_dict(
            metric, subscription_record, organization
        )
        start = subscription_record.usage_start_date
        end = subscription_record.end_date
        # there's 3 periods here.... the chunk between the start and the end of that day,
        # the full days in between, and the chunk between the last full day and the end. There
        # are scenarios where all 3 of them happen or don't independently of each other, so
        # we check individually
        # check for start to end of day condition:
        start_to_eod = not (
            start.hour == 0
            and start.minute == 0
            and start.second == 0
            and start.microsecond == 0
        )
        # check for start of day to endcondition:
        sod_to_end = not (
            end.hour == 23
            and end.minute == 59
            and end.second == 59
            and end.microsecond == 999999
        )
        # check for full days in between condition:
        if not start_to_eod:
            full_days_btwn_start = start.date()
        else:
            full_days_btwn_start = (start + relativedelta(days=1)).date()
        if not sod_to_end:
            full_days_btwn_end = end.date()
        else:
            full_days_btwn_end = (end - relativedelta(days=1)).date()
        full_days_between = (full_days_btwn_end - full_days_btwn_start).days > 0
        # now use our pre-prepared queries with the injectiosn to get the usage
        all_results = []
        if start_to_eod:
            injection_dict["start_date"] = start.replace(microsecond=0)
            injection_dict["end_date"] = start.replace(
                hour=23, minute=59, second=59, microsecond=999999
            )
            injection_dict["cagg_name"] = (
                ("org_" + organization.organization_id.hex)[:22]
                + "___"
                + ("metric_" + metric.metric_id.hex)[:22]
                + "___"
                + "second"
            )
            query = Template(COUNTER_CAGG_TOTAL).render(**injection_dict)
            with connection.cursor() as cursor:
                cursor.execute(query)
                results = namedtuplefetchall(cursor)
            all_results.extend(results)
        if full_days_between:
            injection_dict["start_date"] = full_days_btwn_start
            injection_dict["end_date"] = full_days_btwn_end
            injection_dict["cagg_name"] = (
                ("org_" + organization.organization_id.hex)[:22]
                + "___"
                + ("metric_" + metric.metric_id.hex)[:22]
                + "___"
                + "day"
            )
            query = Template(COUNTER_CAGG_TOTAL).render(**injection_dict)
            with connection.cursor() as cursor:
                cursor.execute(query)
                results = namedtuplefetchall(cursor)
            all_results.extend(results)
        if sod_to_end:
            injection_dict["start_date"] = end.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            injection_dict["end_date"] = end.replace(microsecond=0)
            injection_dict["cagg_name"] = (
                ("org_" + organization.organization_id.hex)[:22]
                + "___"
                + ("metric_" + metric.metric_id.hex)[:22]
                + "___"
                + "second"
            )
            query = Template(COUNTER_CAGG_TOTAL).render(**injection_dict)
            with connection.cursor() as cursor:
                cursor.execute(query)
                results = namedtuplefetchall(cursor)
            all_results.extend(results)
        return all_results

    @staticmethod
    def get_subscription_record_total_billable_usage(
        metric: Metric, subscription_record: SubscriptionRecord
    ) -> Decimal:
        from metering_billing.aggregation.counter_query_templates import (
            COUNTER_UNIQUE_TOTAL,
        )
        from metering_billing.models import Organization

        organization = Organization.objects.prefetch_related("settings").get(
            id=metric.organization.id
        )
        if metric.usage_aggregation_type != METRIC_AGGREGATION.UNIQUE:
            all_results = CounterHandler._get_total_usage_per_day_not_unique(
                metric, subscription_record, organization
            )
        else:
            start = subscription_record.usage_start_date
            end = subscription_record.end_date
            injection_dict = CounterHandler._prepare_injection_dict(
                metric, subscription_record, organization
            )
            injection_dict["start_date"] = start
            injection_dict["end_date"] = end
            injection_dict["property_name"] = metric.property_name
            injection_dict["event_name"] = metric.event_name
            injection_dict["organization_id"] = organization.id
            injection_dict["numeric_filters"] = [
                (x.property_name, x.operator, x.comparison_value)
                for x in metric.numeric_filters.all()
            ]
            injection_dict["categorical_filters"] = [
                (x.property_name, x.operator, x.comparison_value)
                for x in metric.categorical_filters.all()
            ]
            query = Template(COUNTER_UNIQUE_TOTAL).render(**injection_dict)
            with connection.cursor() as cursor:
                cursor.execute(query)
                results = namedtuplefetchall(cursor)
            all_results = results
        totals = {"usage_qty": 0, "num_events": 0}
        for result in all_results:
            usage_qty = result.usage_qty or 0
            if metric.usage_aggregation_type == METRIC_AGGREGATION.AVERAGE:
                totals["usage_qty"] += usage_qty * result.num_events
            elif metric.usage_aggregation_type == METRIC_AGGREGATION.MAX:
                if usage_qty > totals["usage_qty"]:
                    totals["usage_qty"] = usage_qty
            else:
                totals["usage_qty"] += usage_qty
            totals["num_events"] += result.num_events
        if metric.usage_aggregation_type == METRIC_AGGREGATION.AVERAGE:
            totals["usage_qty"] = totals["usage_qty"] / totals["num_events"]
        return totals["usage_qty"]

    @staticmethod
    def get_subscription_record_current_usage(
        metric: Metric, subscription_record: SubscriptionRecord
    ) -> Decimal:
        return CounterHandler.get_subscription_record_total_billable_usage(
            metric, subscription_record
        )

    @staticmethod
    def get_daily_total_usage(
        metric: Metric,
        start_date: datetime.date,
        end_date: datetime.date,
        customer: Optional[Customer],
        top_n: Optional[int],
    ) -> dict[Union[Customer, Literal["Other"]], dict[datetime.date, Decimal]]:
        return MetricHandler.get_daily_total_usage(
            metric, start_date, end_date, customer, top_n, COUNTER_TOTAL_PER_DAY
        )

    @staticmethod
    def get_subscription_record_daily_billable_usage(
        metric: Metric, subscription_record: SubscriptionRecord
    ) -> dict[datetime.date, Decimal]:
        from metering_billing.models import Organization

        from .counter_query_templates import COUNTER_UNIQUE_PER_DAY

        organization = Organization.objects.prefetch_related("settings").get(
            id=metric.organization.id
        )
        all_results = {}
        if metric.usage_aggregation_type != METRIC_AGGREGATION.UNIQUE:
            usg_per_day_results = CounterHandler._get_total_usage_per_day_not_unique(
                metric, subscription_record, organization
            )
            for result in usg_per_day_results:
                time = convert_to_date(result.bucket)
                if time not in all_results:
                    all_results[time] = {"usage_qty": 0, "num_events": 0}
                if metric.usage_aggregation_type == METRIC_AGGREGATION.AVERAGE:
                    all_results[time]["usage_qty"] += (
                        result.usage_qty or 0 * result.num_events
                    )
                elif metric.usage_aggregation_type == METRIC_AGGREGATION.MAX:
                    if result.usage_qty > all_results[time]["usage_qty"]:
                        all_results[time]["usage_qty"] = result.usage_qty
                else:
                    all_results[time]["usage_qty"] += result.usage_qty or 0
            cumulative_max = 0
            for time in sorted(list(all_results.keys())):
                if metric.usage_aggregation_type == METRIC_AGGREGATION.AVERAGE:
                    all_results[time]["usage_qty"] = (
                        all_results[time]["usage_qty"] / all_results[time]["num_events"]
                    )
                elif metric.usage_aggregation_type == METRIC_AGGREGATION.MAX:
                    # we do this so we can get the "incremental" max value which determines
                    # where the revenue is being earned
                    if all_results[time]["usage_qty"] > cumulative_max:
                        cur_value = all_results[time]["usage_qty"]
                        all_results[time]["usage_qty"] = cur_value - cumulative_max
                        cumulative_max = cur_value
                    else:
                        all_results[time]["usage_qty"] = 0
                all_results[time] = all_results[time]["usage_qty"]
        else:
            start = subscription_record.usage_start_date
            end = subscription_record.end_date
            injection_dict = CounterHandler._prepare_injection_dict(
                metric, subscription_record, organization
            )
            injection_dict["start_date"] = start
            injection_dict["end_date"] = end
            injection_dict["property_name"] = metric.property_name
            injection_dict["event_name"] = metric.event_name
            injection_dict["organization_id"] = organization.id
            injection_dict["numeric_filters"] = [
                (x.property_name, x.operator, x.comparison_value)
                for x in metric.numeric_filters.all()
            ]
            injection_dict["categorical_filters"] = [
                (x.property_name, x.operator, x.comparison_value)
                for x in metric.categorical_filters.all()
            ]
            query = Template(COUNTER_UNIQUE_PER_DAY).render(**injection_dict)
            with connection.cursor() as cursor:
                cursor.execute(query)
                results = namedtuplefetchall(cursor)
            all_results = results
        return all_results

    @staticmethod
    def validate_data(data: dict) -> dict:
        # has been top-level validated by the MetricSerializer, so we can assume
        # certain fields are there and ignore others as needed
        # unpack stuff first
        event_name = data.get("event_name", None)
        usg_agg_type = data.get("usage_aggregation_type", None)
        bill_agg_type = data.get("billable_aggregation_type", None)
        metric_type = data.get("metric_type", None)
        event_type = data.get("event_type", None)
        granularity = data.get("granularity", None)
        data.get("numeric_filters", None)
        data.get("categorical_filters", None)
        property_name = data.get("property_name", None)
        proration = data.get("proration", None)

        # now validate
        if metric_type != METRIC_TYPE.COUNTER:
            raise MetricValidationFailed(
                "Metric type must be COUNTER for CounterHandler"
            )
        if usg_agg_type not in CounterHandler._allowed_usage_aggregation_types():
            raise MetricValidationFailed(
                "[METRIC TYPE: COUNTER] Usage aggregation type {} is not allowed.".format(
                    usg_agg_type
                )
            )
        if event_name is None:
            raise MetricValidationFailed(
                "[METRIC TYPE: COUNTER] Must specify event name"
            )
        if usg_agg_type != METRIC_AGGREGATION.COUNT:
            if property_name is None:
                raise MetricValidationFailed(
                    "[METRIC TYPE: COUNTER] Must specify property name unless using COUNT aggregation"
                )
        else:
            if property_name is not None:
                logger.info(
                    "[METRIC TYPE: COUNTER] Property name specified but not needed for COUNT aggregation"
                )
                data.pop("property_name", None)
        if granularity:
            logger.info(
                "[METRIC TYPE: COUNTER] Granularity type not allowed. Making null."
            )
            data.pop("granularity", None)
        if event_type:
            logger.info("[METRIC TYPE: COUNTER] Event type not allowed. Making null.")
            data.pop("event_type", None)
        if bill_agg_type:
            logger.info(
                "[METRIC TYPE: COUNTER] Billable aggregation type not allowed. Making null."
            )
            data.pop("billable_aggregation_type", None)
        if proration:
            logger.info("[METRIC TYPE: COUNTER] Proration not allowed. Making null.")
            data.pop("proration", None)
        return data

    @staticmethod
    def create_continuous_aggregate(metric: Metric, refresh=False):
        # unfortunately there's no good way to make caggs for unique. We'll still
        # make one for the total daily usage graph, but not for second
        # if we're refreshing the matview, then we need to drop the last
        # one and recreate it
        from metering_billing.models import Organization, OrganizationSetting

        from .common_query_templates import CAGG_COMPRESSION, CAGG_DROP, CAGG_REFRESH
        from .counter_query_templates import COUNTER_CAGG_QUERY

        organization = Organization.objects.prefetch_related("settings").get(
            id=metric.organization.id
        )
        try:
            groupby = organization.settings.get(
                setting_name=ORGANIZATION_SETTING_NAMES.SUBSCRIPTION_FILTER_KEYS
            )
            groupby = groupby.setting_values
        except OrganizationSetting.DoesNotExist:
            organization.provision_subscription_filter_settings()
            groupby = []
        sql_injection_data = {
            "query_type": metric.usage_aggregation_type,
            "property_name": metric.property_name,
            "group_by": groupby,
            "event_name": metric.event_name,
            "organization_id": organization.id,
            "numeric_filters": [
                (x.property_name, x.operator, x.comparison_value)
                for x in metric.numeric_filters.all()
            ],
            "categorical_filters": [
                (x.property_name, x.operator, x.comparison_value)
                for x in metric.categorical_filters.all()
            ],
        }
        base_name = (
            ("org_" + organization.organization_id.hex)[:22]
            + "___"
            + ("metric_" + metric.metric_id.hex)[:22]
            + "___"
        )
        sql_injection_data["cagg_name"] = base_name + "day"
        sql_injection_data["bucket_size"] = "day"
        day_query = Template(COUNTER_CAGG_QUERY).render(**sql_injection_data)
        day_drop_query = Template(CAGG_DROP).render(**sql_injection_data)
        day_refresh_query = Template(CAGG_REFRESH).render(**sql_injection_data)
        sql_injection_data["cagg_name"] = base_name + "second"
        sql_injection_data["bucket_size"] = "second"
        second_query = Template(COUNTER_CAGG_QUERY).render(**sql_injection_data)
        second_drop_query = Template(CAGG_DROP).render(**sql_injection_data)
        second_refresh_query = Template(CAGG_REFRESH).render(**sql_injection_data)
        second_compression_query = Template(CAGG_COMPRESSION).render(
            **sql_injection_data
        )
        with connection.cursor() as cursor:
            if refresh is True:
                cursor.execute(day_drop_query)
                cursor.execute(second_drop_query)
            cursor.execute(day_query)
            cursor.execute(day_refresh_query)
            if metric.usage_aggregation_type != METRIC_AGGREGATION.UNIQUE:
                cursor.execute(second_query)
                cursor.execute(second_refresh_query)
                cursor.execute(second_compression_query)

    @staticmethod
    def create_metric(validated_data: dict) -> Metric:
        metric = MetricHandler.create_metric(validated_data)
        CounterHandler.create_continuous_aggregate(metric)
        return metric

    @staticmethod
    def archive_metric(metric: Metric) -> Metric:
        from .common_query_templates import CAGG_DROP

        base_name = (
            ("org_" + metric.organization.organization_id.hex)[:22]
            + "___"
            + ("metric_" + metric.metric_id.hex)[:22]
            + "___"
        )
        sql_injection_data = {"cagg_name": base_name + "day"}
        day_drop_query = Template(CAGG_DROP).render(**sql_injection_data)
        sql_injection_data = {"cagg_name": base_name + "second"}
        second_drop_query = Template(CAGG_DROP).render(**sql_injection_data)
        with connection.cursor() as cursor:
            cursor.execute(day_drop_query)
            cursor.execute(second_drop_query)


class CustomHandler(MetricHandler):
    @staticmethod
    def _run_query(custom_sql, injection_dict: dict):
        from metering_billing.aggregation.custom_query_templates import (
            CUSTOM_BASE_QUERY,
        )

        combined_query = CUSTOM_BASE_QUERY
        if custom_sql.lower().lstrip().startswith("with"):
            custom_sql = custom_sql.lower().replace("with", ",")
        combined_query += custom_sql
        query = Template(combined_query).render(**injection_dict)
        with connection.cursor() as cursor:
            cursor.execute(query)
            results = namedtuplefetchall(cursor)
        return results

    @staticmethod
    def get_subscription_record_total_billable_usage(
        metric: Metric, subscription_record: SubscriptionRecord
    ) -> Decimal:
        from metering_billing.models import Organization

        organization = Organization.objects.prefetch_related("settings").get(
            id=metric.organization.id
        )
        injection_dict = {
            "filter_properties": {},
            "customer_id": subscription_record.customer.id,
        }
        start = subscription_record.usage_start_date
        end = subscription_record.end_date
        injection_dict["start_date"] = start
        injection_dict["end_date"] = end
        injection_dict["organization_id"] = organization.id
        for filter in subscription_record.filters.all():
            injection_dict["filter_properties"][
                filter.property_name
            ] = filter.comparison_value[0]
        results = CustomHandler._run_query(metric.custom_sql, injection_dict)
        if len(results) == 0:
            return Decimal(0)
        return results[0].usage_qty

    @staticmethod
    def get_subscription_record_current_usage(
        metric: Metric, subscription_record: SubscriptionRecord
    ) -> Decimal:
        return CustomHandler.get_subscription_record_total_billable_usage(
            metric, subscription_record
        )

    @staticmethod
    def get_subscription_record_daily_billable_usage(
        metric: Metric, subscription_record: SubscriptionRecord
    ) -> dict[datetime.date, Decimal]:
        usage_qty = CustomHandler.get_subscription_record_total_billable_usage(
            metric, subscription_record
        )
        now = now_utc().date()
        dates_bwn = [
            x
            for x in dates_bwn_two_dts(
                subscription_record.usage_start_date, subscription_record.end_date
            )
            if x <= now
        ]
        dates_dict = {x: usage_qty / len(dates_bwn) for x in dates_bwn}

        return dates_dict

    @staticmethod
    def create_continuous_aggregate(metric: Metric, refresh=False):
        pass

    @staticmethod
    def create_metric(validated_data: dict) -> Metric:
        metric = MetricHandler.create_metric(validated_data)
        CustomHandler.create_continuous_aggregate(metric)
        return metric

    @staticmethod
    def archive_metric(metric: Metric) -> Metric:
        pass

    @staticmethod
    def validate_data(data: dict) -> dict:
        # has been top-level validated by the MetricSerializer, so we can assume
        # certain fields are there and ignore others as needed
        # unpack stuff first
        event_name = data.get("event_name", None)
        usg_agg_type = data.get("usage_aggregation_type", None)
        bill_agg_type = data.get("billable_aggregation_type", None)
        metric_type = data.get("metric_type", None)
        event_type = data.get("event_type", None)
        granularity = data.get("granularity", None)
        numeric_filters = data.get("numeric_filters", None)
        categorical_filters = data.get("categorical_filters", None)
        property_name = data.get("property_name", None)
        custom_sql = data.get("custom_sql", None)

        # now validate
        if event_name is not None:
            logger.info(
                "[METRIC TYPE: CUSTOM] Event name specified but not needed for CUSTOM aggregation"
            )
            data.pop("event_name", None)
        if usg_agg_type is not None:
            logger.info(
                "[METRIC TYPE: CUSTOM] Usage aggregation type specified but not needed for CUSTOM aggregation"
            )
            data.pop("usage_aggregation_type", None)
        if bill_agg_type is not None:
            logger.info(
                "[METRIC TYPE: CUSTOM] Billable aggregation type specified but not needed for CUSTOM aggregation"
            )
            data.pop("billable_aggregation_type", None)
        if metric_type != METRIC_TYPE.CUSTOM:
            raise MetricValidationFailed("Metric type must be CUSTOM for CustomHandler")
        if event_type is not None:
            logger.info(
                "[METRIC TYPE: CUSTOM] Event type specified but not needed for CUSTOM aggregation"
            )
            data.pop("event_type", None)
        if granularity is not None:
            logger.info(
                "[METRIC TYPE: CUSTOM] Granularity specified but not needed for CUSTOM aggregation"
            )
            data.pop("granularity", None)
        if numeric_filters is not None:
            logger.info(
                "[METRIC TYPE: CUSTOM] Numeric filters specified but not needed for CUSTOM aggregation"
            )
            data.pop("numeric_filters", None)
        if categorical_filters is not None:
            logger.info(
                "[METRIC TYPE: CUSTOM] Categorical filters specified but not needed for CUSTOM aggregation"
            )
            data.pop("categorical_filters", None)
        if property_name is not None:
            logger.info(
                "[METRIC TYPE: CUSTOM] Property name specified but not needed for CUSTOM aggregation"
            )
            data.pop("property_name", None)
        if custom_sql is None:
            raise MetricValidationFailed(
                "Custom SQL query is required for CUSTOM metric"
            )
        sql_valid = CustomHandler.validate_custom_sql(custom_sql)
        if not sql_valid:
            raise MetricValidationFailed(
                "Custom SQL query must be a SELECT statement and cannot contain any prohibited keywords"
            )
        try:
            injection_dict = {
                "filter_properties": {},
                "customer_id": 1,
            }
            start = now_utc()
            end = now_utc()
            injection_dict["start_date"] = start
            injection_dict["end_date"] = end
            injection_dict["organization_id"] = 1
            _ = CustomHandler._run_query(custom_sql, injection_dict)
            assert (
                "usage_qty" in custom_sql
            ), "Custom SQL query must return a column named 'usage_qty'"
        except Exception as e:
            raise MetricValidationFailed(
                "Custom SQL query could not be executed successfully: {}".format(e)
            )
        return data

    @staticmethod
    def validate_custom_sql(
        custom_sql: str,
        prohibited_keywords=[
            "alter",
            "create",
            "drop",
            "delete",
            "insert",
            "replace",
            "truncate",
            "update",
        ],
    ) -> bool:
        parsed_sql = sqlparse.parse(custom_sql)

        if parsed_sql[0].get_type() != "SELECT":
            return False

        for token in parsed_sql[0].flatten():
            if (
                token.ttype is sqlparse.tokens.Keyword
                and token.value.lower() in prohibited_keywords
            ):
                return False
            if "metering_billing_" in token.value.lower():
                return False
        return True


class GaugeHandler(MetricHandler):
    """
    The key difference between a gauge handler and an aggregation handler is that the gauge handler has state across time periods. Even when given a blocked off time period, it'll look for previous values of the event/property in question and use those as a starting point. A common example of a metric that woudl fit under the Gauge pattern would be the number of seats a product has available. When we go into a new billing period, the number of seats doesn't magically disappear... we have to keep track of it. We currently support two types of events: quantity_logging and delta_logging. Quantity logging would look like sending events to the API that say we have x users at the moment. Delta logging would be like sending events that say we added x users or removed x users. The gauge handler will look at the previous value of the metric and add/subtract the delta to get the new value.
    """

    @staticmethod
    def validate_data(data: dict) -> dict:
        # has been top-level validated by the MetricSerializer, so we can assume
        # certain fields are there and ignore others as needed

        # unpack stuff first
        event_name = data.get("event_name", None)
        usg_agg_type = data.get("usage_aggregation_type", None)
        bill_agg_type = data.get("billable_aggregation_type", None)
        metric_type = data.get("metric_type", None)
        event_type = data.get("event_type", None)
        granularity = data.get("granularity", None)
        data.get("numeric_filters", None)
        data.get("categorical_filters", None)
        property_name = data.get("property_name", None)
        proration = data.get("proration", None)

        # now validate
        if not event_name:
            raise MetricValidationFailed("[METRIC TYPE: GAUGE] Must specify event name")
        if metric_type != METRIC_TYPE.GAUGE:
            raise MetricValidationFailed("Metric type must be GAUGE for GaugeHandler")
        if usg_agg_type not in GaugeHandler._allowed_usage_aggregation_types():
            raise MetricValidationFailed(
                "[METRIC TYPE: GAUGE] Usage aggregation type {} is not allowed.".format(
                    usg_agg_type
                )
            )
        if not granularity:
            raise MetricValidationFailed(
                "[METRIC TYPE: GAUGE] Must specify granularity"
            )
        if bill_agg_type:
            logger.info(
                "[METRIC TYPE: GAUGE] Billable aggregation type not allowed. Making null."
            )
            data.pop("billable_aggregation_type", None)
        if not event_type:
            raise MetricValidationFailed(
                "[METRIC TYPE: GAUGE] Must specify event type."
            )
        if not property_name:
            raise MetricValidationFailed(
                "[METRIC TYPE: GAUGE] Must specify property name."
            )
        pr_gran = proration
        metric_granularity = granularity
        if pr_gran == METRIC_GRANULARITY.SECOND:
            if metric_granularity == METRIC_GRANULARITY.SECOND:
                data["proration"] = METRIC_GRANULARITY.TOTAL
        elif pr_gran == METRIC_GRANULARITY.MINUTE:
            assert metric_granularity not in [
                METRIC_GRANULARITY.SECOND,
            ], "Metric granularity cannot be finer than proration granularity"
            if metric_granularity == METRIC_GRANULARITY.MINUTE:
                data["proration"] = METRIC_GRANULARITY.TOTAL
        elif pr_gran == METRIC_GRANULARITY.HOUR:
            assert metric_granularity not in [
                METRIC_GRANULARITY.SECOND,
                METRIC_GRANULARITY.MINUTE,
            ], "Metric granularity cannot be finer than proration granularity"
            if metric_granularity == METRIC_GRANULARITY.HOUR:
                data["proration"] = METRIC_GRANULARITY.TOTAL
        elif pr_gran == METRIC_GRANULARITY.DAY:
            assert metric_granularity not in [
                METRIC_GRANULARITY.SECOND,
                METRIC_GRANULARITY.MINUTE,
                METRIC_GRANULARITY.HOUR,
            ], "Metric granularity cannot be finer than proration granularity"
            if metric_granularity == METRIC_GRANULARITY.DAY:
                data["proration"] = METRIC_GRANULARITY.TOTAL
        elif pr_gran == METRIC_GRANULARITY.MONTH:
            assert metric_granularity not in [
                METRIC_GRANULARITY.SECOND,
                METRIC_GRANULARITY.MINUTE,
                METRIC_GRANULARITY.HOUR,
                METRIC_GRANULARITY.DAY,
            ], "Metric granularity cannot be finer than proration granularity"
            if metric_granularity == METRIC_GRANULARITY.MONTH:
                data["proration"] = METRIC_GRANULARITY.TOTAL
        elif pr_gran == METRIC_GRANULARITY.QUARTER:
            assert metric_granularity not in [
                METRIC_GRANULARITY.SECOND,
                METRIC_GRANULARITY.MINUTE,
                METRIC_GRANULARITY.HOUR,
                METRIC_GRANULARITY.DAY,
                METRIC_GRANULARITY.MONTH,
            ], "Metric granularity cannot be finer than proration granularity"
            if metric_granularity == METRIC_GRANULARITY.QUARTER:
                data["proration"] = METRIC_GRANULARITY.TOTAL
        elif pr_gran == METRIC_GRANULARITY.YEAR:
            assert metric_granularity not in [
                METRIC_GRANULARITY.SECOND,
                METRIC_GRANULARITY.MINUTE,
                METRIC_GRANULARITY.HOUR,
                METRIC_GRANULARITY.DAY,
                METRIC_GRANULARITY.MONTH,
                METRIC_GRANULARITY.QUARTER,
            ], "Metric granularity cannot be finer than proration granularity"
            if metric_granularity == METRIC_GRANULARITY.YEAR:
                data["proration"] = METRIC_GRANULARITY.TOTAL
        return data

    @staticmethod
    def _allowed_usage_aggregation_types():
        return [
            METRIC_AGGREGATION.MAX,
        ]

    @staticmethod
    def create_metric(validated_data: dict) -> Metric:
        metric = MetricHandler.create_metric(validated_data)
        GaugeHandler.create_continuous_aggregate(metric)
        return metric

    @staticmethod
    def create_continuous_aggregate(metric: Metric, refresh=False):
        from metering_billing.models import Organization, OrganizationSetting

        from .common_query_templates import CAGG_COMPRESSION, CAGG_DROP, CAGG_REFRESH
        from .gauge_query_templates import (
            GAUGE_DELTA_CUMULATIVE_SUM,
            GAUGE_DELTA_DROP_OLD,
            GAUGE_TOTAL_CUMULATIVE_SUM,
        )

        organization = Organization.objects.prefetch_related("settings").get(
            id=metric.organization.id
        )
        try:
            groupby = organization.settings.get(
                setting_name=ORGANIZATION_SETTING_NAMES.SUBSCRIPTION_FILTER_KEYS
            )
            groupby = groupby.setting_values
        except OrganizationSetting.DoesNotExist:
            organization.provision_subscription_filter_settings()
            groupby = []
        sql_injection_data = {
            "property_name": metric.property_name,
            "group_by": groupby,
            "event_name": metric.event_name,
            "organization_id": organization.id,
            "numeric_filters": [
                (x.property_name, x.operator, x.comparison_value)
                for x in metric.numeric_filters.all()
            ],
            "categorical_filters": [
                (x.property_name, x.operator, x.comparison_value)
                for x in metric.categorical_filters.all()
            ],
        }
        sql_injection_data["cagg_name"] = (
            ("org_" + organization.organization_id.hex)[:22]
            + "___"
            + ("metric_" + metric.metric_id.hex)[:22]
            + "___"
            + "cumsum"
        )
        if metric.event_type == "delta":
            query = Template(GAUGE_DELTA_CUMULATIVE_SUM).render(**sql_injection_data)
            drop_old = Template(GAUGE_DELTA_DROP_OLD).render(**sql_injection_data)
        elif metric.event_type == "total":
            query = Template(GAUGE_TOTAL_CUMULATIVE_SUM).render(**sql_injection_data)
        refresh_query = Template(CAGG_REFRESH).render(**sql_injection_data)
        compression_query = Template(CAGG_COMPRESSION).render(**sql_injection_data)
        with connection.cursor() as cursor:
            if metric.event_type == "delta":
                cursor.execute(drop_old)
            if refresh:
                cursor.execute(Template(CAGG_DROP).render(**sql_injection_data))
            cursor.execute(query)
            cursor.execute(refresh_query)
            cursor.execute(compression_query)

    @staticmethod
    def archive_metric(metric: Metric) -> Metric:
        from .common_query_templates import CAGG_DROP
        from .gauge_query_templates import GAUGE_DELTA_DROP_OLD

        organization = metric.organization
        sql_injection_data = {
            "cagg_name": (
                ("org_" + organization.organization_id.hex)[:22]
                + "___"
                + ("metric_" + metric.metric_id.hex)[:22]
                + "___"
                + "cumsum"
            ),
        }
        query = Template(CAGG_DROP).render(**sql_injection_data)
        if metric.event_type == "delta":
            trigger = Template(GAUGE_DELTA_DROP_OLD).render(**sql_injection_data)
        with connection.cursor() as cursor:
            cursor.execute(query)
            if metric.event_type == "delta":
                cursor.execute(trigger)
        return metric

    @staticmethod
    def get_subscription_record_total_billable_usage(
        metric: Metric, subscription_record: SubscriptionRecord
    ) -> Decimal:
        from metering_billing.models import Organization, OrganizationSetting

        from .gauge_query_templates import (
            GAUGE_DELTA_GET_TOTAL_USAGE_WITH_PRORATION,
            GAUGE_TOTAL_GET_TOTAL_USAGE_WITH_PRORATION,
        )

        organization = Organization.objects.prefetch_related("settings").get(
            id=metric.organization.id
        )
        try:
            groupby = organization.settings.get(
                setting_name=ORGANIZATION_SETTING_NAMES.SUBSCRIPTION_FILTER_KEYS
            )
            groupby = groupby.setting_values
        except OrganizationSetting.DoesNotExist:
            organization.provision_subscription_filter_settings()
            groupby = []
        metric_granularity = metric.granularity
        if metric_granularity == METRIC_GRANULARITY.TOTAL:
            plan_duration = subscription_record.billing_plan.plan.plan_duration
            metric_granularity = (
                METRIC_GRANULARITY.YEAR
                if plan_duration == PLAN_DURATION.YEARLY
                else (
                    METRIC_GRANULARITY.QUARTER
                    if plan_duration == PLAN_DURATION.QUARTERLY
                    else METRIC_GRANULARITY.MONTH
                )
            )
        granularity_ratio = get_granularity_ratio(
            metric_granularity, metric.proration, subscription_record.usage_start_date
        )
        proration_units = metric.proration
        if proration_units == METRIC_GRANULARITY.TOTAL:
            proration_units = None
        injection_dict = {
            "proration_units": proration_units,
            "cumsum_cagg": (
                ("org_" + organization.organization_id.hex)[:22]
                + "___"
                + ("metric_" + metric.metric_id.hex)[:22]
                + "___"
                + "cumsum"
            ),
            "group_by": groupby,
            "filter_properties": {},
            "customer_id": subscription_record.customer.id,
            "start_date": subscription_record.usage_start_date,
            "end_date": subscription_record.end_date,
            "granularity_ratio": granularity_ratio,
            "event_name": metric.event_name,
            "organization_id": organization.id,
            "numeric_filters": [
                (x.property_name, x.operator, x.comparison_value)
                for x in metric.numeric_filters.all()
            ],
            "categorical_filters": [
                (x.property_name, x.operator, x.comparison_value)
                for x in metric.categorical_filters.all()
            ],
            "property_name": metric.property_name,
        }
        for filter in subscription_record.filters.all():
            injection_dict["filter_properties"][
                filter.property_name
            ] = filter.comparison_value[0]
        if metric.event_type == "delta":
            query = Template(GAUGE_DELTA_GET_TOTAL_USAGE_WITH_PRORATION).render(
                **injection_dict
            )
        elif metric.event_type == "total":
            query = Template(GAUGE_TOTAL_GET_TOTAL_USAGE_WITH_PRORATION).render(
                **injection_dict
            )
        with connection.cursor() as cursor:
            cursor.execute(query)
            result = namedtuplefetchall(cursor)
        if len(result) == 0:
            return Decimal(0)
        return result[0].usage_qty

    @staticmethod
    def get_subscription_record_current_usage(
        metric: Metric, subscription_record: SubscriptionRecord
    ) -> Decimal:
        from metering_billing.models import Organization, OrganizationSetting

        from .gauge_query_templates import (
            GAUGE_DELTA_GET_CURRENT_USAGE,
            GAUGE_TOTAL_GET_CURRENT_USAGE,
        )

        organization = Organization.objects.prefetch_related("settings").get(
            id=metric.organization.id
        )
        try:
            groupby = organization.settings.get(
                setting_name=ORGANIZATION_SETTING_NAMES.SUBSCRIPTION_FILTER_KEYS
            )
            groupby = groupby.setting_values
        except OrganizationSetting.DoesNotExist:
            organization.provision_subscription_filter_settings()
            groupby = []
        metric_granularity = metric.granularity
        if metric_granularity == METRIC_GRANULARITY.TOTAL:
            plan_duration = subscription_record.billing_plan.plan.plan_duration
            metric_granularity = (
                METRIC_GRANULARITY.YEAR
                if plan_duration == PLAN_DURATION.YEARLY
                else (
                    METRIC_GRANULARITY.QUARTER
                    if plan_duration == PLAN_DURATION.QUARTERLY
                    else METRIC_GRANULARITY.MONTH
                )
            )
        granularity_ratio = get_granularity_ratio(
            metric_granularity, metric.proration, subscription_record.usage_start_date
        )
        proration_units = metric.proration
        if proration_units == METRIC_GRANULARITY.TOTAL:
            proration_units = None
        injection_dict = {
            "proration_units": proration_units,
            "cumsum_cagg": (
                ("org_" + organization.organization_id.hex)[:22]
                + "___"
                + ("metric_" + metric.metric_id.hex)[:22]
                + "___"
                + "cumsum"
            ),
            "group_by": groupby,
            "filter_properties": {},
            "customer_id": subscription_record.customer.id,
            "start_date": subscription_record.usage_start_date,
            "end_date": subscription_record.end_date,
            "granularity_ratio": granularity_ratio,
            "event_name": metric.event_name,
            "organization_id": organization.id,
            "numeric_filters": [
                (x.property_name, x.operator, x.comparison_value)
                for x in metric.numeric_filters.all()
            ],
            "categorical_filters": [
                (x.property_name, x.operator, x.comparison_value)
                for x in metric.categorical_filters.all()
            ],
            "property_name": metric.property_name,
        }
        for filter in subscription_record.filters.all():
            injection_dict["filter_properties"][
                filter.property_name
            ] = filter.comparison_value[0]
        if metric.event_type == "delta":
            query = Template(GAUGE_DELTA_GET_CURRENT_USAGE).render(**injection_dict)
        elif metric.event_type == "total":
            query = Template(GAUGE_TOTAL_GET_CURRENT_USAGE).render(**injection_dict)
        with connection.cursor() as cursor:
            cursor.execute(query)
            result = namedtuplefetchall(cursor)
        if len(result) == 0:
            return Decimal(0)
        return result[0].usage_qty

    @staticmethod
    def get_subscription_record_daily_billable_usage(
        metric: Metric, subscription_record: SubscriptionRecord
    ) -> dict[datetime.date, Decimal]:
        from metering_billing.models import Organization, OrganizationSetting

        from .gauge_query_templates import (
            GAUGE_DELTA_GET_TOTAL_USAGE_WITH_PRORATION_PER_DAY,
            GAUGE_TOTAL_GET_TOTAL_USAGE_WITH_PRORATION_PER_DAY,
        )

        organization = Organization.objects.prefetch_related("settings").get(
            id=metric.organization.id
        )
        try:
            groupby = organization.settings.get(
                setting_name=ORGANIZATION_SETTING_NAMES.SUBSCRIPTION_FILTER_KEYS
            )
            groupby = groupby.setting_values
        except OrganizationSetting.DoesNotExist:
            organization.provision_subscription_filter_settings()
            groupby = []
        metric_granularity = metric.granularity
        if metric_granularity == METRIC_GRANULARITY.TOTAL:
            plan_duration = subscription_record.billing_plan.plan.plan_duration
            metric_granularity = (
                METRIC_GRANULARITY.YEAR
                if plan_duration == PLAN_DURATION.YEARLY
                else (
                    METRIC_GRANULARITY.QUARTER
                    if plan_duration == PLAN_DURATION.QUARTERLY
                    else METRIC_GRANULARITY.MONTH
                )
            )
        granularity_ratio = get_granularity_ratio(
            metric_granularity, metric.proration, subscription_record.usage_start_date
        )
        proration_units = metric.proration
        if proration_units == METRIC_GRANULARITY.TOTAL:
            proration_units = None
        injection_dict = {
            "proration_units": proration_units,
            "cumsum_cagg": (
                ("org_" + organization.organization_id.hex)[:22]
                + "___"
                + ("metric_" + metric.metric_id.hex)[:22]
                + "___"
                + "cumsum"
            ),
            "group_by": groupby,
            "filter_properties": {},
            "customer_id": subscription_record.customer.id,
            "start_date": subscription_record.usage_start_date,
            "end_date": subscription_record.end_date,
            "granularity_ratio": granularity_ratio,
            "event_name": metric.event_name,
            "organization_id": organization.id,
            "numeric_filters": [
                (x.property_name, x.operator, x.comparison_value)
                for x in metric.numeric_filters.all()
            ],
            "categorical_filters": [
                (x.property_name, x.operator, x.comparison_value)
                for x in metric.categorical_filters.all()
            ],
            "property_name": metric.property_name,
        }
        for filter in subscription_record.filters.all():
            injection_dict["filter_properties"][
                filter.property_name
            ] = filter.comparison_value[0]
        if metric.event_type == "delta":
            query = Template(GAUGE_DELTA_GET_TOTAL_USAGE_WITH_PRORATION_PER_DAY).render(
                **injection_dict
            )
        elif metric.event_type == "total":
            query = Template(GAUGE_TOTAL_GET_TOTAL_USAGE_WITH_PRORATION_PER_DAY).render(
                **injection_dict
            )
        with connection.cursor() as cursor:
            cursor.execute(query)
            result = namedtuplefetchall(cursor)
        results_dict = {}
        for row in result:
            date = convert_to_date(row.time)
            if date not in results_dict:
                results_dict[date] = Decimal(0)
            results_dict[date] += row.usage_qty or Decimal(0)
        return results_dict

    @staticmethod
    def get_daily_total_usage(
        metric: Metric,
        start_date: datetime.date,
        end_date: datetime.date,
        customer: Optional[Customer],
        top_n: Optional[int],
    ) -> dict[Union[Customer, Literal["Other"]], dict[datetime.date, Decimal]]:
        if metric.event_type == "delta":
            return MetricHandler.get_daily_total_usage(
                metric, start_date, end_date, customer, top_n, GAUGE_DELTA_TOTAL_PER_DAY
            )
        elif metric.event_type == "total":
            return MetricHandler.get_daily_total_usage(
                metric, start_date, end_date, customer, top_n, GAUGE_TOTAL_TOTAL_PER_DAY
            )


class RateHandler(MetricHandler):
    """
    A rate handler can be thought of as the exact opposite of a Gauge Handler. A GaugeHandler keeps an underlying state that persists across billing periods. A RateHandler resets it's state in intervals shorter than the billing period. For example, a RateHandler could be used to charge for the number of API calls made in a day, or to limit the number of database insertions per hour. If a GaugeHandler is the "integral" of a CounterHandler, then a RateHandler is the "derivative" of a CounterHandler.
    """

    @staticmethod
    def validate_data(data: dict) -> dict:
        # has been top-level validated by the MetricSerializer, so we can assume
        # certain fields are there and ignore others as needed

        # unpack stuff first
        event_name = data.get("event_name", None)
        usg_agg_type = data.get("usage_aggregation_type", None)
        bill_agg_type = data.get("billable_aggregation_type", None)
        metric_type = data.get("metric_type", None)
        event_type = data.get("event_type", None)
        granularity = data.get("granularity", None)
        data.get("numeric_filters", None)
        data.get("categorical_filters", None)
        property_name = data.get("property_name", None)
        proration = data.get("proration", None)

        # now validate
        if event_name is None:
            raise MetricValidationFailed("[METRIC TYPE: RATE] Must specify event name.")
        if metric_type != METRIC_TYPE.RATE:
            raise MetricValidationFailed("Metric type must be RATE for a RateHandler.")
        if usg_agg_type not in RateHandler._allowed_usage_aggregation_types():
            raise MetricValidationFailed(
                "[METRIC TYPE: RATE] Usage aggregation type {} is not allowed.".format(
                    usg_agg_type
                )
            )
        if bill_agg_type not in RateHandler._allowed_billable_aggregation_types():
            raise MetricValidationFailed(
                "[METRIC TYPE: RATE] Billable aggregation type {} is not allowed.".format(
                    bill_agg_type
                )
            )
        if usg_agg_type != METRIC_AGGREGATION.COUNT:
            if property_name is None:
                raise MetricValidationFailed(
                    "[METRIC TYPE: RATE] Must specify property name unless using COUNT aggregation"
                )
        else:
            if property_name is not None:
                logger.info(
                    "[METRIC TYPE: RATE] Property name specified but not needed for COUNT aggregation"
                )
                data.pop("property_name", None)
        if not granularity:
            raise MetricValidationFailed("[METRIC TYPE: RATE] Must specify granularity")
        if event_type:
            logger.info("[METRIC TYPE: RATE] Event type not allowed. Making null.")
            data.pop("event_type", None)
        if proration:
            logger.info("[METRIC TYPE: RATE] Proration not allowed. Making null.")
            data.pop("proration", None)
        return data

    @staticmethod
    def _allowed_usage_aggregation_types():
        return [
            METRIC_AGGREGATION.SUM,
            METRIC_AGGREGATION.COUNT,
            METRIC_AGGREGATION.AVERAGE,
            METRIC_AGGREGATION.MAX,
        ]

    @staticmethod
    def _allowed_billable_aggregation_types():
        return [
            METRIC_AGGREGATION.MAX,
        ]

    @staticmethod
    def get_daily_total_usage(
        metric: Metric,
        start_date: datetime.date,
        end_date: datetime.date,
        customer: Optional[Customer],
        top_n: Optional[int],
    ) -> dict[Union[Customer, Literal["Other"]], dict[datetime.date, Decimal]]:
        return MetricHandler.get_daily_total_usage(
            metric, start_date, end_date, customer, top_n, RATE_TOTAL_PER_DAY
        )

    @staticmethod
    def create_continuous_aggregate(metric: Metric, refresh=False):
        from metering_billing.models import OrganizationSetting

        from .common_query_templates import CAGG_COMPRESSION, CAGG_DROP, CAGG_REFRESH
        from .rate_query_templates import RATE_CAGG_QUERY

        organization = Organization.objects.prefetch_related("settings").get(
            id=metric.organization.id
        )
        try:
            groupby = organization.settings.get(
                setting_name=ORGANIZATION_SETTING_NAMES.SUBSCRIPTION_FILTER_KEYS
            )
            groupby = groupby.setting_values
        except OrganizationSetting.DoesNotExist:
            organization.provision_subscription_filter_settings()
            groupby = []
        sql_injection_data = {
            "query_type": metric.usage_aggregation_type,
            "property_name": metric.property_name,
            "group_by": groupby,
            "event_name": metric.event_name,
            "organization_id": metric.organization.id,
            "numeric_filters": [
                (x.property_name, x.operator, x.comparison_value)
                for x in metric.numeric_filters.all()
            ],
            "categorical_filters": [
                (x.property_name, x.operator, x.comparison_value)
                for x in metric.categorical_filters.all()
            ],
            "lookback_qty": 1,
            "lookback_units": metric.granularity,
        }
        sql_injection_data["cagg_name"] = (
            ("org_" + organization.organization_id.hex)[:22]
            + "___"
            + ("metric_" + metric.metric_id.hex)[:22]
            + "___"
            + "rate_cagg"
        )
        query = Template(RATE_CAGG_QUERY).render(**sql_injection_data)
        refresh_query = Template(CAGG_REFRESH).render(**sql_injection_data)
        compression_query = Template(CAGG_COMPRESSION).render(**sql_injection_data)
        with connection.cursor() as cursor:
            if refresh:
                cursor.execute(Template(CAGG_DROP).render(**sql_injection_data))
            cursor.execute(query)
            cursor.execute(refresh_query)
            cursor.execute(compression_query)

    @staticmethod
    def archive_metric(metric: Metric) -> Metric:
        from metering_billing.models import Organization

        from .common_query_templates import CAGG_DROP

        organization = Organization.objects.prefetch_related("settings").get(
            id=metric.organization.id
        )
        sql_injection_data = {
            "cagg_name": (
                ("org_" + organization.organization_id.hex)[:22]
                + "___"
                + ("metric_" + metric.metric_id.hex)[:22]
                + "___"
                + "rate_cagg"
            ),
        }
        query = Template(CAGG_DROP).render(**sql_injection_data)
        with connection.cursor() as cursor:
            cursor.execute(query)
        return metric

    @staticmethod
    def _rate_cagg_total_results(
        metric: Metric, subscription_record: SubscriptionRecord
    ):
        from metering_billing.aggregation.rate_query_templates import RATE_CAGG_TOTAL
        from metering_billing.models import Organization, OrganizationSetting

        organization = Organization.objects.prefetch_related("settings").get(
            id=metric.organization.id
        )
        start = subscription_record.usage_start_date
        end = subscription_record.end_date
        injection_dict = {
            "query_type": metric.usage_aggregation_type,
            "organization_id": organization.id,
            "filter_properties": {},
            "customer_id": subscription_record.customer.id,
            "start_date": start.replace(microsecond=0),
            "end_date": end.replace(microsecond=0),
            "cagg_name": ("org_" + organization.organization_id.hex)[:22]
            + "___"
            + ("metric_" + metric.metric_id.hex)[:22]
            + "___"
            + "rate_cagg",
            "lookback_qty": 1,
            "lookback_units": metric.granularity,
            "property_name": metric.property_name,
            "event_name": metric.event_name,
        }
        try:
            sf_setting = organization.settings.get(
                setting_name=ORGANIZATION_SETTING_NAMES.SUBSCRIPTION_FILTER_KEYS
            )
            groupby = sf_setting.setting_values
        except OrganizationSetting.DoesNotExist:
            organization.provision_subscription_filter_settings()
            groupby = []
        injection_dict["group_by"] = groupby
        for filter in subscription_record.filters.all():
            injection_dict["filter_properties"][
                filter.property_name
            ] = filter.comparison_value[0]
        query = Template(RATE_CAGG_TOTAL).render(**injection_dict)
        with connection.cursor() as cursor:
            cursor.execute(query)
            results = namedtuplefetchall(cursor)
        return results

    @staticmethod
    def get_subscription_record_total_billable_usage(
        metric: Metric, subscription_record: SubscriptionRecord
    ) -> Decimal:
        results = RateHandler._rate_cagg_total_results(metric, subscription_record)
        if len(results) == 0:
            return Decimal(0)
        total = results[0].usage_qty
        return total

    @staticmethod
    def get_subscription_record_current_usage(
        metric: Metric, subscription_record: SubscriptionRecord
    ) -> Decimal:
        from metering_billing.aggregation.rate_query_templates import (
            RATE_GET_CURRENT_USAGE,
        )
        from metering_billing.models import Organization, OrganizationSetting

        organization = Organization.objects.prefetch_related("settings").get(
            id=metric.organization.id
        )
        start = subscription_record.usage_start_date
        end = subscription_record.end_date
        injection_dict = {
            "query_type": metric.usage_aggregation_type,
            "filter_properties": {},
            "customer_id": subscription_record.customer.id,
            "start_date": start.replace(microsecond=0),
            "end_date": end.replace(microsecond=0),
            "cagg_name": ("org_" + organization.organization_id.hex)[:22]
            + "___"
            + ("metric_" + metric.metric_id.hex)[:22]
            + "___"
            + "second",
            "property_name": metric.property_name,
            "event_name": metric.event_name,
            "organization_id": organization.id,
            "numeric_filters": [
                (x.property_name, x.operator, x.comparison_value)
                for x in metric.numeric_filters.all()
            ],
            "categorical_filters": [
                (x.property_name, x.operator, x.comparison_value)
                for x in metric.categorical_filters.all()
            ],
            "lookback_qty": 1,
            "lookback_units": metric.granularity,
            "reference_time": now_utc(),
        }
        try:
            sf_setting = organization.settings.get(
                setting_name=ORGANIZATION_SETTING_NAMES.SUBSCRIPTION_FILTER_KEYS
            )
            groupby = sf_setting.setting_values
        except OrganizationSetting.DoesNotExist:
            organization.provision_subscription_filter_settings()
            groupby = []
        injection_dict["group_by"] = groupby
        for filter in subscription_record.filters.all():
            injection_dict["filter_properties"][
                filter.property_name
            ] = filter.comparison_value[0]
        query = Template(RATE_GET_CURRENT_USAGE).render(**injection_dict)
        with connection.cursor() as cursor:
            cursor.execute(query)
            results = namedtuplefetchall(cursor)
        if len(results) == 0:
            return Decimal(0)
        return results[0].usage_qty

    @staticmethod
    def get_subscription_record_daily_billable_usage(
        metric: Metric, subscription_record: SubscriptionRecord
    ) -> dict[datetime.date, Decimal]:
        results = RateHandler._rate_cagg_total_results(metric, subscription_record)
        total = results[0].usage_qty
        date = convert_to_date(results[0].bucket)
        return {date: total}

    @staticmethod
    def create_metric(validated_data: dict) -> Metric:
        metric = MetricHandler.create_metric(validated_data)
        RateHandler.create_continuous_aggregate(metric)
        return metric


METRIC_HANDLER_MAP = {
    METRIC_TYPE.COUNTER: CounterHandler,
    METRIC_TYPE.GAUGE: GaugeHandler,
    METRIC_TYPE.RATE: RateHandler,
    METRIC_TYPE.CUSTOM: CustomHandler,
}
