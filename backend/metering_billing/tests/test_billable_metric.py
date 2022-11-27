import json
from datetime import timedelta
from decimal import Decimal

import pytest
from dateutil import parser
from dateutil.relativedelta import relativedelta
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from metering_billing.models import (
    CategoricalFilter,
    Customer,
    Event,
    Metric,
    NumericFilter,
    PlanComponent,
    PlanVersion,
    PriceTier,
    Subscription,
)
from metering_billing.utils import now_utc
from metering_billing.utils.enums import (
    CATEGORICAL_FILTER_OPERATORS,
    EVENT_TYPE,
    METRIC_AGGREGATION,
    METRIC_GRANULARITY,
    METRIC_TYPE,
    NUMERIC_FILTER_OPERATORS,
    PLAN_DURATION,
    PRICE_TIER_TYPE,
    SUBSCRIPTION_STATUS,
    USAGE_CALC_GRANULARITY,
)
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APIClient


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


@pytest.fixture
def insert_billable_metric_payload():
    payload = {
        "event_name": "test_event",
        "property_name": "test_property",
        "usage_aggregation_type": METRIC_AGGREGATION.SUM,
        "metric_type": METRIC_TYPE.COUNTER,
    }
    return payload


@pytest.mark.django_db(transaction=True)
class TestInsertMetric:
    def test_api_key_can_create_billable_metric_empty_before(
        self,
        billable_metric_test_common_setup,
        insert_billable_metric_payload,
        get_billable_metrics_in_org,
    ):
        # covers num_billable_metrics_before_insert = 0, has_org_api_key=true, user_in_org=true, user_org_and_api_key_org_different=false
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )

        response = setup_dict["client"].post(
            reverse("metric-list"),
            data=json.dumps(insert_billable_metric_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0  # check that the response is not empty
        assert len(get_billable_metrics_in_org(setup_dict["org"])) == 1

    def test_session_auth_can_create_billable_metric_nonempty_before(
        self,
        billable_metric_test_common_setup,
        insert_billable_metric_payload,
        get_billable_metrics_in_org,
    ):
        # covers num_billable_metrics_before_insert = 0, has_org_api_key=true, user_in_org=true, user_org_and_api_key_org_different=false, authenticated=true
        num_billable_metrics = 5
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )

        response = setup_dict["client"].post(
            reverse("metric-list"),
            data=json.dumps(insert_billable_metric_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0
        assert (
            len(get_billable_metrics_in_org(setup_dict["org"]))
            == num_billable_metrics + 1
        )

    def test_user_org_and_api_key_different_reject_creation(
        self,
        billable_metric_test_common_setup,
        insert_billable_metric_payload,
        get_billable_metrics_in_org,
    ):
        # covers user_org_and_api_key_org_different = True
        num_billable_metrics = 3
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="both",
            user_org_and_api_key_org_different=True,
        )

        response = setup_dict["client"].post(
            reverse("metric-list"),
            data=json.dumps(insert_billable_metric_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_406_NOT_ACCEPTABLE
        assert (
            len(get_billable_metrics_in_org(setup_dict["org"])) == num_billable_metrics
        )
        assert (
            len(get_billable_metrics_in_org(setup_dict["org2"])) == num_billable_metrics
        )

    def test_billable_metric_exists_reject_creation(
        self,
        billable_metric_test_common_setup,
        insert_billable_metric_payload,
        get_billable_metrics_in_org,
    ):
        num_billable_metrics = 3
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )

        payload = insert_billable_metric_payload
        Metric.objects.create(
            **{
                **payload,
                "organization": setup_dict["org"],
                "billable_metric_name": "[coun] sum of test_property of test_event",
            }
        )
        response = setup_dict["client"].post(
            reverse("metric-list"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_409_CONFLICT
        assert (
            len(get_billable_metrics_in_org(setup_dict["org"]))
            == num_billable_metrics + 1
        )
        assert (
            len(get_billable_metrics_in_org(setup_dict["org2"])) == num_billable_metrics
        )


@pytest.mark.django_db(transaction=True)
class TestCalculateMetric:
    def test_count_unique(self, billable_metric_test_common_setup):
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )
        billable_metric = Metric.objects.create(
            organization=setup_dict["org"],
            property_name="test_property",
            event_name="test_event",
            usage_aggregation_type="unique",
        )
        time_created = parser.parse("2021-01-01T06:00:00Z")
        customer = baker.make(
            Customer, organization=setup_dict["org"], customer_name="test_customer"
        )
        baker.make(
            Event,
            event_name="test_event",
            properties={"test_property": "foo"},
            organization=setup_dict["org"],
            time_created=time_created,
            customer=customer,
            _quantity=5,
        )
        baker.make(
            Event,
            event_name="test_event",
            properties={"test_property": "bar"},
            organization=setup_dict["org"],
            time_created=time_created,
            customer=customer,
            _quantity=5,
        )
        metric_usage = billable_metric.get_usage(
            parser.parse("2021-01-01"),
            parser.parse("2021-01-30"),
            granularity=USAGE_CALC_GRANULARITY.TOTAL,
            customer=customer,
        )
        metric_usage = metric_usage[customer.customer_name]
        assert len(metric_usage) == 1  # no groupbys
        unique_tup, dd = list(metric_usage.items())[0]
        assert len(dd) == 1
        metric_usage = list(dd.values())[0]
        assert metric_usage == 2

    def test_stateful_total_granularity(self, billable_metric_test_common_setup):
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
        )
        time_created = now_utc() - relativedelta(days=21)
        customer = baker.make(
            Customer, organization=setup_dict["org"], customer_name="foo"
        )
        event_times = [time_created] + [
            time_created + relativedelta(days=i) for i in range(19)
        ]
        properties = (
            3 * [{"number": 1}]
            + 3 * [{"number": 2}]
            + 3 * [{"number": 3}]
            + 3 * [{"number": 4}]
            + 3 * [{"number": 5}]
            + 3 * [{"number": 6}]
            + [{"number": 3}]
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
        now = now_utc()
        subscription = Subscription.objects.create(
            organization=setup_dict["org"],
            billing_plan=billing_plan,
            customer=customer,
            start_date=now - relativedelta(days=23),
            status=SUBSCRIPTION_STATUS.ACTIVE,
        )

        usage_revenue_dict = plan_component.calculate_total_revenue(subscription)
        assert usage_revenue_dict["revenue"] == Decimal(300)

    def test_stateful_daily_granularity(self, billable_metric_test_common_setup):
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
        time_created = now_utc() - relativedelta(days=21)
        customer = baker.make(
            Customer, organization=setup_dict["org"], customer_name="foo"
        )
        event_times = [time_created] + [
            time_created + relativedelta(days=i) for i in range(1, 19)
        ]
        properties = (
            3 * [{"number": 3}]
            + 3 * [{"number": 3}]
            + 3 * [{"number": 3}]
            + 3 * [{"number": 4}]
            + 3 * [{"number": 5}]
            + 3 * [{"number": 6}]
            + [{"number": 3}]
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
        subscription = Subscription.objects.create(
            organization=setup_dict["org"],
            billing_plan=billing_plan,
            customer=customer,
            start_date=time_created,
            status=SUBSCRIPTION_STATUS.ACTIVE,
        )

        usage_revenue_dict = plan_component.calculate_total_revenue(subscription)
        # 3 * (4-3) + 3* (5-3) + 3 * (6-3) = 18 user*days ... it costs 100 per 1 month of
        # user days, so should be between 18/28*100 and 18/31*100
        assert usage_revenue_dict["revenue"] >= Decimal(100) * Decimal(18) / Decimal(31)
        assert usage_revenue_dict["revenue"] <= Decimal(100) * Decimal(18) / Decimal(28)

    def test_rate_hourly_granularity(self, billable_metric_test_common_setup):
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
        properties = (
            4 * [{"num_rows": 1}]
            + 3 * [{"num_rows": 2}]
            + 3 * [{"num_rows": 3}]
            + 3 * [{"num_rows": 4}]
            + 3 * [{"num_rows": 5}]
            + 3 * [{"num_rows": 6}]
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
        properties = (
            4 * [{"num_rows": 1}]
            + 3 * [{"num_rows": 2}]
            + 3 * [{"num_rows": 3}]
            + 2 * [{"num_rows": 4}]
            + 3 * [{"num_rows": 5}]
            + 3 * [{"num_rows": 6}]
        )  # = 60
        baker.make(
            Event,
            event_name="rows_inserted",
            properties=iter(properties),
            organization=setup_dict["org"],
            time_created=iter(event_times),
            customer=customer,
            _quantity=18,
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
        subscription = Subscription.objects.create(
            organization=setup_dict["org"],
            billing_plan=billing_plan,
            customer=customer,
            start_date=now - relativedelta(days=21),
            status=SUBSCRIPTION_STATUS.ACTIVE,
        )

        usage_revenue_dict = plan_component.calculate_total_revenue(subscription)
        # 1 dollar per for 64 rows - 3 free rows = 61 rows * 1 dollar = 61 dollars
        assert usage_revenue_dict["revenue"] == Decimal(61)

    def test_stateful_daily_granularity_delta_event(
        self, billable_metric_test_common_setup
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
        time_created = now_utc() - relativedelta(days=21)
        customer = baker.make(
            Customer, organization=setup_dict["org"], customer_name="test"
        )
        event_times = [time_created] + [
            time_created + relativedelta(days=i) for i in range(8)
        ]
        properties = (
            1 * [{"number": 3}]
            + 3 * [{"number": 1}]  # 1 hr at 4, 1 hr at 5, 1 hr at 6
            + 1 * [{"number": 0}]  # 1 hr at 6
            + 3 * [{"number": -1}]  # 1 hr at 4, 1 hr at 5
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
        subscription = Subscription.objects.create(
            organization=setup_dict["org"],
            billing_plan=billing_plan,
            customer=customer,
            start_date=time_created,
            status=SUBSCRIPTION_STATUS.ACTIVE,
        )

        usage_revenue_dict = plan_component.calculate_total_revenue(subscription)
        # 2 * (4-3) + 2* (5-3) + 2 * (6-3) = 12 user*days abvoe the free tier... it costs 100
        # per 1 month of user*days, so should be between 12/28*100 and 12/31*100
        assert Decimal(100) * Decimal(12) / Decimal(28) >= usage_revenue_dict["revenue"]
        assert Decimal(100) * Decimal(12) / Decimal(31) <= usage_revenue_dict["revenue"]

    def test_stateful_daily_granularity_with_group_by(
        self, billable_metric_test_common_setup
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
        time_created = now_utc() - relativedelta(days=21)
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
        subscription = Subscription.objects.create(
            organization=setup_dict["org"],
            billing_plan=billing_plan,
            customer=customer,
            start_date=time_created,
            status=SUBSCRIPTION_STATUS.ACTIVE,
        )

        usage_revenue_dict = plan_component.calculate_total_revenue(subscription)
        # 3 * (4-3) + 3* (5-3) + 3 * (6-3) = 18 user*days ... it costs 100 per 1 month of
        # user days, so should be between 18/28*100 and 18/31*100
        # if we multiply this by the 8 different combinations we're suppsoed to have, we
        # should get the expected number
        assert usage_revenue_dict["revenue"] >= 8 * Decimal(100) * Decimal(
            18
        ) / Decimal(31)
        assert usage_revenue_dict["revenue"] <= 8 * Decimal(100) * Decimal(
            18
        ) / Decimal(28)

    def test_stateful_daily_granularity_delta_event_with_groupby(
        self, billable_metric_test_common_setup
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
        time_created = now_utc() - relativedelta(days=21)
        customer = baker.make(
            Customer, organization=setup_dict["org"], customer_name="test"
        )
        event_times = [time_created] + [
            time_created + relativedelta(days=i) for i in range(8)
        ]
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
        subscription = Subscription.objects.create(
            organization=setup_dict["org"],
            billing_plan=billing_plan,
            customer=customer,
            start_date=time_created,
            status=SUBSCRIPTION_STATUS.ACTIVE,
        )

        usage_revenue_dict = plan_component.calculate_total_revenue(subscription)
        # 2 * (4-3) + 2* (5-3) + 2 * (6-3) = 12 user*days abvoe the free tier... it costs 100
        # per 1 month of user*days, so should be between 12/28*100 and 12/31*100
        # if we multiply this by the 8 different combinations we're suppsoed to have, we
        assert (
            8 * Decimal(100) * Decimal(12) / Decimal(28)
            >= usage_revenue_dict["revenue"]
        )
        assert (
            8 * Decimal(100) * Decimal(12) / Decimal(31)
            <= usage_revenue_dict["revenue"]
        )

    def test_rate_hourly_granularity_with_groupby(
        self, billable_metric_test_common_setup
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
            Customer, organization=setup_dict["org"], customer_name="test"
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
            separate_by=["groupby_dim_1", "groupby_dim_2", "groupby_dim_3"],
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
        subscription = Subscription.objects.create(
            organization=setup_dict["org"],
            billing_plan=billing_plan,
            customer=customer,
            start_date=now - relativedelta(days=21),
            status=SUBSCRIPTION_STATUS.ACTIVE,
        )

        usage_revenue_dict = plan_component.calculate_total_revenue(subscription)
        # 1 dollar per for 64 rows - 3 free rows = 61 rows * 1 dollar = 61 dollars
        assert usage_revenue_dict["revenue"] == 8 * Decimal(61)

    def test_count_unique_with_groupby(self, billable_metric_test_common_setup):
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )
        billable_metric = Metric.objects.create(
            organization=setup_dict["org"],
            event_name="test_event",
            property_name="test_property",
            usage_aggregation_type=METRIC_AGGREGATION.UNIQUE,
            metric_type=METRIC_TYPE.COUNTER,
        )
        time_created = now_utc() - relativedelta(days=14, hour=0)
        customer = baker.make(
            Customer, organization=setup_dict["org"], customer_name="test"
        )
        event_times = [time_created] + [
            time_created + relativedelta(minutes=i) for i in range(1, 2)
        ]

        customer = baker.make(
            Customer, organization=setup_dict["org"], customer_name="foo"
        )
        for groupby_dim_1 in ["foo", "bar"]:
            for groupby_dimension_2 in ["baz", "qux"]:
                for groupby_dimension_3 in ["quux", "quuz"]:
                    baker.make(
                        Event,
                        event_name="test_event",
                        properties={
                            "test_property": "foo",
                            "groupby_dim_1": groupby_dim_1,
                            "groupby_dim_2": groupby_dimension_2,
                            "groupby_dim_3": groupby_dimension_3,
                        },
                        organization=setup_dict["org"],
                        time_created=event_times[0],
                        customer=customer,
                        _quantity=5,
                    )
                    baker.make(
                        Event,
                        event_name="test_event",
                        properties={
                            "test_property": "bar",
                            "groupby_dim_1": groupby_dim_1,
                            "groupby_dim_2": groupby_dimension_2,
                            "groupby_dim_3": groupby_dimension_3,
                        },
                        organization=setup_dict["org"],
                        time_created=event_times[1],
                        customer=customer,
                        _quantity=5,
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
        )
        free_tier = PriceTier.objects.create(
            plan_component=plan_component,
            type=PRICE_TIER_TYPE.FREE,
            range_start=0,
            range_end=1,
        )
        paid_tier = PriceTier.objects.create(
            plan_component=plan_component,
            type=PRICE_TIER_TYPE.PER_UNIT,
            range_start=1,
            cost_per_batch=100,
            metric_units_per_batch=1,
        )
        subscription = Subscription.objects.create(
            organization=setup_dict["org"],
            billing_plan=billing_plan,
            customer=customer,
            start_date=time_created,
            status=SUBSCRIPTION_STATUS.ACTIVE,
        )

        usage_revenue_dict = plan_component.calculate_total_revenue(subscription)
        # 2 (-1 free) unique + 8 combinations gives 800
        assert 8 * Decimal(100) == usage_revenue_dict["revenue"]


@pytest.mark.django_db(transaction=True)
class TestCalculateMetricProrationForStateful:
    def test_proration_and_metric_granularity_sub_day(
        self, billable_metric_test_common_setup
    ):
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )
        billable_metric = Metric.objects.create(
            organization=setup_dict["org"],
            event_name="number_of_users",
            property_name="number",
            usage_aggregation_type=METRIC_AGGREGATION.MAX,
            metric_type=METRIC_TYPE.STATEFUL,
            granularity=METRIC_GRANULARITY.HOUR,
        )
        time_created = now_utc() - relativedelta(days=21)
        customer = baker.make(
            Customer, organization=setup_dict["org"], customer_name="foo"
        )
        event_times = [
            time_created + relativedelta(days=1) + relativedelta(hour=23, minute=i)
            for i in range(55, 60)
        ]
        event_times += [
            time_created + relativedelta(days=2) + relativedelta(hour=0, minute=i)
            for i in range(6)
        ]
        properties = (
            3 * [{"number": 8}]  # 55-56, 56-57, 57-58 at 8
            + 2 * [{"number": 9}]  # 58-59, 59-60 at 9
            + 1 * [{"number": 10}]  # 60-61 at 10
            + 1 * [{"number": 11}]  # 61-62 at 11
            + 2 * [{"number": 6}]  # 62-63, 63-64 at 6
            + 1 * [{"number": 12}]  # 64-65 at 12
            + [{"number": 0}]  # everything else back to 0
        )  # this should total 3*8 + 2*9 + 1*10 + 1*11 + 2*6 + 1*12 = 87
        baker.make(
            Event,
            event_name="number_of_users",
            properties=iter(properties),
            organization=setup_dict["org"],
            time_created=iter(event_times),
            customer=customer,
            _quantity=11,
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
            proration_granularity=METRIC_GRANULARITY.MINUTE,
        )
        free_tier = PriceTier.objects.create(
            plan_component=plan_component,
            type=PRICE_TIER_TYPE.FREE,
            range_start=0,
            range_end=1,
        )
        paid_tier = PriceTier.objects.create(
            plan_component=plan_component,
            type=PRICE_TIER_TYPE.PER_UNIT,
            range_start=1,
            cost_per_batch=100,
            metric_units_per_batch=1,
        )
        now = now_utc()
        subscription = Subscription.objects.create(
            organization=setup_dict["org"],
            billing_plan=billing_plan,
            customer=customer,
            start_date=now - relativedelta(days=23),
            status=SUBSCRIPTION_STATUS.ACTIVE,
        )

        usage_revenue_dict = plan_component.calculate_total_revenue(subscription)
        calculated_amt = (Decimal(87) - Decimal(60)) / Decimal(60) * Decimal(100)
        assert abs(usage_revenue_dict["revenue"] - calculated_amt) < Decimal(0.01)

        payload = {}
        response = setup_dict["client"].get(
            reverse("cost_analysis"),
            {
                "customer_id": customer.customer_id,
                "start_date": subscription.start_date.date(),
                "end_date": subscription.end_date.date(),
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        per_day = data["per_day"]
        date_where_billable_events_happened = (
            time_created + relativedelta(days=2)
        ).date()
        for day in per_day:
            if day["date"] == str(date_where_billable_events_happened):
                assert abs(day["revenue"] - float(calculated_amt)) < 0.01
            else:
                assert day["revenue"] == 0
        assert abs(data["total_revenue"] - float(calculated_amt)) < 0.01

    def test_metric_granularity_daily_proration_smaller_than_day(
        self, billable_metric_test_common_setup
    ):
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )
        billable_metric = Metric.objects.create(
            organization=setup_dict["org"],
            event_name="number_of_users",
            property_name="number",
            usage_aggregation_type=METRIC_AGGREGATION.MAX,
            metric_type=METRIC_TYPE.STATEFUL,
            granularity=METRIC_GRANULARITY.DAY,
        )
        time_created = now_utc() - relativedelta(days=21)
        customer = baker.make(
            Customer, organization=setup_dict["org"], customer_name="foo"
        )
        event_times = [
            time_created + relativedelta(days=1) + relativedelta(hour=i)
            for i in range(20, 24)
        ]
        event_times += [
            time_created + relativedelta(days=2) + relativedelta(hour=i)
            for i in range(7)
        ]
        properties = (
            4 * [{"number": 12}]  # 20-21, 21-22, 22-23, 23-24 at 12
            + 6 * [{"number": 4}]  # 0-1, 1-2, 2-3, 3-4, 4-5, 5-6 at 4
            + [{"number": 0}]  # everything else back to 0
        )  # this should total 4*12 + 6*9 = 72
        baker.make(
            Event,
            event_name="number_of_users",
            properties=iter(properties),
            organization=setup_dict["org"],
            time_created=iter(event_times),
            customer=customer,
            _quantity=11,
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
            proration_granularity=METRIC_GRANULARITY.HOUR,
        )
        free_tier = PriceTier.objects.create(
            plan_component=plan_component,
            type=PRICE_TIER_TYPE.FREE,
            range_start=0,
            range_end=1,
        )
        paid_tier = PriceTier.objects.create(
            plan_component=plan_component,
            type=PRICE_TIER_TYPE.PER_UNIT,
            range_start=1,
            cost_per_batch=100,
            metric_units_per_batch=1,
        )
        now = now_utc()
        subscription = Subscription.objects.create(
            organization=setup_dict["org"],
            billing_plan=billing_plan,
            customer=customer,
            start_date=now - relativedelta(days=23),
            status=SUBSCRIPTION_STATUS.ACTIVE,
        )

        usage_revenue_dict = plan_component.calculate_total_revenue(subscription)
        supposed_revenue = (Decimal(72) - Decimal(24)) / Decimal(24) * Decimal(100)
        assert abs(usage_revenue_dict["revenue"] - supposed_revenue) < Decimal(0.01)

        payload = {}
        response = setup_dict["client"].get(
            reverse("cost_analysis"),
            {
                "customer_id": customer.customer_id,
                "start_date": subscription.start_date.date(),
                "end_date": subscription.end_date.date(),
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        per_day = data["per_day"]
        first_day = (time_created + relativedelta(days=1)).date()
        second_day = (time_created + relativedelta(days=2)).date()
        for day in per_day:
            if day["date"] in [str(first_day), str(second_day)]:
                assert abs(day["revenue"] - float(supposed_revenue / 2)) < 0.01
            else:
                assert day["revenue"] == 0
        assert abs(data["total_revenue"] - float(supposed_revenue)) < 0.01

    def test_metric_granularity_greater_than_daily_proration_smaller_than_day(
        self, billable_metric_test_common_setup
    ):
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )
        plan = setup_dict["plan"]
        plan.plan_duration = PLAN_DURATION.YEARLY
        plan.save()
        billable_metric = Metric.objects.create(
            organization=setup_dict["org"],
            event_name="number_of_users",
            property_name="number",
            usage_aggregation_type=METRIC_AGGREGATION.MAX,
            metric_type=METRIC_TYPE.STATEFUL,
            granularity=METRIC_GRANULARITY.MONTH,
        )
        time_created = now_utc() - relativedelta(months=3, days=21)
        customer = baker.make(
            Customer, organization=setup_dict["org"], customer_name="foo"
        )
        event_times = [
            time_created
            + relativedelta(day=1)
            - relativedelta(days=1)
            + relativedelta(hour=i)
            for i in range(20, 24)
        ]
        event_times += [
            time_created + relativedelta(day=1) + relativedelta(hour=i)
            for i in range(7)
        ]
        properties = (  # max 744 hours in a month, minimum 672.
            4
            * [{"number": 167}]  # 20-21, 21-22, 22-23, 23-24 at 167 (just short of min)
            + 6
            * [{"number": 13}]  # 0-1, 1-2, 2-3, 3-4, 4-5, 5-6 at 13 (just above max)
            + [{"number": 0}]  # everything else back to 0
        )  # this should total 4*167 + 6*13 = 746 (so right above 1, def less than 2)
        baker.make(
            Event,
            event_name="number_of_users",
            properties=iter(properties),
            organization=setup_dict["org"],
            time_created=iter(event_times),
            customer=customer,
            _quantity=11,
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
            proration_granularity=METRIC_GRANULARITY.HOUR,
        )
        free_tier = PriceTier.objects.create(
            plan_component=plan_component,
            type=PRICE_TIER_TYPE.FREE,
            range_start=0,
            range_end=1,
        )
        paid_tier = PriceTier.objects.create(
            plan_component=plan_component,
            type=PRICE_TIER_TYPE.PER_UNIT,
            range_start=1,
            cost_per_batch=100,
            metric_units_per_batch=1,
        )
        now = now_utc()
        subscription = Subscription.objects.create(
            organization=setup_dict["org"],
            billing_plan=billing_plan,
            customer=customer,
            start_date=now - relativedelta(months=4, days=23),
            status=SUBSCRIPTION_STATUS.ACTIVE,
        )

        usage_revenue_dict = plan_component.calculate_total_revenue(subscription)
        assert Decimal(100) > usage_revenue_dict["revenue"] > Decimal(0)

        payload = {}
        response = setup_dict["client"].get(
            reverse("cost_analysis"),
            {
                "customer_id": customer.customer_id,
                "start_date": subscription.start_date.date(),
                "end_date": subscription.end_date.date(),
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        per_day = data["per_day"]
        first_day = (time_created + relativedelta(day=1)).date()
        for day in per_day:
            if day["date"] in [
                str(first_day),
            ]:
                assert Decimal(100) > day["revenue"] > Decimal(0)
            else:
                assert day["revenue"] == 0
        assert data["total_revenue"] == float(usage_revenue_dict["revenue"])

    def test_metric_granularity_total_on_yearly_plan_proration_quarterly(
        self, billable_metric_test_common_setup
    ):
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )
        plan = setup_dict["plan"]
        plan.plan_duration = PLAN_DURATION.YEARLY
        plan.save()
        billable_metric = Metric.objects.create(
            organization=setup_dict["org"],
            event_name="number_of_users",
            property_name="number",
            usage_aggregation_type=METRIC_AGGREGATION.MAX,
            metric_type=METRIC_TYPE.STATEFUL,
            granularity=METRIC_GRANULARITY.TOTAL,
        )
        time_created = now_utc() - relativedelta(months=5)
        customer = baker.make(
            Customer, organization=setup_dict["org"], customer_name="foo"
        )
        event_times = [time_created + relativedelta(days=i) for i in range(0, 4)]
        properties = (
            1 * [{"number": 4}]
            + 1 * [{"number": 8}]
            + 1 * [{"number": 12}]
            + [{"number": 0}]
        )  # 4 corresponds to 1 user-year, 8 to 2 user-years, 12 to 3 user-years.. so total will
        # be 3 user-years, which is 200... we should make sure that we have 100 each day cuz
        # that's how much we "earned" that day
        baker.make(
            Event,
            event_name="number_of_users",
            properties=iter(properties),
            organization=setup_dict["org"],
            time_created=iter(event_times),
            customer=customer,
            _quantity=4,
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
            proration_granularity=METRIC_GRANULARITY.QUARTER,
        )
        free_tier = PriceTier.objects.create(
            plan_component=plan_component,
            type=PRICE_TIER_TYPE.FREE,
            range_start=0,
            range_end=1,
        )
        paid_tier = PriceTier.objects.create(
            plan_component=plan_component,
            type=PRICE_TIER_TYPE.PER_UNIT,
            range_start=1,
            cost_per_batch=100,
            metric_units_per_batch=1,
        )
        now = now_utc()
        subscription = Subscription.objects.create(
            organization=setup_dict["org"],
            billing_plan=billing_plan,
            customer=customer,
            start_date=now - relativedelta(months=6, day=1, hour=0),
            status=SUBSCRIPTION_STATUS.ACTIVE,
        )

        usage_revenue_dict = plan_component.calculate_total_revenue(subscription)
        assert usage_revenue_dict["revenue"] == Decimal(200)

        payload = {}
        response = setup_dict["client"].get(
            reverse("cost_analysis"),
            {
                "customer_id": customer.customer_id,
                "start_date": subscription.start_date.date(),
                "end_date": subscription.end_date.date(),
            },
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        per_day = data["per_day"]
        amt_per_day = None
        for day in per_day:
            if day["revenue"] != 0 and not amt_per_day:
                amt_per_day = day["revenue"]
                assert amt_per_day == 100
                assert amt_per_day == day["revenue"]
            else:
                assert day["revenue"] == 0 or day["revenue"] == amt_per_day
        assert data["total_revenue"] == usage_revenue_dict["revenue"]


@pytest.mark.django_db(transaction=True)
class TestCalculateMetricWithFilters:
    def test_count_unique_with_filters(self, billable_metric_test_common_setup):
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )
        billable_metric = Metric.objects.create(
            organization=setup_dict["org"],
            property_name="test_property",
            event_name="test_event",
            usage_aggregation_type="unique",
        )
        numeric_filter = NumericFilter.objects.create(
            property_name="test_filter_property",
            operator=NUMERIC_FILTER_OPERATORS.GT,
            comparison_value=10,
        )
        billable_metric.numeric_filters.add(numeric_filter)
        billable_metric.save()
        time_created = parser.parse("2021-01-01T06:00:00Z")
        customer = baker.make(
            Customer, organization=setup_dict["org"], customer_name="test_customer"
        )
        baker.make(
            Event,
            event_name="test_event",
            properties={"test_property": "foo", "test_filter_property": 11},
            organization=setup_dict["org"],
            time_created=time_created,
            customer=customer,
            _quantity=5,
        )
        baker.make(
            Event,
            event_name="test_event",
            properties={"test_property": "bar", "test_filter_property": 11},
            organization=setup_dict["org"],
            time_created=time_created,
            customer=customer,
            _quantity=5,
        )
        baker.make(
            Event,
            event_name="test_event",
            properties={"test_property": "baz", "test_filter_property": 9},
            organization=setup_dict["org"],
            time_created=time_created,
            customer=customer,
            _quantity=5,
        )
        metric_usage = billable_metric.get_usage(
            parser.parse("2021-01-01"),
            parser.parse("2021-01-30"),
            granularity=USAGE_CALC_GRANULARITY.TOTAL,
            customer=customer,
        )
        print(metric_usage)
        metric_usage = metric_usage[customer.customer_name]
        assert len(metric_usage) == 1  # no groupbys
        unique_tup, dd = list(metric_usage.items())[0]
        assert len(dd) == 1
        metric_usage = list(dd.values())[0]
        assert metric_usage == 2

    def test_stateful_total_granularity_with_filters(
        self, billable_metric_test_common_setup
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
        )
        numeric_filter = NumericFilter.objects.create(
            property_name="test_filter_property",
            operator=NUMERIC_FILTER_OPERATORS.EQ,
            comparison_value=10,
        )
        billable_metric.numeric_filters.add(numeric_filter)
        billable_metric.save()
        time_created = now_utc() - relativedelta(days=21)
        customer = baker.make(
            Customer, organization=setup_dict["org"], customer_name="foo"
        )
        event_times = [time_created] + [
            time_created + relativedelta(days=i) for i in range(20)
        ]
        properties = (
            3 * [{"number": 1, "test_filter_property": 10}]
            + 3 * [{"number": 2, "test_filter_property": 10}]
            + 3 * [{"number": 3, "test_filter_property": 10}]
            + 3 * [{"number": 4, "test_filter_property": 10}]
            + 3 * [{"number": 5, "test_filter_property": 10}]
            + 3 * [{"number": 6, "test_filter_property": 10}]
            + [{"number": 3, "test_filter_property": 10}]
            + [{"number": 4, "test_filter_property": 11}]
        )
        baker.make(
            Event,
            event_name="number_of_users",
            properties=iter(properties),
            organization=setup_dict["org"],
            time_created=iter(event_times),
            customer=customer,
            _quantity=20,
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
            cost_per_batch=100,
            metric_units_per_batch=1,
        )
        now = now_utc()
        subscription = Subscription.objects.create(
            organization=setup_dict["org"],
            billing_plan=billing_plan,
            customer=customer,
            start_date=now - relativedelta(days=23),
            status=SUBSCRIPTION_STATUS.ACTIVE,
        )

        usage_revenue_dict = plan_component.calculate_total_revenue(subscription)
        assert usage_revenue_dict["revenue"] == Decimal(300)

    def test_stateful_daily_granularity_with_filters(
        self, billable_metric_test_common_setup
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
        numeric_filter = CategoricalFilter.objects.create(
            property_name="test_filter_property",
            operator=CATEGORICAL_FILTER_OPERATORS.ISIN,
            comparison_value=["a", "b", "c"],
        )
        billable_metric.categorical_filters.add(numeric_filter)
        billable_metric.save()
        time_created = now_utc() - relativedelta(days=21)
        customer = baker.make(
            Customer, organization=setup_dict["org"], customer_name="foo"
        )
        event_times = [time_created] + [
            time_created + relativedelta(days=i) for i in range(1, 20)
        ]
        properties = (
            3 * [{"number": 3, "test_filter_property": "a"}]
            + 3 * [{"number": 3, "test_filter_property": "b"}]
            + 3 * [{"number": 3, "test_filter_property": "c"}]
            + 3 * [{"number": 4, "test_filter_property": "a"}]
            + 3 * [{"number": 5, "test_filter_property": "b"}]
            + 3 * [{"number": 6, "test_filter_property": "c"}]
            + [{"number": 3, "test_filter_property": "a"}]
            + [{"number": 50, "test_filter_property": "d"}]
        )
        baker.make(
            Event,
            event_name="number_of_users",
            properties=iter(properties),
            organization=setup_dict["org"],
            time_created=iter(event_times),
            customer=customer,
            _quantity=20,
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
        subscription = Subscription.objects.create(
            organization=setup_dict["org"],
            billing_plan=billing_plan,
            customer=customer,
            start_date=time_created,
            status=SUBSCRIPTION_STATUS.ACTIVE,
        )

        usage_revenue_dict = plan_component.calculate_total_revenue(subscription)
        # 3 * (4-3) + 3* (5-3) + 3 * (6-3) = 18 user*days ... it costs 100 per 1 month of
        # user days, so should be between 18/28*100 and 18/31*100
        assert usage_revenue_dict["revenue"] >= Decimal(100) * Decimal(18) / Decimal(31)
        assert usage_revenue_dict["revenue"] <= Decimal(100) * Decimal(18) / Decimal(28)

    def test_rate_hourly_granularity_with_filters(
        self, billable_metric_test_common_setup
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
        numeric_filter = CategoricalFilter.objects.create(
            property_name="test_filter_property",
            operator=CATEGORICAL_FILTER_OPERATORS.ISNOTIN,
            comparison_value=["a", "b", "c"],
        )
        billable_metric.categorical_filters.add(numeric_filter)
        billable_metric.save()
        time_created = now_utc() - relativedelta(days=14, hour=0)
        customer = baker.make(
            Customer, organization=setup_dict["org"], customer_name="foo"
        )

        # 64 in an hour, 14 days ago
        event_times = [time_created] + [
            time_created + relativedelta(minutes=i) for i in range(1, 20)
        ]
        properties = (
            4 * [{"num_rows": 1, "test_filter_property": "12erfg"}]
            + 3 * [{"num_rows": 2, "test_filter_property": "4refvbnj"}]
            + 3 * [{"num_rows": 3, "test_filter_property": "redfvbhj"}]
            + 3 * [{"num_rows": 4, "test_filter_property": "yfvbn"}]
            + 3 * [{"num_rows": 5, "test_filter_property": "9yge"}]
            + 3 * [{"num_rows": 6, "test_filter_property": "wedsfgu"}]
            + [{"num_rows": 3, "test_filter_property": "a"}]
        )  # = 64
        baker.make(
            Event,
            event_name="rows_inserted",
            properties=iter(properties),
            organization=setup_dict["org"],
            time_created=iter(event_times),
            customer=customer,
            _quantity=20,
        )
        # 60 in an hour, 5 days ago
        time_created = now_utc() - relativedelta(days=5, hour=0)
        event_times = [time_created] + [
            time_created + relativedelta(minutes=i) for i in range(1, 19)
        ]
        properties = (
            4 * [{"num_rows": 1}]
            + 3 * [{"num_rows": 2}]
            + 3 * [{"num_rows": 3}]
            + 2 * [{"num_rows": 4}]
            + 3 * [{"num_rows": 5}]
            + 3 * [{"num_rows": 6}]
        )  # = 60
        baker.make(
            Event,
            event_name="rows_inserted",
            properties=iter(properties),
            organization=setup_dict["org"],
            time_created=iter(event_times),
            customer=customer,
            _quantity=18,
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
        subscription = Subscription.objects.create(
            organization=setup_dict["org"],
            billing_plan=billing_plan,
            customer=customer,
            start_date=now - relativedelta(days=21),
            status=SUBSCRIPTION_STATUS.ACTIVE,
        )

        usage_revenue_dict = plan_component.calculate_total_revenue(subscription)
        # 1 dollar per for 64 rows - 3 free rows = 61 rows * 1 dollar = 61 dollars
        assert usage_revenue_dict["revenue"] == Decimal(61)
