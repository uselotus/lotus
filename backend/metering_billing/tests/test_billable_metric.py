import json
from datetime import timedelta
from decimal import Decimal

import pytest
from dateutil import parser
from dateutil.relativedelta import relativedelta
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from metering_billing.models import (
    BillableMetric,
    Customer,
    Event,
    PlanComponent,
    PlanVersion,
    PriceTier,
    Subscription,
)
from metering_billing.utils import now_utc
from metering_billing.utils.enums import (
    EVENT_TYPE,
    METRIC_AGGREGATION,
    METRIC_GRANULARITY,
    METRIC_TYPE,
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
class TestInsertBillableMetric:
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
        BillableMetric.objects.create(
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
class TestCalculateBillableMetric:
    def test_count_unique(self, billable_metric_test_common_setup):
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )
        billable_metric = BillableMetric.objects.create(
            organization=setup_dict["org"],
            property_name="test_property",
            event_name="test_event",
            usage_aggregation_type="unique",
        )
        time_created = parser.parse("2021-01-01T06:00:00Z")
        customer = baker.make(Customer, organization=setup_dict["org"])
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
        metric_usage = list(metric_usage.values())[0]

        assert metric_usage == 2

    def test_stateful_total_granularity(self, billable_metric_test_common_setup):
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )
        billable_metric = BillableMetric.objects.create(
            organization=setup_dict["org"],
            event_name="number_of_users",
            property_name="number",
            usage_aggregation_type=METRIC_AGGREGATION.MAX,
            metric_type=METRIC_TYPE.STATEFUL,
        )
        time_created = now_utc() - relativedelta(days=21)
        customer = baker.make(Customer, organization=setup_dict["org"])
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
        billable_metric = BillableMetric.objects.create(
            organization=setup_dict["org"],
            event_name="number_of_users",
            property_name="number",
            usage_aggregation_type=METRIC_AGGREGATION.MAX,
            metric_type=METRIC_TYPE.STATEFUL,
            granularity=METRIC_GRANULARITY.DAY,
        )
        time_created = now_utc() - relativedelta(days=21)
        customer = baker.make(Customer, organization=setup_dict["org"])
        event_times = [time_created] + [
            time_created + relativedelta(days=i) for i in range(1, 19)
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
        billable_metric = BillableMetric.objects.create(
            organization=setup_dict["org"],
            event_name="rows_inserted",
            property_name="num_rows",
            usage_aggregation_type=METRIC_AGGREGATION.SUM,
            billable_aggregation_type=METRIC_AGGREGATION.MAX,
            metric_type=METRIC_TYPE.RATE,
            granularity=METRIC_GRANULARITY.DAY,
        )
        time_created = now_utc() - relativedelta(days=14, hour=0)
        customer = baker.make(Customer, organization=setup_dict["org"])
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
        billable_metric = BillableMetric.objects.create(
            organization=setup_dict["org"],
            event_name="number_of_users",
            property_name="number",
            usage_aggregation_type=METRIC_AGGREGATION.MAX,
            metric_type=METRIC_TYPE.STATEFUL,
            granularity=METRIC_GRANULARITY.DAY,
            event_type=EVENT_TYPE.DELTA,
        )
        time_created = now_utc() - relativedelta(days=21)
        customer = baker.make(
            Customer, organization=setup_dict["org"], customer_name="test"
        )
        event_times = [time_created] + [
            time_created + relativedelta(days=i) for i in range(1, 11)
        ]
        properties = (
            3 * [{"number": 1}]
            + 3 * [{"number": 1}]  # 1 hr at 4, 1 hr at 5, 1 hr at 6
            + 1 * [{"number": 0}]  # 1 hr at 6
            + 3 * [{"number": -1}]  # 1 hr at 4, 1 hr at 5, 1 hr at 6
            + 2 * [{"number": -1}]
        )
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
