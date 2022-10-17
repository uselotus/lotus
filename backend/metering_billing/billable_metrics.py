import abc
import datetime
from typing import Optional

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
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Cast, Trunc
from metering_billing.models import BillableMetric, Customer, Event
from metering_billing.utils import (
    METRIC_AGGREGATION,
    METRIC_TYPE,
    REVENUE_CALC_GRANULARITY,
    periods_bwn_twodates,
)
from rest_framework import serializers, status


class BillableMetricHandler(abc.ABC):
    @abc.abstractmethod
    def __init__(self, billable_metric: BillableMetric):
        """This method will be called whenever we need to work with a billable metric, whether that's determining usage, or calculating revenue, or generating a bill. You might want to extract the fields you want to work with in the metric and make them instance variables."""
        pass

    @abc.abstractmethod
    def get_usage(
        self,
        granularity: REVENUE_CALC_GRANULARITY,
        start_date: datetime.date,
        end_date: datetime.date,
        customer: Optional[Customer],
        billable_only: bool,
    ) -> dict[Customer.name, dict[datetime.datetime, float]]:
        """This method will be used to calculate the usage at the given granularity. This is purely how much has been used and will typically be used in dahsboarding to show usage of the metric. You should be able to handle any aggregation type returned in the allowed_aggregation_types method.

        Customer can either be a customer object or None. If it is None, then you should return the per-customer usage. If it is a customer object, then you should return the usage for that customer.

        You should return a dictionary of datetime to usage, where the datetime is the start of the time period "granularity". For example, if we have an hourly granularity from May 1st to May 7th, you should return a dictionary with a maximum of 168 entries (7 days * 24 hours), one for each hour (May 1st 12:00AM, May 1st 1:00 AM, etc.), with the key being the start of the hour and the value being the usage for that hour. If there is no usage for that hour, then it is optional to include it in the dictionary.

        Keep an eye out for the billable_only parameter. If it is True, then you should only return usage that is billable. Though in some cases the usage is the same as the billable usage, there are cases where this is not the case. For example, if your billable metric is a UNIQUE aggregation over the property product_users, then your usage per day will be the number of unique product_users in that day. However, your billable usage will depend on when you first saw each product_user. You'd have a usage of 1 for each new product_user you saw, and attribute it to the day you first saw them.
        """
        pass

    @staticmethod
    @abc.abstractmethod
    def allowed_aggregation_types() -> list[METRIC_AGGREGATION]:
        """This method will be called to determine what aggregation types are allowed for this billable metric."""
        pass

    @staticmethod
    @abc.abstractmethod
    def validate_properties(properties) -> dict:
        """We will use this method when validating post requests to create a billable metric. You should validate the properties of the billable metric and return the proeprties dict (altered if you want to). This will then be inserted directly into the properties of the created billable metric."""
        pass


class AggregationHandler(BillableMetricHandler):
    def __init__(self, billable_metric: BillableMetric):
        self.event_name = billable_metric.event_name
        self.aggregation_type = billable_metric.aggregation_type
        self.property_name = (
            None
            if self.aggregation_type == METRIC_AGGREGATION.COUNT
            or billable_metric.property_name == ""
            else billable_metric.property_name
        )
        self.numeric_filters = billable_metric.numeric_filters
        self.categorical_filters = billable_metric.categorical_filters
        self.organization = billable_metric.organization

        assert (
            billable_metric.metric_type == METRIC_TYPE.AGGREGATION
        ), f"Billable metric of type {billable_metric.metric_type} can't be handled by an AggregationHandler."
        assert (
            self.aggregation_type in self.allowed_aggregation_types()
        ), f"Aggregation type {self.aggregation_type} is not allowed for this billable metric handler."

    def get_usage(
        self, granularity, start_date, end_date, customer=None, billable_only=False
    ):
        now = datetime.datetime.now(datetime.timezone.utc)
        filter_kwargs = {
            "organization": self.organization,
            "event_name": self.event_name,
            "time_created__lt": now,
            "time_created__date__gte": start_date,
            "time_created__date__lte": end_date,
        }
        pre_groupby_annotation_kwargs = {}
        groupby_kwargs = {"customer_name": F("customer__name")}
        post_groupby_annotation_kwargs = {}
        if customer:
            filter_kwargs["customer"] = customer
        if self.property_name is not None:
            filter_kwargs["properties__has_key"] = self.property_name
            pre_groupby_annotation_kwargs["property_value"] = F(
                f"properties__{self.property_name}"
            )
        if granularity != REVENUE_CALC_GRANULARITY.TOTAL:
            groupby_kwargs["time_created_truncated"] = Trunc(
                expression=F("time_created"),
                kind=granularity.value,
                output_field=DateTimeField(),
            )
        else:
            groupby_kwargs["time_created_truncated"] = Value(
                datetime.datetime.combine(
                    start_date, datetime.time.min, tzinfo=datetime.timezone.utc
                )
            )

        if self.aggregation_type == METRIC_AGGREGATION.COUNT:
            post_groupby_annotation_kwargs["usage_qty"] = Count("pk")
        elif self.aggregation_type == METRIC_AGGREGATION.SUM:
            post_groupby_annotation_kwargs["usage_qty"] = Sum(
                Cast(F("property_value"), FloatField())
            )
        elif self.aggregation_type == METRIC_AGGREGATION.AVERAGE:
            post_groupby_annotation_kwargs["usage_qty"] = Avg(
                Cast(F("property_value"), FloatField())
            )
        elif self.aggregation_type == METRIC_AGGREGATION.MIN:
            if billable_only:
                # if its billable only, then we need to find the min event over the whole
                # time period, and then use that as the billable usage... if we aggregate using
                # min, then we'll get the min event for each period in granularity, which is not
                # what we want... lets remove the groupby, and simply annotate
                post_groupby_annotation_kwargs = groupby_kwargs
                groupby_kwargs = {}
                post_groupby_annotation_kwargs["usage_qty"] = Cast(
                    F("property_value"), FloatField()
                )
            else:
                post_groupby_annotation_kwargs["usage_qty"] = Min(
                    Cast(F("property_value"), FloatField())
                )
        elif self.aggregation_type == METRIC_AGGREGATION.MAX:
            if billable_only:
                # if its billable only, then we need to find the max event over the whole
                # time period, and then use that as the billable usage... if we aggregate using
                # max, then we'll get the max event for each period in granularity, which is not
                # what we want
                post_groupby_annotation_kwargs = groupby_kwargs
                groupby_kwargs = {}
                post_groupby_annotation_kwargs["usage_qty"] = Cast(
                    F("property_value"), FloatField()
                )
            else:
                post_groupby_annotation_kwargs["usage_qty"] = Max(
                    Cast(F("property_value"), FloatField())
                )
        elif self.aggregation_type == METRIC_AGGREGATION.UNIQUE:
            if billable_only:
                # for unique, we need to find the first time we saw each unique property value. If
                # we just aggregate using count unique, then we'll get the unique per period of
                # granularity, which is not what we want.
                post_groupby_annotation_kwargs = groupby_kwargs
                groupby_kwargs = {}
            post_groupby_annotation_kwargs["usage_qty"] = Count(
                F("property_value"), distinct=True
            )
        elif self.aggregation_type == METRIC_AGGREGATION.LATEST:
            post_groupby_annotation_kwargs = groupby_kwargs
            groupby_kwargs = {}
            post_groupby_annotation_kwargs["usage_qty"] = Cast(
                F("property_value"), FloatField()
            )

        q_filt = Event.objects.filter(**filter_kwargs)
        q_pre_gb_ann = q_filt.annotate(**pre_groupby_annotation_kwargs)
        q_gb = q_pre_gb_ann.values(**groupby_kwargs)
        q_post_gb_ann = q_gb.annotate(**post_groupby_annotation_kwargs)

        if self.aggregation_type == METRIC_AGGREGATION.LATEST:
            latest_filt = {
                "customer_name": OuterRef("customer_name"),
            }
            if not billable_only:
                # if its not billable only, then we need to match the time truncated too
                latest_filt["time_created_truncated"] = OuterRef(
                    "time_created_truncated"
                )
            latest = q_post_gb_ann.filter(**latest_filt).order_by("-time_created")
            q_post_gb_ann = q_post_gb_ann.annotate(
                latest_pk=Subquery(latest.values("pk")[:1])
            ).filter(pk=F("latest_pk"))
        elif self.aggregation_type == METRIC_AGGREGATION.MAX and billable_only:
            max = q_post_gb_ann.filter(
                customer_name=OuterRef("customer_name")
            ).order_by("-usage_qty")
            q_post_gb_ann = q_post_gb_ann.annotate(
                max_pk=Subquery(max.values("pk")[:1])
            ).filter(pk=F("max_pk"))
        elif self.aggregation_type == METRIC_AGGREGATION.MIN and billable_only:
            min = q_post_gb_ann.filter(
                customer_name=OuterRef("customer_name")
            ).order_by("usage_qty")
            q_post_gb_ann = q_post_gb_ann.annotate(
                min_pk=Subquery(min.values("pk")[:1])
            ).filter(pk=F("min_pk"))
        elif self.aggregation_type == METRIC_AGGREGATION.UNIQUE and billable_only:
            q_post_gb_ann = q_post_gb_ann.filter(
                ~Exists(
                    q_post_gb_ann.filter(
                        time_created__lt=OuterRef("time_created"),
                        customer_name=OuterRef("customer_name"),
                        property_value=OuterRef("property_value"),
                    )
                )
            )
            q_post_gb_ann = q_post_gb_ann.values(
                "customer_name",
                "time_created_truncated",
            ).annotate(usage_qty=Count("pk"))

        return_dict = {}
        for row in q_post_gb_ann:
            cust_name = row["customer_name"]
            tc_trunc = row["time_created_truncated"]
            usage_qty = row["usage_qty"]
            if cust_name not in return_dict:
                return_dict[cust_name] = {}
            return_dict[cust_name][tc_trunc] = usage_qty
        return return_dict

    @staticmethod
    def allowed_aggregation_types():
        return [
            METRIC_AGGREGATION.UNIQUE,
            METRIC_AGGREGATION.SUM,
            METRIC_AGGREGATION.COUNT,
            METRIC_AGGREGATION.AVERAGE,
            METRIC_AGGREGATION.MIN,
            METRIC_AGGREGATION.MAX,
            METRIC_AGGREGATION.LATEST,
        ]

    @staticmethod
    def validate_properties(properties) -> dict:
        if type(properties) != dict:
            raise ValueError("properties must be a dict")
        else:
            return properties


class StatefulHandler(BillableMetricHandler):
    """
    The key difference between a stateful handler and an aggregation handler is that the stateful handler has state across time periods. Even when given a blocked off time period, it'll look for previous values of the event/property in question and use those as a starting point. A common example of a metric that woudl fit under the Stateful pattern would be the number of seats a product has available. When we go into a new billing period, the number of seats doesn't magically disappear... we have to keep track of it. We currently support two types of events: quantity_logging and delta_logging. Quantity logging would look like sending events to the API that say we have x users at the moment. Delta logging would be like sending events that say we added x users or removed x users. The stateful handler will look at the previous value of the metric and add/subtract the delta to get the new value.
    """

    def __init__(self, billable_metric: BillableMetric):
        self.event_name = billable_metric.event_name
        self.aggregation_type = billable_metric.aggregation_type
        self.property_name = billable_metric.property_name
        self.numeric_filters = billable_metric.numeric_filters
        self.categorical_filters = billable_metric.categorical_filters
        self.organization = billable_metric.organization
        self.initial_value = billable_metric.properties.get("initial_value", 0)

        assert (
            billable_metric.metric_type == METRIC_TYPE.STATEFUL
        ), f"Billable metric of type {billable_metric.metric_type} can't be handled by an AggregationHandler."
        assert (
            self.aggregation_type in self.allowed_aggregation_types()
        ), f"Aggregation type {self.aggregation_type} is not allowed for this billable metric handler."
        assert (
            self.property_name != ""
        ), "Property name must be set for a stateful billable metric."

    def get_usage(
        self, granularity, start_date, end_date, customer=None, billable_only=False
    ):
        # quick note on billable only. Since the stateful keeps track of some udnerlying state,
        # then billable only doesn't make sense since all the usage is billable (there's always) an
        # underlying state. So we'll just ignore it.
        now = datetime.datetime.now(datetime.timezone.utc)
        filter_kwargs = {
            "organization": self.organization,
            "event_name": self.event_name,
            "time_created__lt": now,
            "time_created__date__gte": start_date,
            "time_created__date__lte": end_date,
        }
        pre_groupby_annotation_kwargs = {}
        groupby_kwargs = {"customer_name": F("customer__name")}
        post_groupby_annotation_kwargs = {}
        if customer:
            filter_kwargs["customer"] = customer
        if self.property_name is not None:
            filter_kwargs["properties__has_key"] = self.property_name
            pre_groupby_annotation_kwargs["property_value"] = F(
                f"properties__{self.property_name}"
            )
        if granularity != REVENUE_CALC_GRANULARITY.TOTAL:
            groupby_kwargs["time_created_truncated"] = Trunc(
                expression=F("time_created"),
                kind=granularity.value,
                output_field=DateTimeField(),
            )
        else:
            groupby_kwargs["time_created_truncated"] = Value(
                datetime.datetime.combine(
                    start_date, datetime.time.min, tzinfo=datetime.timezone.utc
                )
            )

        if self.aggregation_type == METRIC_AGGREGATION.MIN:
            post_groupby_annotation_kwargs["usage_qty"] = Min(
                Cast(F("property_value"), FloatField())
            )
        elif self.aggregation_type == METRIC_AGGREGATION.MAX:
            post_groupby_annotation_kwargs["usage_qty"] = Max(
                Cast(F("property_value"), FloatField())
            )
        elif self.aggregation_type == METRIC_AGGREGATION.LATEST:
            post_groupby_annotation_kwargs = groupby_kwargs
            groupby_kwargs = {}
            post_groupby_annotation_kwargs["usage_qty"] = Cast(
                F("property_value"), FloatField()
            )

        q_filt = Event.objects.filter(**filter_kwargs)
        q_pre_gb_ann = q_filt.annotate(**pre_groupby_annotation_kwargs)
        q_gb = q_pre_gb_ann.values(**groupby_kwargs)
        q_post_gb_ann = q_gb.annotate(**post_groupby_annotation_kwargs)

        period_usages = {}
        for x in q_post_gb_ann:
            cust = x["customer_name"]
            tc_trunc = x["time_created_truncated"]
            usage_qty = x["usage_qty"]
            if cust not in period_usages:
                period_usages[cust] = {}
            period_usages[cust][tc_trunc] = usage_qty

        # grab latest value from previous period per customer
        latest_filt = {
            "customer_name": OuterRef("customer_name"),
            "time_created_truncated": OuterRef("time_created_truncated"),
        }
        latest = q_post_gb_ann.filter(**latest_filt).order_by("-time_created")
        latest_per_period = q_post_gb_ann.annotate(
            latest_pk=Subquery(latest.values("pk")[:1])
        ).filter(pk=F("latest_pk"))
        latest_in_period_usages = {}
        for x in latest_per_period:
            cust = x["customer_name"]
            tc_trunc = x["time_created_truncated"]
            usage_qty = x["usage_qty"]
            if cust not in latest_in_period_usages:
                latest_in_period_usages[cust] = {}
            latest_in_period_usages[cust][tc_trunc] = usage_qty

        # grab pre-query initial values
        last_usage = (
            Event.objects.filter(
                organization=self.organization,
                event_name=self.event_name,
                time_created__date__lt=start_date,
                customer=customer,
                properties__has_key=self.property_name,
            )
            .annotate(customer_name=F("customer__name"))
            .order_by("customer_name", "-time_created")
            .distinct("customer_name")
            .annotate(property_value=F(f"properties__{self.property_name}"))
            .annotate(usage_qty=Cast(F("property_value"), FloatField()))
        )
        last_usages = {}
        for x in last_usage:
            cust = x.customer_name
            usage_qty = x.usage_qty
            last_usages[cust] = usage_qty

        # quantize first according to the stateful period
        plan_periods = list(periods_bwn_twodates(granularity, start_date, end_date))
        # for each period, get the events and calculate the usage and revenue
        usage_dict = {}
        for customer_name, cust_usages in period_usages.items():
            last_usage = last_usages.get(customer_name, self.initial_value)
            customer_latest_in_period_usages = latest_in_period_usages.get(
                customer_name, {}
            )
            usage_dict[customer_name] = {}
            for period in plan_periods:
                # check the usage for that period
                period_usage = cust_usages.get(period, None)
                # if its none, then we'll use the last usage
                if not period_usage:
                    period_usage = last_usage
                # add revenue and usage to the dict
                usage_dict[customer_name][period] = period_usage
                # redefine what the "last" one is
                latest_in_period = customer_latest_in_period_usages.get(period, None)
                if latest_in_period:
                    last_usage = latest_in_period
                else:
                    last_usage = period_usage
        return usage_dict

    @staticmethod
    def allowed_aggregation_types():
        return [
            METRIC_AGGREGATION.MIN,
            METRIC_AGGREGATION.MAX,
            METRIC_AGGREGATION.LATEST,
        ]

    @staticmethod
    def validate_properties(properties) -> dict:
        assert isinstance(properties, dict), "properties must be a dict"
        if "initial_value" not in properties:
            properties["initial_value"] = 0
        assert isinstance(
            properties["initial_value"], (int, float)
        ), "initial_value must be a number"
        return properties


METRIC_HANDLER_MAP = {
    METRIC_TYPE.AGGREGATION: AggregationHandler,
    METRIC_TYPE.STATEFUL: StatefulHandler,
}
