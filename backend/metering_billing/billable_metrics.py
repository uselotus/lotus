import abc
import datetime
from datetime import timedelta
from typing import Optional

from dateutil import parser
from dateutil.relativedelta import relativedelta
from django.apps import apps
from django.db.models import (
    Avg,
    Count,
    DateTimeField,
    Exists,
    F,
    FloatField,
    Max,
    Min,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    Window,
)
from django.db.models.functions import Cast, Trunc
from metering_billing.utils import (
    convert_to_date,
    date_as_min_dt,
    now_utc,
    periods_bwn_twodates,
)
from metering_billing.utils.enums import (
    EVENT_TYPE,
    METRIC_AGGREGATION,
    METRIC_GRANULARITY,
    METRIC_TYPE,
    USAGE_CALC_GRANULARITY,
)

Metric = apps.get_app_config("metering_billing").get_model(model_name="Metric")
Customer = apps.get_app_config("metering_billing").get_model(model_name="Customer")
Event = apps.get_app_config("metering_billing").get_model(model_name="Event")
Subscription = apps.get_app_config("metering_billing").get_model(
    model_name="Subscription"
)


class MetricHandler(abc.ABC):
    @abc.abstractmethod
    def __init__(self, billable_metric: Metric):
        """This method will be called whenever we need to work with a billable metric, whether that's determining usage, or calculating revenue, or generating a bill. You might want to extract the fields you want to work with in the metric and make them instance variables. Additionally, you should double-check that some thinsg you expect are true, for example that the metric type matches the handler, and that the aggregation is supported by the handler. If not, raise an exception."""
        pass

    @abc.abstractmethod
    def get_usage(
        self,
        results_granularity: USAGE_CALC_GRANULARITY,
        start: datetime.date,
        end: datetime.date,
        customer: Optional[Customer],
        group_by: Optional[list[str]],
    ) -> dict[Customer.customer_name, dict[datetime.datetime, float]]:
        """This method will be used to calculate the usage at the given results_granularity. This is purely how much has been used and will typically be used in dahsboarding to show usage of the metric. You should be able to handle any aggregation type returned in the allowed_usage_aggregation_types method.

        Customer can either be a customer object or None. If it is None, then you should return the per-customer usage. If it is a customer object, then you should return the usage for that customer.

        You should return a dictionary of datetime to usage, where the datetime is the start of the time period "results_granularity". For example, if we have an hourly results_granularity from May 1st to May 7th, you should return a dictionary with a maximum of 168 entries (7 days * 24 hours), one for each hour (May 1st 12:00AM, May 1st 1:00 AM, etc.), with the key being the start of the hour and the value being the usage for that hour. If there is no usage for that hour, then it is optional to include it in the dictionary.
        """
        pass

    @abc.abstractmethod
    def get_current_usage(
        self,
        subscription: Subscription,
    ) -> float:
        """This method will be used to calculate how much usage a customer currently has on a subscription. THough there are cases where get_usage and get_current_usage will be the same, there are cases where they will not. For example, if your billable metric is Stateful with a Max aggregation, then your usage over some period will be the max over past readings, but your current usage will be the latest reading."""
        pass

    @abc.abstractmethod
    def get_earned_usage_per_day(
        self, start: datetime.date, end: datetime.date, customer: Customer
    ) -> dict[datetime.datetime, float]:
        """This method will be used when calculating a concept known as "earned revenue" which is very important in accounting. It essentially states that revenue is "earned" not when someone pays, but when you deliver the goods/services at a previously agreed upon price. To accurately calculate accounting metrics, we will need to be able to tell for a given susbcription, where each cent of revenue came from, and the first step for that is to calculate how much billable usage was delivered each day. This method will be used to calculate that.

        Similar to the get current usage method above, this might often look extremely similar to the get usage method, bu there's cases where it can differ quite a bit. For example, if your billable metric is Counter with a Unique aggregation, then your usage per day would naturally make sense to be the number of unique values seen on that day, but you only "earn" from the first time a unique value is seen, so you would attribute the earned usage to that day."""
        pass

    @staticmethod
    @abc.abstractmethod
    def validate_data(data) -> dict:
        """We will use this method when validating post requests to create a billable metric. You should validate the data of the billable metric and return the validated data (can be changed if you want)."""
        pass


class CounterHandler(MetricHandler):
    def __init__(self, billable_metric: Metric):
        self.organization = billable_metric.organization
        self.event_name = billable_metric.event_name
        assert (
            billable_metric.metric_type == METRIC_TYPE.COUNTER
        ), f"Billable metric of type {billable_metric.metric_type} can't be handled by a CounterHandler."
        self.usage_aggregation_type = billable_metric.usage_aggregation_type
        self.property_name = (
            None
            if self.usage_aggregation_type == METRIC_AGGREGATION.COUNT
            or billable_metric.property_name == ""
            else billable_metric.property_name
        )

        assert (
            self.usage_aggregation_type
            in CounterHandler._allowed_usage_aggregation_types()
        ), f"Usage aggregation type {self.usage_aggregation_type} is not allowed for billable metrics of type {billable_metric.metric_type}."

    @staticmethod
    def _allowed_usage_aggregation_types() -> list[METRIC_AGGREGATION]:
        return [
            METRIC_AGGREGATION.UNIQUE,
            METRIC_AGGREGATION.SUM,
            METRIC_AGGREGATION.COUNT,
            METRIC_AGGREGATION.AVERAGE,
            METRIC_AGGREGATION.MAX,
        ]

    def get_usage(
        self,
        results_granularity,
        start,
        end,
        customer=None,
        group_by=[],
    ):
        now = now_utc()
        filter_kwargs = {
            "organization": self.organization,
            "event_name": self.event_name,
            "time_created__lt": now,
            "time_created__gte": start,
            "time_created__lte": end,
        }
        pre_groupby_annotation_kwargs = {}
        groupby_kwargs = {}
        for group_by_property in group_by:
            filter_kwargs["properties__has_key"] = group_by_property
            pre_groupby_annotation_kwargs[group_by_property] = F(
                f"properties__{group_by_property}"
            )
            groupby_kwargs[group_by_property] = F(group_by_property)
        groupby_kwargs["customer_name"] = F("customer__customer_name")
        post_groupby_annotation_kwargs = {}
        if customer:
            filter_kwargs["customer"] = customer
        if self.property_name is not None:
            filter_kwargs["properties__has_key"] = self.property_name
            pre_groupby_annotation_kwargs["property_value"] = F(
                f"properties__{self.property_name}"
            )
        if results_granularity != USAGE_CALC_GRANULARITY.TOTAL:
            groupby_kwargs["time_created_truncated"] = Trunc(
                expression=F("time_created"),
                kind=results_granularity,
                output_field=DateTimeField(),
            )
        else:
            groupby_kwargs["time_created_truncated"] = Value(date_as_min_dt(start))

        if self.usage_aggregation_type == METRIC_AGGREGATION.COUNT:
            post_groupby_annotation_kwargs["usage_qty"] = Count("pk")
        elif self.usage_aggregation_type == METRIC_AGGREGATION.SUM:
            post_groupby_annotation_kwargs["usage_qty"] = Sum(
                Cast(F("property_value"), FloatField())
            )
        elif self.usage_aggregation_type == METRIC_AGGREGATION.AVERAGE:
            post_groupby_annotation_kwargs["usage_qty"] = Avg(
                Cast(F("property_value"), FloatField())
            )
        elif self.usage_aggregation_type == METRIC_AGGREGATION.MAX:
            post_groupby_annotation_kwargs["usage_qty"] = Max(
                Cast(F("property_value"), FloatField())
            )
        elif self.usage_aggregation_type == METRIC_AGGREGATION.UNIQUE:
            post_groupby_annotation_kwargs["usage_qty"] = Count(
                F("property_value"), distinct=True
            )

        q_filt = Event.objects.filter(**filter_kwargs)
        q_pre_gb_ann = q_filt.annotate(**pre_groupby_annotation_kwargs)
        q_gb = q_pre_gb_ann.values(**groupby_kwargs)
        q_post_gb_ann = q_gb.annotate(**post_groupby_annotation_kwargs)

        return_dict = {}
        unique_groupby_props = ["customer_name"] + group_by
        for row in q_post_gb_ann:
            cust_name = row["customer_name"]
            tc_trunc = row["time_created_truncated"]
            unique_tup = tuple(row[prop] for prop in unique_groupby_props)
            usage_qty = row["usage_qty"]
            if cust_name not in return_dict:
                return_dict[cust_name] = {}
            if unique_tup not in return_dict[cust_name]:
                return_dict[cust_name][unique_tup] = {}
            return_dict[cust_name][unique_tup][tc_trunc] = usage_qty
        return return_dict

    def get_current_usage(self, subscription):
        per_customer = self.get_usage(
            start=subscription.start,
            end=subscription.end,
            results_granularity=USAGE_CALC_GRANULARITY.TOTAL,
            customer=subscription.customer,
        )
        assert (
            subscription.customer.customer_name in per_customer
            or len(per_customer) == 0
        )
        if len(per_customer) == 0:
            return 0
        customer_usage = per_customer[subscription.customer.customer_name]
        _, customer_usage_val = list(customer_usage.items())[0]
        return customer_usage_val

    def get_earned_usage_per_day(self, start, end, customer, group_by=[]):
        now = now_utc()
        filter_kwargs = {
            "organization": self.organization,
            "event_name": self.event_name,
            "time_created__lt": now,
            "time_created__gte": start,
            "time_created__lte": end,
            "customer": customer,
        }
        pre_groupby_annotation_kwargs = {}
        groupby_kwargs = {}
        for group_by_property in group_by:
            filter_kwargs["properties__has_key"] = group_by_property
            pre_groupby_annotation_kwargs[group_by_property] = F(
                f"properties__{group_by_property}"
            )
            groupby_kwargs[group_by_property] = F(group_by_property)
        groupby_kwargs["customer_name"] = F("customer__customer_name")
        post_groupby_annotation_kwargs = {}
        if self.property_name is not None:
            filter_kwargs["properties__has_key"] = self.property_name
            pre_groupby_annotation_kwargs["property_value"] = F(
                f"properties__{self.property_name}"
            )
        groupby_kwargs["time_created_truncated"] = Trunc(
            expression=F("time_created"),
            kind=USAGE_CALC_GRANULARITY.DAILY,
            output_field=DateTimeField(),
        )

        if self.usage_aggregation_type == METRIC_AGGREGATION.COUNT:
            post_groupby_annotation_kwargs["usage_qty"] = Count("pk")
        elif self.usage_aggregation_type == METRIC_AGGREGATION.SUM:
            post_groupby_annotation_kwargs["usage_qty"] = Sum(
                Cast(F("property_value"), FloatField())
            )
        elif self.usage_aggregation_type == METRIC_AGGREGATION.AVERAGE:
            post_groupby_annotation_kwargs["usage_qty"] = Avg(
                Cast(F("property_value"), FloatField())
            )
            post_groupby_annotation_kwargs["n_events"] = Count("pk")
        elif self.usage_aggregation_type == METRIC_AGGREGATION.MAX:
            post_groupby_annotation_kwargs = groupby_kwargs
            groupby_kwargs = {}
            post_groupby_annotation_kwargs["usage_qty"] = Cast(
                F("property_value"), FloatField()
            )
        elif self.usage_aggregation_type == METRIC_AGGREGATION.UNIQUE:
            # for unique, we need to find the first time we saw each unique property value. If
            # we just aggregate using count unique, then we'll get the unique per period of
            # granularity, which is not what we want.
            post_groupby_annotation_kwargs = groupby_kwargs
            groupby_kwargs = {}
            post_groupby_annotation_kwargs["usage_qty"] = Count(
                F("property_value"), distinct=True
            )

        q_filt = Event.objects.filter(**filter_kwargs)
        q_pre_gb_ann = q_filt.annotate(**pre_groupby_annotation_kwargs)
        q_gb = q_pre_gb_ann.values(**groupby_kwargs)
        q_post_gb_ann = q_gb.annotate(**post_groupby_annotation_kwargs)

        if self.usage_aggregation_type == METRIC_AGGREGATION.MAX:
            q_post_gb_ann = q_post_gb_ann.order_by("-usage_qty").first()
        elif self.usage_aggregation_type == METRIC_AGGREGATION.UNIQUE:
            q_post_gb_ann = q_post_gb_ann.filter(
                ~Exists(
                    q_post_gb_ann.filter(
                        time_created__lt=OuterRef("time_created"),
                        property_value=OuterRef("property_value"),
                    )
                )
            )
            q_post_gb_ann = q_post_gb_ann.values(
                "time_created_truncated",
            ).annotate(usage_qty=Count("pk"))

        if self.usage_aggregation_type == METRIC_AGGREGATION.AVERAGE:
            return_dict = {}
            total_usage_qty = sum(
                [row["usage_qty"] * row["n_events"] for row in q_post_gb_ann]
            )
            total_num_events = sum([row["n_events"] for row in q_post_gb_ann])
            total_average = total_usage_qty / total_num_events
            for row in q_post_gb_ann:
                tc_trunc = row["time_created_truncated"]
                usage_qty = total_average * (
                    row["usage_qty"] * row["n_events"] / total_usage_qty
                )
                return_dict[tc_trunc] = usage_qty
        else:
            return_dict = {}
            for row in q_post_gb_ann:
                tc_trunc = row["time_created_truncated"]
                usage_qty = row["usage_qty"]
                return_dict[tc_trunc] = usage_qty
        return return_dict

    @staticmethod
    def validate_data(data: dict) -> dict:
        # has been top-level validated by the MetricSerializer, so we can assume
        # certain fields are there and ignore others as needed
        # unpack stuff first
        usg_agg_type = data.get("usage_aggregation_type", None)
        bill_agg_type = data.get("billable_aggregation_type", None)
        metric_type = data.get("metric_type", None)
        event_type = data.get("event_type", None)
        granularity = data.get("granularity", None)
        numeric_filters = data.get("numeric_filters", None)
        categorical_filters = data.get("categorical_filters", None)
        property_name = data.get("property_name", None)

        # now validate
        assert metric_type == METRIC_TYPE.COUNTER
        assert (
            usg_agg_type in CounterHandler._allowed_usage_aggregation_types()
        ), "[METRIC TYPE: COUNTER] Usage aggregation type {} is not allowed.".format(
            usg_agg_type
        )
        if usg_agg_type != METRIC_AGGREGATION.COUNT:
            assert (
                property_name is not None
            ), "[METRIC TYPE: COUNTER] Must specify property name unless using COUNT aggregation"
        else:
            if property_name is not None:
                print(
                    "[METRIC TYPE: COUNTER] Property name specified but not needed for COUNT aggregation"
                )
                data.pop("property_name", None)
        if granularity:
            print("[METRIC TYPE: COUNTER] Granularity type not allowed. Making null.")
            data.pop("granualarity", None)
        if event_type:
            print("[METRIC TYPE: COUNTER] Event type not allowed. Making null.")
            data.pop("event_type", None)
        if numeric_filters or categorical_filters:
            print("[METRIC TYPE: COUNTER] Filters not currently supported. Removing")
            data.pop("numeric_filters", None)
            data.pop("categorical_filters", None)
        if bill_agg_type:
            print(
                "[METRIC TYPE: COUNTER] Billable aggregation type not allowed. Making null."
            )
            data.pop("billable_aggregation_type", None)
        return data


class StatefulHandler(MetricHandler):
    """
    The key difference between a stateful handler and an aggregation handler is that the stateful handler has state across time periods. Even when given a blocked off time period, it'll look for previous values of the event/property in question and use those as a starting point. A common example of a metric that woudl fit under the Stateful pattern would be the number of seats a product has available. When we go into a new billing period, the number of seats doesn't magically disappear... we have to keep track of it. We currently support two types of events: quantity_logging and delta_logging. Quantity logging would look like sending events to the API that say we have x users at the moment. Delta logging would be like sending events that say we added x users or removed x users. The stateful handler will look at the previous value of the metric and add/subtract the delta to get the new value.

    An interesting thing to note is the definition of "usage".
    """

    def __init__(self, billable_metric: Metric):
        self.organization = billable_metric.organization
        self.event_name = billable_metric.event_name
        assert (
            billable_metric.metric_type == METRIC_TYPE.STATEFUL
        ), f"Billable metric of type {billable_metric.metric_type} can't be handled by a CounterHandler."
        self.event_type = billable_metric.event_type
        self.usage_aggregation_type = billable_metric.usage_aggregation_type
        self.granularity = billable_metric.granularity
        self.property_name = (
            None
            if billable_metric.property_name == " "
            or billable_metric.property_name == ""
            else billable_metric.property_name
        )

        assert (
            self.usage_aggregation_type
            in StatefulHandler._allowed_usage_aggregation_types()
        ), f"Usage aggregation type {self.usage_aggregation_type} is not allowed for billable metrics of type {billable_metric.metric_type}."

    @staticmethod
    def validate_data(data: dict) -> dict:
        # has been top-level validated by the MetricSerializer, so we can assume
        # certain fields are there and ignore others as needed

        # unpack stuff first
        usg_agg_type = data.get("usage_aggregation_type", None)
        bill_agg_type = data.get("billable_aggregation_type", None)
        metric_type = data.get("metric_type", None)
        event_type = data.get("event_type", None)
        granularity = data.get("granularity", None)
        numeric_filters = data.get("numeric_filters", None)
        categorical_filters = data.get("categorical_filters", None)
        property_name = data.get("property_name", None)

        # now validate
        assert metric_type == METRIC_TYPE.STATEFUL
        assert (
            usg_agg_type in StatefulHandler._allowed_usage_aggregation_types()
        ), "[METRIC TYPE: STATEFUL] Usage aggregation type {} is not allowed.".format(
            usg_agg_type
        )
        assert granularity, "[METRIC TYPE: STATEFUL] Must specify granularity"
        if numeric_filters or categorical_filters:
            print("[METRIC TYPE: STATEFUL] Filters not currently supported. Removing")
            data.pop("numeric_filters", None)
            data.pop("categorical_filters", None)
        if bill_agg_type:
            print(
                "[METRIC TYPE: STATEFUL] Billable aggregation type not allowed. Making null."
            )
            data.pop("billable_aggregation_type", None)
        assert event_type, "[METRIC TYPE: STATEFUL] Must specify event type."
        assert property_name, "[METRIC TYPE: STATEFUL] Must specify property name."
        return data

    def get_usage(
        self,
        results_granularity,
        start,
        end,
        customer=None,
        group_by=[],
    ):
        return self._get_usage(
            results_granularity,
            start,
            end,
            customer,
            group_by,
            event_type=self.event_type,
        )

    def _get_usage(
        self,
        results_granularity,
        start,
        end,
        customer=None,
        group_by=[],
        event_type=EVENT_TYPE.TOTAL,
    ):
        now = now_utc()
        filter_kwargs = {
            "organization": self.organization,
            "event_name": self.event_name,
            "time_created__lt": now,
            "time_created__gte": start,
            "time_created__lte": end,
            "properties__has_key": self.property_name,
        }
        pre_groupby_annotation_kwargs = {
            "property_value": F(f"properties__{self.property_name}"),
            "customer_name": F("customer__customer_name"),
        }
        groupby_kwargs = {}
        for group_by_property in group_by:
            filter_kwargs["properties__has_key"] = group_by_property
            pre_groupby_annotation_kwargs[group_by_property] = F(
                f"properties__{group_by_property}"
            )
            groupby_kwargs[group_by_property] = F(group_by_property)
        groupby_kwargs["customer_name"] = F("customer__customer_name")
        post_groupby_annotation_kwargs = {}
        if customer:
            filter_kwargs["customer"] = customer
        if self.granularity != METRIC_GRANULARITY.TOTAL:
            groupby_kwargs["time_created_truncated"] = Trunc(
                expression=F("time_created"),
                kind=self.granularity,
                output_field=DateTimeField(),
            )
        else:
            groupby_kwargs["time_created_truncated"] = Value(date_as_min_dt(start))

        q_filt = Event.objects.filter(**filter_kwargs)
        q_pre_gb_ann = q_filt.annotate(**pre_groupby_annotation_kwargs)

        if event_type == EVENT_TYPE.TOTAL:
            if self.usage_aggregation_type == METRIC_AGGREGATION.MAX:
                post_groupby_annotation_kwargs["usage_qty"] = Max(
                    Cast(F("property_value"), FloatField())
                )
            if self.usage_aggregation_type == METRIC_AGGREGATION.LATEST:
                post_groupby_annotation_kwargs = groupby_kwargs
                groupby_kwargs = {}
                post_groupby_annotation_kwargs["usage_qty"] = Cast(
                    F("property_value"), FloatField()
                )

            q_gb = q_pre_gb_ann.values(**groupby_kwargs)
            q_post_gb_ann = q_gb.annotate(**post_groupby_annotation_kwargs)

        elif event_type == EVENT_TYPE.DELTA:
            subquery_dict = {
                "time_created__gte": start,
                "time_created__lte": OuterRef("time_created"),
                "customer": OuterRef("customer"),
            }
            for group_by_property in group_by:
                subquery_dict[group_by_property] = OuterRef(group_by_property)
            subquery = (
                q_pre_gb_ann.filter(**subquery_dict)
                .values(*(["customer_name"] + group_by))
                .annotate(cum_sum=Window(Sum(Cast(F("property_value"), FloatField()))))
            )

            cumulative_per_event = q_pre_gb_ann.annotate(
                usage_qty=Subquery(
                    subquery.values("cum_sum")[:1], output_field=FloatField()
                )
            )

            if self.usage_aggregation_type == METRIC_AGGREGATION.MAX:
                q_post_gb_ann = cumulative_per_event.values(**groupby_kwargs).annotate(
                    usage_qty=Max("usage_qty")
                )
            elif self.usage_aggregation_type == METRIC_AGGREGATION.LATEST:
                q_post_gb_ann = cumulative_per_event.order_by(
                    *(["customer_name"] + group_by), "-time_created"
                ).distinct(*(["customer_name"] + group_by))

        period_usages = {}
        unique_groupby_props = ["customer_name"] + group_by
        for row in q_post_gb_ann:
            cust_name = row["customer_name"]
            tc_trunc = row["time_created_truncated"]
            unique_tup = tuple(row[prop] for prop in unique_groupby_props)
            usage_qty = row["usage_qty"]
            if cust_name not in period_usages:
                period_usages[cust_name] = {}
            if unique_tup not in period_usages[cust_name]:
                period_usages[cust_name][unique_tup] = {}
            period_usages[cust_name][unique_tup][tc_trunc] = usage_qty

        # grab latest value from previous period per customer
        # needed in case there's gaps from data , you would take the "latest" value not the
        # usage value from aprevious period
        latest_filt = {
            "customer_name": OuterRef("customer_name"),
            "time_created_truncated": OuterRef("time_created_truncated"),
        }
        for prop in group_by:
            latest_filt[prop] = OuterRef(prop)
        latest = q_post_gb_ann.filter(**latest_filt).order_by("-time_created")
        latest_per_period = q_post_gb_ann.annotate(
            latest_pk=Subquery(latest.values("pk")[:1])
        ).filter(pk=F("latest_pk"))
        latest_in_period_usages = {}
        for row in latest_per_period:
            cust_name = row["customer_name"]
            tc_trunc = row["time_created_truncated"]
            unique_tup = tuple(row[prop] for prop in unique_groupby_props)
            usage_qty = row["usage_qty"]
            if cust_name not in latest_in_period_usages:
                latest_in_period_usages[cust_name] = {}
            if unique_tup not in latest_in_period_usages[cust_name]:
                latest_in_period_usages[cust_name][unique_tup] = {}
            latest_in_period_usages[cust_name][unique_tup][tc_trunc] = usage_qty
        # grab pre-query initial values
        filter_kwargs = {
            "organization": self.organization,
            "event_name": self.event_name,
            "time_created__lt": start,
            "properties__has_key": self.property_name,
        }
        annotate_kwargs = {
            "property_value": F(f"properties__{self.property_name}"),
            "customer_name": F("customer__customer_name"),
        }
        for group_by_property in group_by:
            filter_kwargs["properties__has_key"] = group_by_property
            annotate_kwargs[group_by_property] = F(f"properties__{group_by_property}")
        pre_query_all_events = Event.objects.filter(**filter_kwargs).annotate(
            **annotate_kwargs
        )
        grouping_filter = {
            "customer_name": OuterRef("customer_name"),
        }
        for prop in group_by:
            latest_filt[prop] = OuterRef(prop)
        last_pre_query_grouped = pre_query_all_events.filter(
            **grouping_filter
        ).order_by("-time_created")
        last_pre_query_actual_events = pre_query_all_events.annotate(
            latest_pk=Subquery(last_pre_query_grouped.values("pk")[:1])
        ).filter(pk=F("latest_pk"))
        last_usages = {}
        for row in last_pre_query_actual_events:
            cust_name = row["customer_name"]
            tc_trunc = row["time_created_truncated"]
            unique_tup = tuple(row[prop] for prop in unique_groupby_props)
            usage_qty = row["usage_qty"]
            if cust_name not in last_usages:
                last_usages[cust_name] = {}
            if unique_tup not in last_usages[cust_name]:
                last_usages[cust_name][unique_tup] = {}
            last_usages[cust_name][unique_tup][tc_trunc] = usage_qty

        # quantize first according to the stateful period
        plan_periods = list(periods_bwn_twodates(self.granularity, start, end))
        # for each period, get the events and calculate the usage
        usage_dict = {}
        for customer_name, cust_usages in period_usages.items():
            usage_dict[customer_name] = {}
            last_usage_cust = last_usages.get(customer_name, {})
            customer_latest_in_period_usages = latest_in_period_usages.get(
                customer_name, {}
            )
            for unique_customer_tuple, unique_usage in cust_usages.items():
                last_usage_unique = last_usage_cust.get(unique_customer_tuple, 0)
                latest_in_period_usages = customer_latest_in_period_usages.get(
                    unique_customer_tuple, {}
                )
                usage_dict[customer_name][unique_customer_tuple] = {}
                for period in plan_periods:
                    # check the usage for that period
                    period_usage = unique_usage.get(period, None)
                    # if its none, then we'll use the last usage
                    if not period_usage:
                        period_usage = last_usage_unique
                    # add revenue and usage to the dict
                    usage_dict[customer_name][unique_customer_tuple][
                        period
                    ] = period_usage
                    # redefine what the "last" one is
                    latest_in_period = latest_in_period_usages.get(period, None)
                    if latest_in_period:
                        last_usage_unique = latest_in_period
                    else:
                        last_usage_unique = period_usage
        # ok we got here, but now we have a problem. Usage dicts is indexed in time periods of
        # self.granularity. However, we need to have it in units of results_granularity. We
        # have two cases: 1) results_granularity is coarser than self.granularity (eg want
        # total usage, but we have self.granularity in days. Let's just pass up the dictionary
        # and let whoever called this function handled that, don't assume. 2) self.
        # granularity is coarser than results_granularity. eg, we are charging for user-months,
        # but we want to get daily usage. In this case, since we aren't billing on this, we can
        # probably just extend that same valeu for the other days
        if self.granularity == results_granularity:  # day = day, total = total
            return usage_dict
        elif (
            results_granularity == USAGE_CALC_GRANULARITY.TOTAL
            and self.granularity != METRIC_GRANULARITY.TOTAL
        ):
            return usage_dict
            # sd = date_as_min_dt(start)
            # new_usage_dict = {}
            # for customer_name, cust_usages in usage_dict.items():
            #     new_usage_dict[customer_name] = {sd: sum(cust_usages.values())}
            # usage_dict = new_usage_dict
        else:
            # this means that the metric granularity is coarser than the results_granularity
            new_usage_dict = {}
            for customer_name, cust_usages in usage_dict.items():
                new_usage_dict[customer_name] = {}
                coarse_periods = sorted(cust_usages.items(), key=lambda x: x[0])
                fine_periods = list(
                    periods_bwn_twodates(results_granularity, start, end)
                )  # daily
                i = 0
                j = 0
                last_amt = 0
                while i < len(fine_periods):
                    try:
                        cur_coarse, coarse_usage = coarse_periods[j]
                    except IndexError:
                        cur_coarse = None
                    cur_fine = fine_periods[i]
                    cc_none = cur_coarse is None
                    cf_less_cc = cur_fine < cur_coarse if not cc_none else False
                    if cc_none or cf_less_cc:
                        new_usage_dict[customer_name][cur_fine] = last_amt
                    else:
                        new_usage_dict[customer_name][cur_fine] = coarse_usage
                        last_amt = coarse_usage
                        j += 1
                    i += 1
            usage_dict = new_usage_dict
        return usage_dict

    def get_current_usage(self, subscription):
        now = now_utc()
        filter_kwargs = {
            "organization": self.organization,
            "event_name": self.event_name,
            "time_created__lt": now,
            "properties__has_key": self.property_name,
            "customer": subscription.customer,
        }
        if self.event_type == EVENT_TYPE.TOTAL:
            last_usage = (
                Event.objects.filter(**filter_kwargs)
                .order_by("-time_created")
                .annotate(property_value=F(f"properties__{self.property_name}"))
                .annotate(usage_qty=Cast(F("property_value"), FloatField()))
            )
            return last_usage.first().usage_qty
        else:
            last_usage = (
                Event.objects.filter(**filter_kwargs)
                .annotate(property_value=F(f"properties__{self.property_name}"))
                .annotate(usage_qty=Cast(F("property_value"), FloatField()))
                .aggregate(tot_qty=Sum("usage_qty"))
            )
            return last_usage.first().tot_qty

    def get_earned_usage_per_day(self, start, end, customer):
        per_customer = self.get_usage(
            start=start,
            end=end,
            results_granularity=USAGE_CALC_GRANULARITY.DAILY,
            customer=customer,
        )
        customer_usage = per_customer.get(customer.customer_name, {})
        return customer_usage

    @staticmethod
    def _allowed_usage_aggregation_types():
        return [
            METRIC_AGGREGATION.MAX,
            METRIC_AGGREGATION.LATEST,
        ]


class RateHandler(MetricHandler):
    """
    A rate handler can be thought of as the exact opposite of a Stateful Handler. A StatefulHandler keeps an underlying state that persists across billing periods. A RateHandler resets it's state in intervals shorter than the billing period. For example, a RateHandler could be used to charge for the number of API calls made in a day, or to limit the number of database insertions per hour. If a StatefulHandler is teh "integral" of a CounterHandler, then a RateHandler is the "derivative" of a CounterHandler.
    """

    def __init__(self, billable_metric: Metric):
        self.organization = billable_metric.organization
        self.event_name = billable_metric.event_name
        assert (
            billable_metric.metric_type == METRIC_TYPE.RATE
        ), f"Billable metric of type {billable_metric.metric_type} can't be handled by a RateHandler."
        self.usage_aggregation_type = billable_metric.usage_aggregation_type
        self.billable_aggregation_type = billable_metric.billable_aggregation_type
        self.granularity = billable_metric.granularity
        self.property_name = (
            None
            if billable_metric.property_name == " "
            or billable_metric.property_name == ""
            else billable_metric.property_name
        )

        assert (
            self.usage_aggregation_type
            in RateHandler._allowed_usage_aggregation_types()
        ), f"Usage aggregation type {self.usage_aggregation_type} is not allowed for billable metrics of type {billable_metric.metric_type}."
        assert (
            self.billable_aggregation_type
            in RateHandler._allowed_billable_aggregation_types()
        ), f"Billable aggregation type {self.billable_aggregation_type} is not allowed for billable metrics of type {billable_metric.metric_type}."

    @staticmethod
    def validate_data(data: dict) -> dict:
        # has been top-level validated by the MetricSerializer, so we can assume
        # certain fields are there and ignore others as needed

        # unpack stuff first
        usg_agg_type = data.get("usage_aggregation_type", None)
        bill_agg_type = data.get("billable_aggregation_type", None)
        metric_type = data.get("metric_type", None)
        event_type = data.get("event_type", None)
        granularity = data.get("granularity", None)
        numeric_filters = data.get("numeric_filters", None)
        categorical_filters = data.get("categorical_filters", None)
        property_name = data.get("property_name", None)

        # now validate
        assert metric_type == METRIC_TYPE.RATE
        assert (
            usg_agg_type in RateHandler._allowed_usage_aggregation_types()
        ), "[METRIC TYPE: RATE] Usage aggregation type {} is not allowed.".format(
            usg_agg_type
        )
        assert (
            bill_agg_type in RateHandler._allowed_billable_aggregation_types()
        ), "[METRIC TYPE: RATE] Billable aggregation type {} is not allowed.".format(
            bill_agg_type
        )
        if usg_agg_type != METRIC_AGGREGATION.COUNT:
            assert (
                property_name is not None
            ), "[METRIC TYPE: RATE] Must specify property name unless using COUNT aggregation"
        else:
            if property_name is not None:
                print(
                    "[METRIC TYPE: RATE] Property name specified but not needed for COUNT aggregation"
                )
                data.pop("property_name", None)
        assert granularity, "[METRIC TYPE: RATE] Must specify granularity"
        if numeric_filters or categorical_filters:
            print("[METRIC TYPE: RATE] Filters not currently supported. Removing")
            data.pop("numeric_filters", None)
            data.pop("categorical_filters", None)
        if event_type:
            print("[METRIC TYPE: RATE] Event type not allowed. Making null.")
            data.pop("event_type", None)
        return data

    def _floor_dt(self, dt, delta):
        return dt - (datetime.datetime.min - dt) % delta

    def _get_current_query_start_end(self):
        now = now_utc()
        end = now
        start = now - relativedelta(**{self.granularity: 1})
        return start, end

    def get_current_usage(self, subscription, group_by=[]):
        start, end = self._get_current_query_start_end(subscription)
        filter_kwargs = {
            "organization": self.organization,
            "event_name": self.event_name,
            "time_created__lte": end,
            "time_created__gte": start,
            "customer": subscription.customer,
        }
        if self.property_name is not None:
            filter_kwargs["properties__has_key"] = self.property_name
            pre_groupby_annotation_kwargs["property_value"] = F(
                f"properties__{self.property_name}"
            )

        pre_groupby_annotation_kwargs = {}
        groupby_kwargs = {}
        for group_by_property in group_by:
            filter_kwargs["properties__has_key"] = group_by_property
            pre_groupby_annotation_kwargs[group_by_property] = F(
                f"properties__{group_by_property}"
            )
            groupby_kwargs[group_by_property] = F(group_by_property)
        groupby_kwargs["customer_name"] = F("customer__customer_name")
        post_groupby_annotation_kwargs = {}
        if self.usage_aggregation_type == METRIC_AGGREGATION.COUNT:
            post_groupby_annotation_kwargs["usage_qty"] = Count("pk")
        elif self.usage_aggregation_type == METRIC_AGGREGATION.SUM:
            post_groupby_annotation_kwargs["usage_qty"] = Sum(
                Cast(F("property_value"), FloatField())
            )
        elif self.usage_aggregation_type == METRIC_AGGREGATION.AVERAGE:
            post_groupby_annotation_kwargs["usage_qty"] = Avg(
                Cast(F("property_value"), FloatField())
            )
        elif self.usage_aggregation_type == METRIC_AGGREGATION.MAX:
            post_groupby_annotation_kwargs["usage_qty"] = Max(
                Cast(F("property_value"), FloatField())
            )
        elif self.usage_aggregation_type == METRIC_AGGREGATION.UNIQUE:
            post_groupby_annotation_kwargs["usage_qty"] = Count(
                F("property_value"), distinct=True
            )

        q_filt = Event.objects.filter(**filter_kwargs)
        q_pre_gb_ann = q_filt.annotate(**pre_groupby_annotation_kwargs)
        q_gb = q_pre_gb_ann.values(**groupby_kwargs)
        q_post_gb_ann = q_gb.annotate(**post_groupby_annotation_kwargs)

        event = q_post_gb_ann.first()
        if event:
            return event["usage_qty"]
        return 0

    def get_usage(
        self,
        results_granularity,
        start,
        end,
        customer=None,
        group_by=[],
    ):
        now = now_utc()
        filter_kwargs = {
            "organization": self.organization,
            "event_name": self.event_name,
            "time_created__lt": now,
            "time_created__gte": start,
            "time_created__lte": end,
        }
        pre_groupby_annotation_kwargs = {
            "property_value": F(f"properties__{self.property_name}"),
            "customer_name": F("customer__customer_name"),
        }
        groupby_kwargs = {}
        for group_by_property in group_by:
            filter_kwargs["properties__has_key"] = group_by_property
            # filter_kwargs[f"properties__{group_by_property}__isnull"] = False 
            pre_groupby_annotation_kwargs[group_by_property] = F(
                f"properties__{group_by_property}"
            )
            groupby_kwargs[group_by_property] = F(group_by_property)
        groupby_kwargs["customer_name"] = F("customer__customer_name")

        if results_granularity != USAGE_CALC_GRANULARITY.TOTAL:
            groupby_kwargs["time_created_truncated"] = Trunc(
                expression=F("time_created"),
                kind=results_granularity,
                output_field=DateTimeField(),
            )
        else:
            groupby_kwargs["time_created_truncated"] = Value(date_as_min_dt(start))

        if customer:
            filter_kwargs["customer"] = customer
        if self.property_name is not None:
            filter_kwargs["properties__has_key"] = self.property_name
            pre_groupby_annotation_kwargs["property_value"] = F(
                f"properties__{self.property_name}"
            )

        q_filt = Event.objects.filter(**filter_kwargs)
        q_pre_gb_ann = q_filt.annotate(**pre_groupby_annotation_kwargs)

        subquery_dict = {
            "time_created__gte": OuterRef("time_created")
            - timedelta(**{self.granularity: 1}),
            "time_created__lte": OuterRef("time_created"),
            "customer": OuterRef("customer"),
        }
        for group_by_property in group_by:
            subquery_dict[group_by_property] = OuterRef(group_by_property)
        subquery = q_pre_gb_ann.filter(**subquery_dict).values(
            *(["customer"] + group_by)
        )

        if self.usage_aggregation_type == METRIC_AGGREGATION.COUNT:
            subquery = subquery.annotate(usage_qty=Window(Count("pk")))
        elif self.usage_aggregation_type == METRIC_AGGREGATION.SUM:
            subquery = subquery.annotate(
                usage_qty=Window(Sum(Cast(F("property_value"), FloatField())))
            )
        elif self.usage_aggregation_type == METRIC_AGGREGATION.AVERAGE:
            subquery = subquery.annotate(
                usage_qty=Window(Avg(Cast(F("property_value"), FloatField())))
            )
        elif self.usage_aggregation_type == METRIC_AGGREGATION.MAX:
            subquery = subquery.annotate(
                usage_qty=Window(Max(Cast(F("property_value"), FloatField())))
            )

        rate_per_event = q_pre_gb_ann.annotate(
            usage_qty=Subquery(
                subquery.values("usage_qty")[:1], output_field=FloatField()
            )
        )

        q_gb = rate_per_event.values(**groupby_kwargs)
        q_post_gb_ann = q_gb.annotate(new_usage_qty=Max("usage_qty"))

        return_dict = {}
        unique_groupby_props = ["customer_name"] + group_by
        for row in q_post_gb_ann:
            cust_name = row["customer_name"]
            tc_trunc = row["time_created_truncated"]
            unique_tup = tuple(row[prop] for prop in unique_groupby_props)
            usage_qty = row["new_usage_qty"]
            if cust_name not in return_dict:
                return_dict[cust_name] = {}
            if unique_tup not in return_dict[cust_name]:
                return_dict[cust_name][unique_tup] = {}
            return_dict[cust_name][unique_tup][tc_trunc] = usage_qty

        return return_dict

    def get_earned_usage_per_day(self, start, end, customer):
        per_customer = self.get_usage(
            start=start,
            end=end,
            granularity=USAGE_CALC_GRANULARITY.DAILY,
            customer=customer,
        )
        customer_usage = per_customer[customer.customer_name]
        if len(customer_usage) == 0:
            return {}
        else:
            max_usage = sorted(
                customer_usage.items(), key=lambda x: x[1], reverse=True
            )[:1]
            return {max_usage[0][0]: max_usage[0][1]}

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


METRIC_HANDLER_MAP = {
    METRIC_TYPE.COUNTER: CounterHandler,
    METRIC_TYPE.STATEFUL: StatefulHandler,
    METRIC_TYPE.RATE: RateHandler,
}
