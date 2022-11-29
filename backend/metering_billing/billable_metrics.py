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
    CATEGORICAL_FILTER_OPERATORS,
    EVENT_TYPE,
    METRIC_AGGREGATION,
    METRIC_GRANULARITY,
    METRIC_TYPE,
    NUMERIC_FILTER_OPERATORS,
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
        proration: Optional[METRIC_GRANULARITY],
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
        group_by: list[str] = [],
    ) -> float:
        """This method will be used to calculate how much usage a customer currently has on a subscription. THough there are cases where get_usage and get_current_usage will be the same, there are cases where they will not. For example, if your billable metric is Stateful with a Max aggregation, then your usage over some period will be the max over past readings, but your current usage will be the latest reading."""
        pass

    @abc.abstractmethod
    def get_earned_usage_per_day(
        self,
        start: datetime.date,
        end: datetime.date,
        customer: Customer,
        group_by: list[str] = [],
        proration: Optional[METRIC_GRANULARITY] = None,
    ) -> dict[datetime.datetime, float]:
        """This method will be used when calculating a concept known as "earned revenue" which is very important in accounting. It essentially states that revenue is "earned" not when someone pays, but when you deliver the goods/services at a previously agreed upon price. To accurately calculate accounting metrics, we will need to be able to tell for a given susbcription, where each cent of revenue came from, and the first step for that is to calculate how much billable usage was delivered each day. This method will be used to calculate that.

        Similar to the get current usage method above, this might often look extremely similar to the get usage method, bu there's cases where it can differ quite a bit. For example, if your billable metric is Counter with a Unique aggregation, then your usage per day would naturally make sense to be the number of unique values seen on that day, but you only "earn" from the first time a unique value is seen, so you would attribute the earned usage to that day."""
        pass

    @abc.abstractmethod
    def _build_filter_kwargs(self, start, end, customer, group_by=[]):
        """This method will be used to build the filter args for the get_usage and get_earned_usage_per_day methods. You should build the filter args for the Event model, and return them as a dictionary. You should also handle the case where customer is None, which means that you should return the usage for all customers."""
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
        if len(group_by) > 0:
            filter_kwargs["properties__has_keys"] = []
            for group in group_by:
                filter_kwargs["properties__has_keys"].append(group)
                filter_kwargs[f"properties__{group}__isnull"] = False
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
        return filter_args, filter_kwargs

    @abc.abstractmethod
    def _build_pre_groupby_annotation_kwargs(self, group_by=[]):
        pre_groupby_annotation_kwargs = {
            "customer_name": F("customer__customer_name"),
        }
        if self.property_name is not None:
            pre_groupby_annotation_kwargs["property_value"] = F(
                f"properties__{self.property_name}"
            )
        for group_by_property in group_by:
            pre_groupby_annotation_kwargs[group_by_property] = F(
                f"properties__{group_by_property}"
            )
        return pre_groupby_annotation_kwargs

    @abc.abstractmethod
    def _build_groupby_kwargs(
        self, customer, results_granularity, start, group_by=[], proration=None
    ):
        groupby_kwargs = {}
        for group_by_property in group_by:
            groupby_kwargs[group_by_property] = F(group_by_property)
        groupby_kwargs["customer_name"] = F("customer__customer_name")

        if self.billable_metric.metric_type == METRIC_TYPE.STATEFUL:
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
            if kind != None:
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


class CounterHandler(MetricHandler):
    def __init__(self, billable_metric: Metric):
        self.organization = billable_metric.organization
        self.event_name = billable_metric.event_name
        self.billable_metric = billable_metric
        assert (
            billable_metric.metric_type == METRIC_TYPE.COUNTER
        ), f"Billable metric of type {billable_metric.metric_type} can't be handled by a CounterHandler."
        self.usage_aggregation_type = billable_metric.usage_aggregation_type
        self.numeric_filters = billable_metric.numeric_filters.all()
        self.categorical_filters = billable_metric.categorical_filters.all()
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

    def _build_filter_kwargs(self, start, end, customer, group_by=[]):
        return super()._build_filter_kwargs(start, end, customer, group_by)

    def _build_pre_groupby_annotation_kwargs(self, group_by=[]):
        return super()._build_pre_groupby_annotation_kwargs(group_by)

    def _build_groupby_kwargs(
        self, customer, results_granularity, start, group_by=[], proration=None
    ):
        return super()._build_groupby_kwargs(
            customer, results_granularity, start, group_by, proration
        )

    def get_usage(
        self,
        results_granularity,
        start,
        end,
        customer=None,
        group_by=[],
        proration=None,
    ):
        filter_args, filter_kwargs = self._build_filter_kwargs(
            start, end, customer, group_by
        )
        pre_groupby_annotation_kwargs = self._build_pre_groupby_annotation_kwargs(
            group_by
        )
        groupby_kwargs = self._build_groupby_kwargs(
            customer, results_granularity, start, group_by
        )
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
        q_filt = Event.objects.filter(*filter_args, **filter_kwargs)
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

    def get_current_usage(self, subscription, group_by=[]):
        per_customer = self.get_usage(
            start=subscription.start_date,
            end=subscription.end_date,
            results_granularity=USAGE_CALC_GRANULARITY.TOTAL,
            customer=subscription.customer,
            group_by=group_by,
        )
        assert (
            subscription.customer.customer_name in per_customer
            or len(per_customer) == 0
        )
        return per_customer

    def get_earned_usage_per_day(
        self, start, end, customer, group_by=[], proration=None
    ):
        filter_args, filter_kwargs = self._build_filter_kwargs(
            start, end, customer, group_by
        )
        pre_groupby_annotation_kwargs = self._build_pre_groupby_annotation_kwargs(
            group_by
        )
        groupby_kwargs = self._build_groupby_kwargs(
            customer,
            results_granularity=USAGE_CALC_GRANULARITY.DAILY,
            start=start,
            group_by=group_by,
            proration=proration,
        )
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

        q_filt = Event.objects.filter(*filter_args, **filter_kwargs)
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
            intermediate_dict = {}
            unique_groupby_props = ["customer_name"] + group_by
            for row in q_post_gb_ann:
                tc_trunc = row["time_created_truncated"]
                unique_tup = tuple(row[prop] for prop in unique_groupby_props)
                usage_qty = row["usage_qty"]
                if unique_tup not in intermediate_dict:
                    intermediate_dict[unique_tup] = {}
                if tc_trunc not in intermediate_dict[unique_tup]:
                    intermediate_dict[unique_tup][tc_trunc] = {
                        "usage_qty": usage_qty,
                        "n_events": row["n_events"],
                    }
            return_dict = {}
            for unique_tup, v in intermediate_dict.items():
                return_dict[unique_tup] = {}
                total_usage_qty = sum([row["usage_qty"] * row["n_events"] for row in v])
                total_num_events = sum([row["n_events"] for row in v])
                total_average = total_usage_qty / total_num_events
                for row in v:
                    tc_trunc = row["time_created_truncated"]
                    usage_qty = total_average * (
                        row["usage_qty"] * row["n_events"] / total_usage_qty
                    )
                    return_dict[unique_tup][tc_trunc] = usage_qty
        else:
            return_dict = {}
            unique_groupby_props = ["customer_name"] + group_by
            for row in q_post_gb_ann:
                tc_trunc = row["time_created_truncated"]
                unique_tup = tuple(row[prop] for prop in unique_groupby_props)
                usage_qty = row["usage_qty"]
                if unique_tup not in return_dict:
                    return_dict[unique_tup] = {}
                if tc_trunc not in return_dict[unique_tup]:
                    return_dict[unique_tup][tc_trunc] = usage_qty
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
            data.pop("granularity", None)
        if event_type:
            print("[METRIC TYPE: COUNTER] Event type not allowed. Making null.")
            data.pop("event_type", None)
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
        self.billable_metric = billable_metric
        assert (
            billable_metric.metric_type == METRIC_TYPE.STATEFUL
        ), f"Billable metric of type {billable_metric.metric_type} can't be handled by a CounterHandler."
        self.event_type = billable_metric.event_type
        self.usage_aggregation_type = billable_metric.usage_aggregation_type
        self.granularity = billable_metric.granularity
        self.numeric_filters = billable_metric.numeric_filters.all()
        self.categorical_filters = billable_metric.categorical_filters.all()
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
        if bill_agg_type:
            print(
                "[METRIC TYPE: STATEFUL] Billable aggregation type not allowed. Making null."
            )
            data.pop("billable_aggregation_type", None)
        assert event_type, "[METRIC TYPE: STATEFUL] Must specify event type."
        assert property_name, "[METRIC TYPE: STATEFUL] Must specify property name."
        return data

    def _build_filter_kwargs(self, start, end, customer, group_by=[]):
        return super()._build_filter_kwargs(start, end, customer, group_by)

    def _build_pre_groupby_annotation_kwargs(self, group_by=[]):
        return super()._build_pre_groupby_annotation_kwargs(group_by)

    def _build_groupby_kwargs(
        self, customer, results_granularity, start, group_by=[], proration=None
    ):
        return super()._build_groupby_kwargs(
            customer, results_granularity, start, group_by, proration
        )

    def get_usage(
        self,
        results_granularity,
        start,
        end,
        customer=None,
        group_by=[],
        proration=None,
    ):
        filter_args, filter_kwargs = self._build_filter_kwargs(
            start, end, customer, group_by
        )
        pre_groupby_annotation_kwargs = self._build_pre_groupby_annotation_kwargs(
            group_by
        )
        groupby_kwargs = self._build_groupby_kwargs(
            customer, results_granularity, start, group_by, proration
        )
        smallest_granularity = groupby_kwargs.pop("granularity", None)
        post_groupby_annotation_kwargs = {}
        q_filt = Event.objects.filter(*filter_args, **filter_kwargs)
        q_pre_gb_ann = q_filt.annotate(**pre_groupby_annotation_kwargs)
        if self.event_type == EVENT_TYPE.TOTAL:
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

        elif self.event_type == EVENT_TYPE.DELTA:
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
                q_post_gb_ann = (
                    cumulative_per_event.order_by(
                        *(["customer_name"] + group_by), "-time_created"
                    )
                    .distinct(*(["customer_name"] + group_by))
                    .values()
                    .annotate(
                        time_created_truncated=groupby_kwargs["time_created_truncated"]
                    )
                )

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
        filter_kwargs["time_created__lt"] = start
        del filter_kwargs["time_created__gte"]
        annotate_kwargs = {
            "property_value": F(f"properties__{self.property_name}"),
            "customer_name": F("customer__customer_name"),
        }
        for group_by_property in group_by:
            annotate_kwargs[group_by_property] = F(f"properties__{group_by_property}")
        pre_query_all_events = Event.objects.filter(
            *filter_args, **filter_kwargs
        ).annotate(**annotate_kwargs)
        grouping_filter = {
            "customer_name": OuterRef("customer_name"),
        }
        for prop in group_by:
            grouping_filter[prop] = OuterRef(prop)
        if self.event_type == EVENT_TYPE.TOTAL:
            last_pre_query_grouped = pre_query_all_events.filter(
                *filter_args, **grouping_filter
            ).order_by("-time_created")
            last_pre_query_actual_events = (
                pre_query_all_events.annotate(
                    latest_pk=Subquery(last_pre_query_grouped.values("pk")[:1])
                )
                .filter(pk=F("latest_pk"))
                .annotate(property_value=F(f"properties__{self.property_name}"))
                .annotate(usage_qty=Cast(F("property_value"), FloatField()))
            )
        elif self.event_type == EVENT_TYPE.DELTA:
            last_pre_query_grouped = (
                pre_query_all_events.filter(*filter_args, **grouping_filter)
                .values(*[x for x in grouping_filter.keys()])
                .annotate(last_qty=Sum(Cast(F("property_value"), FloatField())))
            )
            last_pre_query_actual_events = pre_query_all_events.annotate(
                usage_qty=Subquery(last_pre_query_grouped.values("last_qty")[:1])
            )

        last_usages = {}
        for row in last_pre_query_actual_events:
            cust_name = row.customer_name
            unique_tup = tuple(getattr(row, prop) for prop in unique_groupby_props)
            usage_qty = row.usage_qty
            if cust_name not in last_usages:
                last_usages[cust_name] = {}
            if unique_tup not in last_usages[cust_name]:
                last_usages[cust_name][unique_tup] = {}
            last_usages[cust_name][unique_tup] = usage_qty
        # quantize first according to the stateful period
        truncate_to_granularity = smallest_granularity not in ["total", None]
        plan_periods = list(
            periods_bwn_twodates(
                smallest_granularity,
                start,
                end,
                truncate_to_granularity=truncate_to_granularity,
            )
        )
        now = now_utc()
        plan_periods = [x for x in plan_periods if x <= end and x <= now]
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
                    if period_usage is None:
                        period_usage = last_usage_unique
                    # add revenue and usage to the dict
                    usage_dict[customer_name][unique_customer_tuple][
                        period
                    ] = period_usage
                    # redefine what the "last" one is
                    last_usage_unique = latest_in_period_usages.get(
                        period, period_usage
                    )
        # ok we got here, but now we have a problem. Usage dicts is indexed in time periods of
        # self.granularity. However, we need to have it in units of results_granularity. We
        # have two cases: 1) results_granularity is coarser than self.granularity (eg want
        # total usage, but we have self.granularity in days. Let's just pass up the dictionary
        # and let whoever called this function handled that, don't assume. 2) self.
        # granularity is coarser than results_granularity. eg, we are charging for user-months,
        # but we want to get daily usage. In this case, since we aren't billing on this, we can
        # probably just extend that same valeu for the other days
        if smallest_granularity == results_granularity:  # day = day, total = total
            return usage_dict
        elif (
            results_granularity == USAGE_CALC_GRANULARITY.TOTAL
            and smallest_granularity != METRIC_GRANULARITY.TOTAL
        ) or (
            results_granularity == USAGE_CALC_GRANULARITY.DAILY
            and smallest_granularity
            in [
                METRIC_GRANULARITY.SECOND,
                METRIC_GRANULARITY.MINUTE,
                METRIC_GRANULARITY.HOUR,
            ]
        ):
            return usage_dict
        else:
            # this means that the metric granularity is coarser than the results_granularity
            new_usage_dict = {}
            for customer_name, cust_usages in usage_dict.items():
                cust_dict = {}
                for unique_customer_tuple, unique_usage in cust_usages.items():
                    cust_dict[unique_customer_tuple] = {}
                    coarse_periods = sorted(unique_usage.items(), key=lambda x: x[0])
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
                            cust_dict[unique_customer_tuple][cur_fine] = last_amt
                        else:
                            cust_dict[unique_customer_tuple][cur_fine] = coarse_usage
                            last_amt = coarse_usage
                            j += 1
                        i += 1
                new_usage_dict[customer_name] = cust_dict
            usage_dict = new_usage_dict
        return usage_dict

    def get_current_usage(self, subscription, group_by=[]):
        cur_usg_agg = self.usage_aggregation_type
        cur_granularity = self.granularity
        self.usage_aggregation_type = METRIC_AGGREGATION.LATEST
        self.granularity = METRIC_GRANULARITY.TOTAL
        usg = self.get_usage(
            results_granularity=USAGE_CALC_GRANULARITY.TOTAL,
            start=subscription.start_date,
            end=subscription.end_date,
            customer=subscription.customer,
            group_by=group_by,
        )
        self.usage_aggregation_type = cur_usg_agg
        self.granularity = cur_granularity

        return usg

    def get_earned_usage_per_day(
        self, start, end, customer, group_by=[], proration=None
    ):
        per_customer = self.get_usage(
            start=start,
            end=end,
            results_granularity=USAGE_CALC_GRANULARITY.TOTAL,
            customer=customer,
            group_by=group_by,
            proration=proration,
        )
        longer_than_daily = [
            METRIC_GRANULARITY.TOTAL,
            METRIC_GRANULARITY.YEAR,
            METRIC_GRANULARITY.QUARTER,
            METRIC_GRANULARITY.MONTH,
        ]
        customer_usage = per_customer.get(customer.customer_name, {})
        coalesced_usage = {}
        if self.granularity in longer_than_daily and proration in longer_than_daily:
            if self.usage_aggregation_type == METRIC_AGGREGATION.LATEST:
                for unique_customer_tuple, unique_usage in customer_usage.items():
                    coalesced_usage[unique_customer_tuple] = {}
                    for period in unique_usage:
                        period_end = period
                        if (
                            self.granularity == METRIC_GRANULARITY.MONTH
                            or proration == METRIC_GRANULARITY.MONTH
                        ):
                            period_end = period + relativedelta(months=1, days=-1)
                        elif (
                            self.granularity == METRIC_GRANULARITY.QUARTER
                            or proration == METRIC_GRANULARITY.QUARTER
                        ):
                            period_end = period + relativedelta(months=3, days=-1)
                        elif (
                            self.granularity == METRIC_GRANULARITY.YEAR
                            or proration == METRIC_GRANULARITY.YEAR
                        ):
                            period_end = period + relativedelta(years=1, days=-1)
                        else:
                            period_end = end + relativedelta(days=-1)
                        coalesced_usage[unique_customer_tuple][
                            period_end
                        ] = unique_usage[period]
            else:
                daily_per_customer = self.get_usage(
                    start=start,
                    end=end,
                    results_granularity=USAGE_CALC_GRANULARITY.TOTAL,
                    customer=customer,
                    group_by=group_by,
                    proration=METRIC_GRANULARITY.DAY,
                ).get(customer.customer_name, {})
                for unique_customer_tuple, unique_usage in customer_usage.items():
                    daily_per_unique = daily_per_customer.get(unique_customer_tuple, {})
                    coalesced_usage[unique_customer_tuple] = {}
                    last_value = 0
                    unique_usage_items = sorted(
                        unique_usage.items(), key=lambda x: x[0]
                    )
                    for i, (period, usage) in enumerate(unique_usage_items):
                        period = convert_to_date(period)
                        try:
                            less_than = convert_to_date(unique_usage_items[i + 1][0])
                        except:
                            less_than = None
                        for day, usage in daily_per_unique.items():
                            day = convert_to_date(day)
                            if day < period:
                                continue
                            if less_than:
                                if day >= less_than:
                                    break
                            if usage > last_value:
                                coalesced_usage[unique_customer_tuple][day] = (
                                    usage - last_value
                                )
                                last_value = usage
        else:
            for unique_customer_tuple, unique_usage in customer_usage.items():
                coalesced_usage[unique_customer_tuple] = {}
                for period, usage in unique_usage.items():
                    day = period.date()
                    if day not in coalesced_usage[unique_customer_tuple]:
                        coalesced_usage[unique_customer_tuple][day] = 0
                    coalesced_usage[unique_customer_tuple][day] += usage
        return coalesced_usage

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
        self.billable_metric = billable_metric
        assert (
            billable_metric.metric_type == METRIC_TYPE.RATE
        ), f"Billable metric of type {billable_metric.metric_type} can't be handled by a RateHandler."
        self.usage_aggregation_type = billable_metric.usage_aggregation_type
        self.billable_aggregation_type = billable_metric.billable_aggregation_type
        self.granularity = billable_metric.granularity
        self.numeric_filters = billable_metric.numeric_filters.all()
        self.categorical_filters = billable_metric.categorical_filters.all()
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
        if event_type:
            print("[METRIC TYPE: RATE] Event type not allowed. Making null.")
            data.pop("event_type", None)
        return data

    def _floor_dt(self, dt, delta):
        return dt - (datetime.datetime.min - dt) % delta

    def _get_current_query_start_end(self):
        now = now_utc()
        end = now
        try:
            start = now - relativedelta(**{self.granularity: 1})
        except:
            start = None
        return start, end

    def _build_filter_kwargs(self, start, end, customer, group_by=[]):
        return super()._build_filter_kwargs(start, end, customer, group_by)

    def _build_pre_groupby_annotation_kwargs(self, group_by=[]):
        return super()._build_pre_groupby_annotation_kwargs(group_by)

    def _build_groupby_kwargs(
        self, customer, results_granularity, start, group_by=[], proration=None
    ):
        return super()._build_groupby_kwargs(
            customer, results_granularity, start, group_by, proration
        )

    def get_current_usage(self, subscription, group_by=[]):
        start, end = self._get_current_query_start_end()
        start = start if start else subscription.start_date
        filter_args, filter_kwargs = self._build_filter_kwargs(
            start, end, subscription.customer, group_by
        )
        filter_kwargs["time_created__gt"] = subscription.start_date
        pre_groupby_annotation_kwargs = self._build_pre_groupby_annotation_kwargs(
            group_by
        )
        groupby_kwargs = self._build_groupby_kwargs(
            subscription.customer,
            results_granularity=None,
            start=start,
            group_by=group_by,
        )
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

        q_filt = Event.objects.filter(*filter_args, **filter_kwargs)
        q_pre_gb_ann = q_filt.annotate(**pre_groupby_annotation_kwargs)
        q_gb = q_pre_gb_ann.values(*filter_args, **groupby_kwargs)
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

    def get_usage(
        self,
        results_granularity,
        start,
        end,
        customer=None,
        group_by=[],
        proration=None,
    ):
        filter_args, filter_kwargs = self._build_filter_kwargs(
            start, end, customer, group_by
        )
        pre_groupby_annotation_kwargs = self._build_pre_groupby_annotation_kwargs(
            group_by
        )
        groupby_kwargs = self._build_groupby_kwargs(
            customer, results_granularity, start, group_by
        )

        q_filt = Event.objects.filter(*filter_args, **filter_kwargs)
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

    def get_earned_usage_per_day(
        self, start, end, customer, group_by=[], proration=None
    ):
        per_customer = self.get_usage(
            start=start,
            end=end,
            granularity=USAGE_CALC_GRANULARITY.DAILY,
            customer=customer,
            group_by=group_by,
            proration=proration,
        )

        return_dict = {}
        unique_groupby_props = ["customer_name"] + group_by
        for row in per_customer:
            tc_trunc = row["time_created_truncated"]
            unique_tup = tuple(row[prop] for prop in unique_groupby_props)
            usage_qty = row["new_usage_qty"]
            if unique_tup not in return_dict:
                return_dict[unique_tup] = {}
            if max(return_dict[unique_tup].values(), default=0) < usage_qty:
                return_dict[unique_tup] = {tc_trunc: usage_qty}

        return return_dict

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
