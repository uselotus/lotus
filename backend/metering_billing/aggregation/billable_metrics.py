import abc
import datetime
import logging
from datetime import timedelta
from typing import Optional, TypedDict

import sqlparse
from dateutil import parser
from dateutil.relativedelta import relativedelta
from django.apps import apps
from django.db import connection
from django.db.models import *
from django.db.models.functions import Cast, Trunc
from jinja2 import Template
from metering_billing.exceptions.exceptions import *
from metering_billing.utils import *
from metering_billing.utils.enums import *

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
    def get_usage(
        self,
        results_granularity: USAGE_CALC_GRANULARITY,
        start: datetime.date,
        end: datetime.date,
        customer: Optional[Customer],
        proration: Optional[METRIC_GRANULARITY],
        filters: Optional[dict[str, str]],
    ) -> dict[Customer.customer_name, dict[datetime.datetime, float]]:
        """This method will be used to calculate the usage at the given results_granularity. This is purely how much has been used and will typically be used in dahsboarding to show usage of the metric. You should be able to handle any aggregation type returned in the allowed_usage_aggregation_types method.

        Customer can either be a customer object or None. If it is None, then you should return the per-customer usage. If it is a customer object, then you should return the usage for that customer.

        You should return a dictionary of datetime to usage, where the datetime is the start of the time period "results_granularity". For example, if we have an hourly results_granularity from May 1st to May 7th, you should return a dictionary with a maximum of 168 entries (7 days * 24 hours), one for each hour (May 1st 12:00AM, May 1st 1:00 AM, etc.), with the key being the start of the hour and the value being the usage for that hour. If there is no usage for that hour, then it is optional to include it in the dictionary.
        """
        pass

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

    @abc.abstractmethod
    def _build_filter_kwargs(self, start, end, customer, filters=None):
        """This method will be used to build the filter args for the get_usage and get_earned_usage_per_day methods. You should build the filter args for the Event model, and return them as a dictionary. You should also handle the case where customer is None, which means that you should return the usage for all customers."""
        if filters is None:
            filters = {}
        now = now_utc()
        filter_kwargs = {
            "organization": self.organization,
            "event_name": self.event_name,
            "time_created__lt": now,
            "time_created__gte": start,
            "time_created__lte": end,
        }
        if self.property_name is not None:
            filter_kwargs["properties__has_key"] = self.property_name
            filter_kwargs[f"properties__{self.property_name}__isnull"] = False
        if customer is not None:
            filter_kwargs["customer"] = customer
        filter_args = []
        for f in self.numeric_filters:
            comparator_string = (
                "" if f.operator == NUMERIC_FILTER_OPERATORS.EQ else f"__{f.operator}"
            )
            d = {
                f"properties__{f.property_name}{comparator_string}": f.comparison_value
            }
            filter_args.append(Q(**d))
        for f in self.categorical_filters:
            d = {f"properties__{f.property_name}__in": f.comparison_value}
            q = Q(**d) if f.operator == CATEGORICAL_FILTER_OPERATORS.ISIN else ~Q(**d)
            filter_args.append(q)
        for filter_name, filter_value in filters.items():
            filter_args.append(Q(**{f"properties__{filter_name}": filter_value}))
        return filter_args, filter_kwargs

    @abc.abstractmethod
    def _build_pre_groupby_annotation_kwargs(self):
        pre_groupby_annotation_kwargs = {
            "customer_name": F("customer__customer_name"),
        }
        if self.property_name is not None:
            pre_groupby_annotation_kwargs["property_value"] = F(
                f"properties__{self.property_name}"
            )
        return pre_groupby_annotation_kwargs

    @abc.abstractmethod
    def _build_groupby_kwargs(
        self, customer, results_granularity, start, proration=None
    ):
        groupby_kwargs = {}
        groupby_kwargs["customer_name"] = F("customer__customer_name")

        if self.billable_metric.metric_type == METRIC_TYPE.GAUGE:
            kind = None
            granularity = None
            if (
                self.granularity == METRIC_GRANULARITY.SECOND
                or proration == METRIC_GRANULARITY.SECOND
            ):
                kind = "second"
                granularity = METRIC_GRANULARITY.SECOND
            elif (
                self.granularity == METRIC_GRANULARITY.MINUTE
                or proration == METRIC_GRANULARITY.MINUTE
            ):
                kind = "minute"
                granularity = METRIC_GRANULARITY.MINUTE
            elif (
                self.granularity == METRIC_GRANULARITY.HOUR
                or proration == METRIC_GRANULARITY.HOUR
            ):
                kind = "hour"
                granularity = METRIC_GRANULARITY.HOUR
            elif (
                self.granularity == METRIC_GRANULARITY.DAY
                or proration == METRIC_GRANULARITY.DAY
            ):
                kind = "day"
                granularity = METRIC_GRANULARITY.DAY
            elif (
                self.granularity == METRIC_GRANULARITY.MONTH
                or proration == METRIC_GRANULARITY.MONTH
            ):
                kind = "month"
                granularity = METRIC_GRANULARITY.MONTH
            elif (
                self.granularity == METRIC_GRANULARITY.QUARTER
                or proration == METRIC_GRANULARITY.QUARTER
            ):
                kind = "quarter"
                granularity = METRIC_GRANULARITY.QUARTER
            if kind is not None:
                groupby_kwargs["time_created_truncated"] = Trunc(
                    expression=F("time_created"),
                    kind=kind,
                    output_field=DateTimeField(),
                )
            else:
                groupby_kwargs["time_created_truncated"] = Value(start)
            if granularity:
                groupby_kwargs["granularity"] = granularity
        else:
            if results_granularity == USAGE_CALC_GRANULARITY.DAILY:
                groupby_kwargs["time_created_truncated"] = Trunc(
                    expression=F("time_created"),
                    kind=USAGE_CALC_GRANULARITY.DAILY,
                    output_field=DateTimeField(),
                )
            else:
                groupby_kwargs["time_created_truncated"] = Value(date_as_min_dt(start))

        return groupby_kwargs

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
        bm = Metric.objects.create(**validated_data)

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
                setting_name=ORGANIZATION_SETTING_NAMES.SUBSCRIPTION_FILTERS
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
        from metering_billing.models import Organization, OrganizationSetting

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
        numeric_filters = data.get("numeric_filters", None)
        categorical_filters = data.get("categorical_filters", None)
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
        from metering_billing.models import OrganizationSetting

        if metric.usage_aggregation_type != METRIC_AGGREGATION.UNIQUE:
            # unfortunately there's no good way to make caggs for unique
            # if we're refreshing the matview, then we need to drop the last
            # one and recreate it
            from metering_billing.models import Organization

            from .common_query_templates import CAGG_COMPRESSION, CAGG_REFRESH
            from .counter_query_templates import COUNTER_CAGG_QUERY

            organization = Organization.objects.prefetch_related("settings").get(
                id=metric.organization.id
            )
            if refresh is True:
                CounterHandler.archive_metric(metric)
            try:
                groupby = organization.settings.get(
                    setting_name=ORGANIZATION_SETTING_NAMES.SUBSCRIPTION_FILTERS
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
            day_refresh_query = Template(CAGG_REFRESH).render(**sql_injection_data)
            sql_injection_data["cagg_name"] = base_name + "second"
            sql_injection_data["bucket_size"] = "second"
            second_query = Template(COUNTER_CAGG_QUERY).render(**sql_injection_data)
            second_refresh_query = Template(CAGG_REFRESH).render(**sql_injection_data)
            second_compression_query = Template(CAGG_COMPRESSION).render(
                **sql_injection_data
            )
            with connection.cursor() as cursor:
                cursor.execute(day_query)
                cursor.execute(day_refresh_query)
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
        day_query = Template(CAGG_DROP).render(**sql_injection_data)
        sql_injection_data = {"cagg_name": base_name + "second"}
        second_query = Template(CAGG_DROP).render(**sql_injection_data)
        with connection.cursor() as cursor:
            cursor.execute(day_query)
            cursor.execute(second_query)


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
    def get_subscription_record_current_usage(
        metric: Metric, subscription_record: SubscriptionRecord
    ) -> Decimal:
        return CounterHandler.get_subscription_record_total_billable_usage(
            metric, subscription_record
        )

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
        numeric_filters = data.get("numeric_filters", None)
        categorical_filters = data.get("categorical_filters", None)
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

        from .common_query_templates import CAGG_COMPRESSION, CAGG_REFRESH
        from .gauge_query_templates import (
            GAUGE_DELTA_CREATE_TRIGGER_FN,
            GAUGE_DELTA_CUMULATIVE_SUM,
            GAUGE_DELTA_DELETE_TRIGGER,
            GAUGE_DELTA_INSERT_TRIGGER,
            GAUGE_DELTA_UPDATE_TRIGGER,
            GAUGE_TOTAL_CUMULATIVE_SUM,
        )

        organization = Organization.objects.prefetch_related("settings").get(
            id=metric.organization.id
        )
        if refresh is True:
            GaugeHandler.archive_metric(metric)
        try:
            groupby = organization.settings.get(
                setting_name=ORGANIZATION_SETTING_NAMES.SUBSCRIPTION_FILTERS
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
            trigger_fn = Template(GAUGE_DELTA_CREATE_TRIGGER_FN).render(
                **sql_injection_data
            )
            trigger1 = Template(GAUGE_DELTA_DELETE_TRIGGER).render(**sql_injection_data)
            trigger2 = Template(GAUGE_DELTA_INSERT_TRIGGER).render(**sql_injection_data)
            trigger3 = Template(GAUGE_DELTA_UPDATE_TRIGGER).render(**sql_injection_data)
        elif metric.event_type == "total":
            query = Template(GAUGE_TOTAL_CUMULATIVE_SUM).render(**sql_injection_data)
        else:
            raise ValueError(
                "Invalid event type for gauge: {}".format(metric.event_type)
            )
        refresh_query = Template(CAGG_REFRESH).render(**sql_injection_data)
        compression_query = Template(CAGG_COMPRESSION).render(**sql_injection_data)
        with connection.cursor() as cursor:
            cursor.execute(query)
            if metric.event_type == "delta":
                cursor.execute(trigger_fn)
                cursor.execute(trigger1)
                cursor.execute(trigger2)
                cursor.execute(trigger3)
            else:
                cursor.execute(refresh_query)
                cursor.execute(compression_query)

    @staticmethod
    def archive_metric(metric: Metric) -> Metric:
        from .common_query_templates import CAGG_DROP
        from .gauge_query_templates import GAUGE_DELTA_DROP_TRIGGER

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
            trigger = Template(GAUGE_DELTA_DROP_TRIGGER).render(**sql_injection_data)
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

        from .gauge_query_templates import GAUGE_GET_TOTAL_USAGE_WITH_PRORATION

        organization = Organization.objects.prefetch_related("settings").get(
            id=metric.organization.id
        )
        try:
            groupby = organization.settings.get(
                setting_name=ORGANIZATION_SETTING_NAMES.SUBSCRIPTION_FILTERS
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
        }
        for filter in subscription_record.filters.all():
            injection_dict["filter_properties"][
                filter.property_name
            ] = filter.comparison_value[0]
        query = Template(GAUGE_GET_TOTAL_USAGE_WITH_PRORATION).render(**injection_dict)
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

        from .gauge_query_templates import GAUGE_GET_CURRENT_USAGE

        organization = Organization.objects.prefetch_related("settings").get(
            id=metric.organization.id
        )
        try:
            groupby = organization.settings.get(
                setting_name=ORGANIZATION_SETTING_NAMES.SUBSCRIPTION_FILTERS
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
        }
        for filter in subscription_record.filters.all():
            injection_dict["filter_properties"][
                filter.property_name
            ] = filter.comparison_value[0]
        query = Template(GAUGE_GET_CURRENT_USAGE).render(**injection_dict)
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

        from .gauge_query_templates import GAUGE_GET_TOTAL_USAGE_WITH_PRORATION_PER_DAY

        organization = Organization.objects.prefetch_related("settings").get(
            id=metric.organization.id
        )
        try:
            groupby = organization.settings.get(
                setting_name=ORGANIZATION_SETTING_NAMES.SUBSCRIPTION_FILTERS
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
        }
        for filter in subscription_record.filters.all():
            injection_dict["filter_properties"][
                filter.property_name
            ] = filter.comparison_value[0]
        query = Template(GAUGE_GET_TOTAL_USAGE_WITH_PRORATION_PER_DAY).render(
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
        numeric_filters = data.get("numeric_filters", None)
        categorical_filters = data.get("categorical_filters", None)
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
    def create_continuous_aggregate(metric: Metric, refresh=False):
        # from metering_billing.models import OrganizationSetting

        # from .common_query_templates import CAGG_COMPRESSION, CAGG_REFRESH
        # from .rate_query_templates import RATE_CAGG_QUERY

        # if refresh is True:
        #     RateHandler.archive_metric(metric)
        # try:
        #     groupby = metric.organization.settings.get(
        #         setting_name=ORGANIZATION_SETTING_NAMES.SUBSCRIPTION_FILTERS
        #     )
        #     groupby = groupby.setting_values
        # except OrganizationSetting.DoesNotExist:
        #     metric.organization.provision_subscription_filter_settings()
        #     groupby = []
        # sql_injection_data = {
        #     "query_type": metric.usage_aggregation_type,
        #     "property_name": metric.property_name,
        #     "group_by": groupby,
        #     "event_name": metric.event_name,
        #     "organization_id": metric.organization.id,
        #     "numeric_filters": [
        #         (x.property_name, x.operator, x.comparison_value)
        #         for x in metric.numeric_filters.all()
        #     ],
        #     "categorical_filters": [
        #         (x.property_name, x.operator, x.comparison_value)
        #         for x in metric.categorical_filters.all()
        #     ],
        #     "lookback_qty": 1,
        #     "lookback_units": metric.granularity,
        # }
        # for continuous_agg_type in ["second"]:
        #     sql_injection_data["cagg_name"] = (
        #         metric.organization.organization_id[:22]
        #         + "___"
        #         + ("metric_" + metric.metric_id.hex)[:22]
        #         + "___"
        #         + continuous_agg_type
        #     )
        #     sql_injection_data["bucket_size"] = continuous_agg_type
        #     query = Template(RATE_CAGG_QUERY).render(**sql_injection_data)
        #     refresh_query = Template(CAGG_REFRESH).render(**sql_injection_data)
        #     compression_query = Template(CAGG_COMPRESSION).render(**sql_injection_data)
        #     with connection.cursor() as cursor:
        #         cursor.execute(query)
        #         cursor.execute(refresh_query)
        #         if continuous_agg_type == "second":
        #             cursor.execute(compression_query)
        pass

    @staticmethod
    def archive_metric(metric: Metric) -> Metric:
        # from metering_billing.models import Organization

        # from .common_query_templates import CAGG_DROP

        # organization = Organization.objects.prefetch_related("settings").get(
        #     id=metric.organization.id
        # )
        # sql_injection_data = {
        #     "cagg_name": (
        #         organization.organization_id[:22]
        #         + "___"
        #         + ("metric_" + metric.metric_id.hex)[:22]
        #         + "___"
        #         + "second"
        #     ),
        # }
        # query = Template(CAGG_DROP).render(**sql_injection_data)
        # with connection.cursor() as cursor:
        #     cursor.execute(query)
        # return metric
        pass

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
            + "second",
            "lookback_qty": 1,
            "lookback_units": metric.granularity,
            "property_name": metric.property_name,
            "event_name": metric.event_name,
        }
        try:
            sf_setting = organization.settings.get(
                setting_name=ORGANIZATION_SETTING_NAMES.SUBSCRIPTION_FILTERS
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
                setting_name=ORGANIZATION_SETTING_NAMES.SUBSCRIPTION_FILTERS
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
