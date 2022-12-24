import itertools
import json
import unittest.mock as mock
from collections import namedtuple
from datetime import timedelta
from decimal import Decimal

import pytest
from dateutil import parser
from dateutil.relativedelta import relativedelta
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection
from django.urls import reverse
from jinja2 import Template
from metering_billing.models import (
    CategoricalFilter,
    Customer,
    Event,
    Metric,
    NumericFilter,
    PlanComponent,
    PlanVersion,
    PriceTier,
    SubscriptionRecord,
    User,
)
from metering_billing.utils import now_utc
from metering_billing.utils.enums import (
    CATEGORICAL_FILTER_OPERATORS,
    EVENT_TYPE,
    METRIC_AGGREGATION,
    METRIC_GRANULARITY,
    METRIC_STATUS,
    METRIC_TYPE,
    NUMERIC_FILTER_OPERATORS,
    PLAN_DURATION,
    PLAN_STATUS,
    PLAN_VERSION_STATUS,
    PRICE_TIER_TYPE,
    USAGE_CALC_GRANULARITY,
)
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APIClient


def namedtuplefetchall(cursor):
    "Return all rows from a cursor as a namedtuple"
    desc = cursor.description
    nt_result = namedtuple("Result", [col[0] for col in desc])
    return [nt_result(*row) for row in cursor.fetchall()]


@pytest.fixture
def billable_metric_test_common_setup(
    generate_org_and_api_key,
    add_billable_metrics_to_org,
    add_users_to_org,
    api_client_with_api_key_auth,
    add_product_to_org,
    add_plan_to_product,
):
    def do_billable_metric_test_common_setup(
        *, num_billable_metrics, auth_method, user_org_and_api_key_org_different
    ):
        # set up organizations and api keys
        org, key = generate_org_and_api_key()
        org2, key2 = generate_org_and_api_key()
        setup_dict = {
            "org": org,
            "key": key,
            "org2": org2,
            "key2": key2,
        }
        # set up the client with the appropriate api key spec
        if auth_method == "api_key":
            client = api_client_with_api_key_auth(key)
        elif auth_method == "session_auth":
            client = APIClient()
            (user,) = add_users_to_org(org, n=1)
            client.force_authenticate(user=user)
            setup_dict["user"] = user
        else:
            client = api_client_with_api_key_auth(key)
            if user_org_and_api_key_org_different:
                (user,) = add_users_to_org(org2, n=1)
            else:
                (user,) = add_users_to_org(org, n=1)
            client.force_authenticate(user=user)
            setup_dict["user"] = user
        setup_dict["client"] = client

        # set up billable_metrics
        if num_billable_metrics > 0:
            setup_dict["org_billable_metrics"] = add_billable_metrics_to_org(
                org, n=num_billable_metrics
            )
            setup_dict["org2_billable_metrics"] = add_billable_metrics_to_org(
                org2, n=num_billable_metrics
            )
        product = add_product_to_org(org)
        plan = add_plan_to_product(product)
        setup_dict["plan"] = plan
        return setup_dict

    return do_billable_metric_test_common_setup


@pytest.mark.django_db(transaction=True)
class TestCalculateMetric:
    def test_raw_sql_rate_hourly_granularity(
        self, billable_metric_test_common_setup, add_subscription_to_org
    ):
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )
        billable_metric = Metric.objects.create(
            organization=setup_dict["org"],
            event_name="rows_inserted",
            property_name="num_rows",
            usage_aggregation_type=METRIC_AGGREGATION.SUM,
            billable_aggregation_type=METRIC_AGGREGATION.MAX,
            metric_type=METRIC_TYPE.RATE,
            granularity=METRIC_GRANULARITY.DAY,
        )
        time_created = now_utc() - relativedelta(days=14, hour=0)
        customer = baker.make(
            Customer, organization=setup_dict["org"], customer_name="foo"
        )
        # 64 in an hour, 14 days ago
        event_times = [time_created] + [
            time_created + relativedelta(minutes=i) for i in range(1, 19)
        ]
        for groupby_dim_1 in ["foo", "bar"]:
            for groupby_dimension_2 in ["baz", "qux"]:
                for groupby_dimension_3 in ["quux", "quuz"]:
                    properties = (
                        4
                        * [
                            {
                                "num_rows": 1,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                        + 3
                        * [
                            {
                                "num_rows": 2,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                        + 3
                        * [
                            {
                                "num_rows": 3,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                        + 3
                        * [
                            {
                                "num_rows": 4,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                        + 3
                        * [
                            {
                                "num_rows": 5,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                        + 3
                        * [
                            {
                                "num_rows": 6,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                    )  # = 64
                    baker.make(
                        Event,
                        event_name="rows_inserted",
                        properties=iter(properties),
                        organization=setup_dict["org"],
                        time_created=iter(event_times),
                        customer=customer,
                        _quantity=19,
                    )
        # 60 in an hour, 5 days ago
        time_created = now_utc() - relativedelta(days=5, hour=0)
        event_times = [time_created] + [
            time_created + relativedelta(minutes=i) for i in range(1, 19)
        ]
        for groupby_dim_1 in ["foo", "bar"]:
            for groupby_dimension_2 in ["baz", "qux"]:
                for groupby_dimension_3 in ["quux", "quuz"]:
                    properties = (
                        4
                        * [
                            {
                                "num_rows": 1,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                        + 3
                        * [
                            {
                                "num_rows": 2,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                        + 3
                        * [
                            {
                                "num_rows": 3,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                        + 2
                        * [
                            {
                                "num_rows": 4,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                        + 3
                        * [
                            {
                                "num_rows": 5,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                        + 3
                        * [
                            {
                                "num_rows": 6,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                    )  # = 64
                    baker.make(
                        Event,
                        event_name="rows_inserted",
                        properties=list(properties),
                        organization=setup_dict["org"],
                        time_created=iter(event_times),
                        customer=customer,
                        _quantity=19,
                    )
        billing_plan = PlanVersion.objects.create(
            organization=setup_dict["org"],
            flat_rate=0,
            version=1,
            plan=setup_dict["plan"],
        )
        plan_component = PlanComponent.objects.create(
            billable_metric=billable_metric,
            plan_version=billing_plan,
        )
        free_tier = PriceTier.objects.create(
            plan_component=plan_component,
            type=PRICE_TIER_TYPE.FREE,
            range_start=0,
            range_end=3,
        )
        paid_tier = PriceTier.objects.create(
            plan_component=plan_component,
            type=PRICE_TIER_TYPE.PER_UNIT,
            range_start=3,
            cost_per_batch=1,
            metric_units_per_batch=1,
        )
        now = now_utc()
        with (
            mock.patch(
                "metering_billing.models.now_utc",
                return_value=now - relativedelta(days=31),
            ),
            mock.patch(
                "metering_billing.tests.test_billable_metric.now_utc",
                return_value=now - relativedelta(days=31),
            ),
        ):
            subscription, subscription_record = add_subscription_to_org(
                setup_dict["org"],
                billing_plan,
                customer,
                now - relativedelta(days=31),
            )
        from metering_billing.aggregation.rate_query_templates import (
            RATE_GET_CURRENT_USAGE,
            RATE_USAGE_PER_DAY,
        )

        data = {
            "customer_id": customer.pk,
            "event_name": "rows_inserted",
            "organization_id": setup_dict["org"].pk,
            "current_time": now_utc(),
            "start_time": now_utc() - relativedelta(months=2),
            "end_time": now_utc(),
            "group_by": ["groupby_dim_1", "groupby_dim_2", "groupby_dim_3"],
            "filter_properties": {
                "groupby_dim_1": ["foo", "bar"],
                "groupby_dim_2": ["baz"],
                "groupby_dim_3": ["quux"],
            },
            "query_type": METRIC_AGGREGATION.SUM,
            "property_name": "num_rows",
            "lookback_qty": 15,
            "lookback_units": "day",
        }
        query = Template(RATE_GET_CURRENT_USAGE).render(**data)
        with connection.cursor() as cursor:
            cursor.execute(query)
            results = namedtuplefetchall(cursor)
        assert len(results) == 2
        assert results[0].usage_qty == 64
        assert results[1].usage_qty == 64

        data["lookback_qty"] = 1
        query = Template(RATE_GET_CURRENT_USAGE).render(**data)
        with connection.cursor() as cursor:
            cursor.execute(query)
            results = namedtuplefetchall(cursor)
        assert len(results) == 0

    def test_raw_sql_stateful_current_usage_delta(
        self, billable_metric_test_common_setup, add_subscription_to_org
    ):
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )
        billable_metric = Metric.objects.create(
            organization=setup_dict["org"],
            event_name="number_of_users",
            property_name="number",
            usage_aggregation_type=METRIC_AGGREGATION.MAX,
            metric_type=METRIC_TYPE.STATEFUL,
            granularity=METRIC_GRANULARITY.MONTH,
            event_type=EVENT_TYPE.DELTA,
        )
        time_created = now_utc() - relativedelta(days=45)
        customer = baker.make(
            Customer, organization=setup_dict["org"], customer_name="test"
        )
        event_times = [time_created + relativedelta(days=i) for i in range(8)]
        for groupby_dim_1 in ["foo", "bar"]:
            for groupby_dimension_2 in ["baz", "qux"]:
                for groupby_dimension_3 in ["quux", "quuz"]:
                    properties = (
                        1
                        * [
                            {
                                "number": 3,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                        + 3
                        * [
                            {
                                "number": 1,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                        + 1
                        * [
                            {
                                "number": 0,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                        + 3
                        * [
                            {
                                "number": -1,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                    )
                    baker.make(
                        Event,
                        event_name="number_of_users",
                        properties=iter(properties),
                        organization=setup_dict["org"],
                        time_created=iter(event_times),
                        customer=customer,
                        _quantity=8,
                    )
        billing_plan = PlanVersion.objects.create(
            organization=setup_dict["org"],
            flat_rate=0,
            version=1,
            plan=setup_dict["plan"],
        )
        plan_component = PlanComponent.objects.create(
            billable_metric=billable_metric,
            plan_version=billing_plan,
            separate_by=["groupby_dim_1", "groupby_dim_2", "groupby_dim_3"],
            proration_granularity=METRIC_GRANULARITY.DAY,
        )
        free_tier = PriceTier.objects.create(
            plan_component=plan_component,
            type=PRICE_TIER_TYPE.FREE,
            range_start=0,
            range_end=3,
        )
        paid_tier = PriceTier.objects.create(
            plan_component=plan_component,
            type=PRICE_TIER_TYPE.PER_UNIT,
            range_start=3,
            cost_per_batch=100,
            metric_units_per_batch=1,
        )
        with (
            mock.patch("metering_billing.models.now_utc", return_value=time_created),
            mock.patch(
                "metering_billing.tests.test_billable_metric.now_utc",
                return_value=time_created,
            ),
        ):
            subscription, subscription_record = add_subscription_to_org(
                setup_dict["org"], billing_plan, customer, time_created
            )
        from metering_billing.aggregation.stateful_query_templates import (
            STATEFUL_GET_CURRENT_USAGE_DELTA,
        )

        data = {
            "customer_id": customer.pk,
            "event_name": "number_of_users",
            "organization_id": setup_dict["org"].pk,
            "current_time": now_utc(),
            "start_time": now_utc() - relativedelta(months=2),
            "end_time": now_utc(),
            "group_by": ["groupby_dim_1", "groupby_dim_2", "groupby_dim_3"],
            "filter_properties": {
                "groupby_dim_1": ["foo", "bar"],
                "groupby_dim_2": ["baz"],
                "groupby_dim_3": ["quux"],
            },
            "query_type": METRIC_AGGREGATION.SUM,
            "property_name": "number",
            "event_type": EVENT_TYPE.DELTA,
        }
        query = Template(STATEFUL_GET_CURRENT_USAGE_DELTA).render(**data)
        with connection.cursor() as cursor:
            cursor.execute(query)
            results = namedtuplefetchall(cursor)
        assert len(results) == 2
        assert results[0].usage_qty == 3
        assert results[1].usage_qty == 3

    def test_raw_sql_stateful_current_usage_total(
        self, billable_metric_test_common_setup, add_subscription_to_org
    ):
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )
        billable_metric = Metric.objects.create(
            organization=setup_dict["org"],
            event_name="number_of_users",
            property_name="number",
            usage_aggregation_type=METRIC_AGGREGATION.MAX,
            metric_type=METRIC_TYPE.STATEFUL,
            granularity=METRIC_GRANULARITY.MONTH,
        )
        time_created = now_utc() - relativedelta(days=45)
        customer = baker.make(
            Customer, organization=setup_dict["org"], customer_name="test"
        )
        event_times = [time_created] + [
            time_created + relativedelta(days=i) for i in range(1, 19)
        ]
        for groupby_dim_1 in ["foo", "bar"]:
            for groupby_dimension_2 in ["baz", "qux"]:
                for groupby_dimension_3 in ["quux", "quuz"]:
                    properties = (
                        3
                        * [
                            {
                                "number": 3,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                        + 3
                        * [
                            {
                                "number": 3,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                        + 3
                        * [
                            {
                                "number": 3,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                        + 3
                        * [
                            {
                                "number": 4,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                        + 3
                        * [
                            {
                                "number": 5,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                        + 3
                        * [
                            {
                                "number": 6,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                        + [
                            {
                                "number": 3,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                    )
                    baker.make(
                        Event,
                        event_name="number_of_users",
                        properties=iter(properties),
                        organization=setup_dict["org"],
                        time_created=iter(event_times),
                        customer=customer,
                        _quantity=19,
                    )
        billing_plan = PlanVersion.objects.create(
            organization=setup_dict["org"],
            flat_rate=0,
            version=1,
            plan=setup_dict["plan"],
        )
        plan_component = PlanComponent.objects.create(
            billable_metric=billable_metric,
            plan_version=billing_plan,
            separate_by=["groupby_dim_1", "groupby_dim_2", "groupby_dim_3"],
            proration_granularity=METRIC_GRANULARITY.DAY,
        )
        free_tier = PriceTier.objects.create(
            plan_component=plan_component,
            type=PRICE_TIER_TYPE.FREE,
            range_start=0,
            range_end=3,
        )
        paid_tier = PriceTier.objects.create(
            plan_component=plan_component,
            type=PRICE_TIER_TYPE.PER_UNIT,
            range_start=3,
            cost_per_batch=100,
            metric_units_per_batch=1,
        )
        with (
            mock.patch("metering_billing.models.now_utc", return_value=time_created),
            mock.patch(
                "metering_billing.tests.test_billable_metric.now_utc",
                return_value=time_created,
            ),
        ):
            subscription, subscription_record = add_subscription_to_org(
                setup_dict["org"], billing_plan, customer, time_created
            )
        from metering_billing.aggregation.stateful_query_templates import (
            STATEFUL_GET_CURRENT_USAGE_TOTAL,
        )

        data = {
            "customer_id": customer.pk,
            "event_name": "number_of_users",
            "organization_id": setup_dict["org"].pk,
            "current_time": now_utc(),
            "start_time": now_utc() - relativedelta(months=2),
            "end_time": now_utc(),
            "group_by": ["groupby_dim_1", "groupby_dim_2", "groupby_dim_3"],
            "filter_properties": {
                "groupby_dim_1": ["foo", "bar"],
                "groupby_dim_2": ["baz"],
                "groupby_dim_3": ["quux"],
            },
            "query_type": METRIC_AGGREGATION.SUM,
            "property_name": "number",
            "event_type": EVENT_TYPE.DELTA,
        }
        query = Template(STATEFUL_GET_CURRENT_USAGE_TOTAL).render(**data)
        with connection.cursor() as cursor:
            cursor.execute(query)
            results = namedtuplefetchall(cursor)
        assert len(results) == 2
        assert results[0].usage_qty == 3
        assert results[1].usage_qty == 3

    def test_raw_sql_stateful_toal_usage_total(
        self, billable_metric_test_common_setup, add_subscription_to_org
    ):
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )
        billable_metric = Metric.objects.create(
            organization=setup_dict["org"],
            event_name="number_of_users",
            property_name="number",
            usage_aggregation_type=METRIC_AGGREGATION.MAX,
            metric_type=METRIC_TYPE.STATEFUL,
            granularity=METRIC_GRANULARITY.MONTH,
        )
        time_created = now_utc() - relativedelta(days=45)
        customer = baker.make(
            Customer, organization=setup_dict["org"], customer_name="test"
        )
        event_times = [time_created] + [
            time_created + relativedelta(days=i) for i in range(1, 19)
        ]
        for groupby_dim_1 in ["foo", "bar"]:
            for groupby_dimension_2 in ["baz", "qux"]:
                for groupby_dimension_3 in ["quux", "quuz"]:
                    properties = (
                        3
                        * [
                            {
                                "number": 3,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                        + 3
                        * [
                            {
                                "number": 3,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                        + 3
                        * [
                            {
                                "number": 3,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                        + 3
                        * [
                            {
                                "number": 4,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                        + 3
                        * [
                            {
                                "number": 5,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                        + 3
                        * [
                            {
                                "number": 6,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                        + [
                            {
                                "number": 3,
                                "groupby_dim_1": groupby_dim_1,
                                "groupby_dim_2": groupby_dimension_2,
                                "groupby_dim_3": groupby_dimension_3,
                            }
                        ]
                    )
                    baker.make(
                        Event,
                        event_name="number_of_users",
                        properties=iter(properties),
                        organization=setup_dict["org"],
                        time_created=iter(event_times),
                        customer=customer,
                        _quantity=19,
                    )
        billing_plan = PlanVersion.objects.create(
            organization=setup_dict["org"],
            flat_rate=0,
            version=1,
            plan=setup_dict["plan"],
        )
        plan_component = PlanComponent.objects.create(
            billable_metric=billable_metric,
            plan_version=billing_plan,
            separate_by=["groupby_dim_1", "groupby_dim_2", "groupby_dim_3"],
            proration_granularity=METRIC_GRANULARITY.DAY,
        )
        free_tier = PriceTier.objects.create(
            plan_component=plan_component,
            type=PRICE_TIER_TYPE.FREE,
            range_start=0,
            range_end=3,
        )
        paid_tier = PriceTier.objects.create(
            plan_component=plan_component,
            type=PRICE_TIER_TYPE.PER_UNIT,
            range_start=3,
            cost_per_batch=100,
            metric_units_per_batch=1,
        )
        with (
            mock.patch("metering_billing.models.now_utc", return_value=time_created),
            mock.patch(
                "metering_billing.tests.test_billable_metric.now_utc",
                return_value=time_created,
            ),
        ):
            subscription, subscription_record = add_subscription_to_org(
                setup_dict["org"], billing_plan, customer, time_created
            )
        from metering_billing.aggregation.stateful_query_templates import (
            STATEFUL_GET_USAGE_WITH_GRANULARITY,
        )

        data = {
            "customer_id": customer.pk,
            "event_name": "number_of_users",
            "organization_id": setup_dict["org"].pk,
            "current_time": now_utc(),
            "start_time": now_utc() - relativedelta(months=1),
            "end_time": now_utc(),
            "group_by": ["groupby_dim_1", "groupby_dim_2", "groupby_dim_3"],
            "filter_properties": {
                "groupby_dim_1": ["foo", "bar"],
                "groupby_dim_2": ["baz"],
                "groupby_dim_3": ["quux"],
            },
            "query_type": METRIC_AGGREGATION.SUM,
            "property_name": "number",
            "event_type": EVENT_TYPE.DELTA,
            "granularity": METRIC_GRANULARITY.DAY,
        }
        query = Template(STATEFUL_GET_USAGE_WITH_GRANULARITY).render(**data)
        with connection.cursor() as cursor:
            cursor.execute(query)
            results = namedtuplefetchall(cursor)
        foo = [x for x in results if x.groupby_dim_1 == "foo"]
        bar = [x for x in results if x.groupby_dim_1 == "bar"]
        print("start_time", data["start_time"])
        print("foo", foo)
        assert 28 <= len(foo) <= 32
        assert 28 <= len(bar) <= 32
        assert max([x.usage_qty for x in foo if x.usage_qty is not None]) == 6
        assert max([x.usage_qty for x in bar if x.usage_qty is not None]) == 6
        assert False
