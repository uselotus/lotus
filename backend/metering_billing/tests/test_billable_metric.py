import itertools
import json
import unittest.mock as mock
from decimal import Decimal

import pytest
from dateutil.relativedelta import relativedelta
from django.urls import reverse
from metering_billing.aggregation.billable_metrics import METRIC_HANDLER_MAP
from metering_billing.models import (
    CategoricalFilter,
    Event,
    Metric,
    NumericFilter,
    PlanComponent,
    PlanVersion,
    PriceTier,
)
from metering_billing.serializers.serializer_utils import DjangoJSONEncoder
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
    add_customers_to_org,
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
        (customer,) = add_customers_to_org(org, n=1)
        setup_dict["customer"] = customer
        return setup_dict

    return do_billable_metric_test_common_setup


@pytest.fixture
def insert_billable_metric_payload():
    payload = {
        "event_name": "test_event",
        "property_name": "test_property",
        "usage_aggregation_type": METRIC_AGGREGATION.SUM,
        "metric_type": METRIC_TYPE.COUNTER,
        "metric_name": "test_billable_metric",
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
        payload["billable_metric_name"] = payload.pop("metric_name")
        Metric.objects.create(
            **{
                **payload,
                "organization": setup_dict["org"],
            }
        )
        payload["metric_name"] = payload.pop("billable_metric_name")
        response = setup_dict["client"].post(
            reverse("metric-list"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            len(get_billable_metrics_in_org(setup_dict["org"]))
            == num_billable_metrics + 1
        )
        assert (
            len(get_billable_metrics_in_org(setup_dict["org2"])) == num_billable_metrics
        )


@pytest.mark.django_db(transaction=True)
class TestArchiveMetric:
    def test_cant_archive_with_active_plan_version(
        self,
        billable_metric_test_common_setup,
        insert_billable_metric_payload,
        get_billable_metrics_in_org,
        add_product_to_org,
        add_plan_to_product,
    ):
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )
        org = setup_dict["org"]

        metric_set = baker.make(
            Metric,
            organization=org,
            event_name="email_sent",
            property_name=itertools.cycle(["num_characters", "peak_bandwith", ""]),
            usage_aggregation_type=itertools.cycle(["sum", "max", "count"]),
            billable_metric_name=itertools.cycle(
                ["count_chars", "peak_bandwith", "email_sent"]
            ),
            _quantity=3,
        )
        setup_dict["metrics"] = metric_set
        product = add_product_to_org(org)
        setup_dict["product"] = product
        plan = add_plan_to_product(product)
        setup_dict["plan"] = plan
        billing_plan = baker.make(
            PlanVersion,
            organization=org,
            description="test_plan for testing",
            plan=plan,
            status=PLAN_VERSION_STATUS.ACTIVE,
        )
        for i, (fmu, cpb, mupb) in enumerate(
            zip([50, 0, 1], [5, 0.05, 2], [100, 1, 1])
        ):
            pc = PlanComponent.objects.create(
                plan_version=billing_plan,
                billable_metric=metric_set[i],
            )
            start = 0
            if fmu > 0:
                PriceTier.objects.create(
                    plan_component=pc,
                    type=PriceTier.PriceTierType.FREE,
                    range_start=0,
                    range_end=fmu,
                )
                start = fmu
            PriceTier.objects.create(
                plan_component=pc,
                type=PriceTier.PriceTierType.PER_UNIT,
                range_start=start,
                cost_per_batch=cpb,
                metric_units_per_batch=mupb,
            )
        setup_dict["billing_plan"] = billing_plan

        payload = {"status": METRIC_STATUS.ARCHIVED}
        assert billing_plan.status == PLAN_VERSION_STATUS.ACTIVE
        assert billing_plan.plan.status == PLAN_STATUS.ACTIVE
        assert billing_plan.plan_components.count() == 3
        all_pcs = billing_plan.plan_components.all()
        assert (
            all_pcs[0].billable_metric == metric_set[0]
            or all_pcs[1].billable_metric == metric_set[0]
            or all_pcs[2].billable_metric == metric_set[0]
        )
        response = setup_dict["client"].patch(
            reverse(
                "metric-detail",
                kwargs={"metric_id": "metric_" + metric_set[0].metric_id.hex},
            ),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            response.data["type"]
            == "https://docs.uselotus.io/errors/error-responses#validation-error"
        )
        billing_plan.status = PLAN_VERSION_STATUS.ARCHIVED
        billing_plan.save()

        response = setup_dict["client"].patch(
            reverse(
                "metric-detail",
                kwargs={"metric_id": "metric_" + metric_set[0].metric_id.hex},
            ),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert (
            Metric.objects.get(metric_id=metric_set[0].metric_id).status
            == METRIC_STATUS.ARCHIVED
        )


@pytest.mark.django_db(transaction=True)
class TestCalculateMetric:
    def test_count_unique(
        self, billable_metric_test_common_setup, add_subscription_record_to_org
    ):
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
            usage_aggregation_type=METRIC_AGGREGATION.UNIQUE,
            metric_type=METRIC_TYPE.COUNTER,
        )
        METRIC_HANDLER_MAP[billable_metric.metric_type].create_continuous_aggregate(
            billable_metric
        )
        time_created = now_utc()
        customer = setup_dict["customer"]
        baker.make(
            Event,
            event_name="test_event",
            properties={"test_property": "foo"},
            organization=setup_dict["org"],
            time_created=time_created,
            cust_id=customer.customer_id,
            _quantity=5,
        )
        baker.make(
            Event,
            event_name="test_event",
            properties={"test_property": "bar"},
            organization=setup_dict["org"],
            time_created=time_created,
            cust_id=customer.customer_id,
            _quantity=5,
        )
        billing_plan = PlanVersion.objects.create(
            organization=setup_dict["org"],
            version=1,
            plan=setup_dict["plan"],
        )
        plan_component = PlanComponent.objects.create(
            billable_metric=billable_metric,
            plan_version=billing_plan,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.FREE,
            range_start=0,
            range_end=3,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.PER_UNIT,
            range_start=3,
            cost_per_batch=100,
            metric_units_per_batch=1,
        )
        now = now_utc()
        with (
            mock.patch(
                "metering_billing.models.now_utc",
                return_value=now - relativedelta(days=1),
            ),
            mock.patch(
                "metering_billing.tests.test_billable_metric.now_utc",
                return_value=now - relativedelta(days=1),
            ),
        ):
            subscription_record = add_subscription_record_to_org(
                setup_dict["org"],
                billing_plan,
                customer,
                now - relativedelta(days=1),
            )
        metric_usage = billable_metric.get_subscription_record_total_billable_usage(
            subscription_record
        )
        assert metric_usage == 2

    def test_gauge_total_granularity(
        self, billable_metric_test_common_setup, add_subscription_record_to_org
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
            metric_type=METRIC_TYPE.GAUGE,
            event_type=EVENT_TYPE.TOTAL,
        )
        METRIC_HANDLER_MAP[billable_metric.metric_type].create_continuous_aggregate(
            billable_metric
        )
        time_created = now_utc() - relativedelta(days=45)
        customer = setup_dict["customer"]
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
            cust_id=customer.customer_id,
            _quantity=19,
        )
        billing_plan = PlanVersion.objects.create(
            organization=setup_dict["org"],
            version=1,
            plan=setup_dict["plan"],
        )
        plan_component = PlanComponent.objects.create(
            billable_metric=billable_metric,
            plan_version=billing_plan,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.FREE,
            range_start=0,
            range_end=3,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.PER_UNIT,
            range_start=3,
            cost_per_batch=100,
            metric_units_per_batch=1,
        )
        now = now_utc()

        with (
            mock.patch(
                "metering_billing.models.now_utc",
                return_value=now - relativedelta(days=46),
            ),
            mock.patch(
                "metering_billing.tests.test_billable_metric.now_utc",
                return_value=now - relativedelta(days=46),
            ),
        ):
            subscription_record = add_subscription_record_to_org(
                setup_dict["org"],
                billing_plan,
                customer,
                now - relativedelta(days=46),
            )

        usage_revenue_dict = plan_component.calculate_total_revenue(subscription_record)
        assert usage_revenue_dict["revenue"] == Decimal(300)

    def test_gauge_daily_granularity(
        self, billable_metric_test_common_setup, add_subscription_record_to_org
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
            metric_type=METRIC_TYPE.GAUGE,
            granularity=METRIC_GRANULARITY.MONTH,
            proration=METRIC_GRANULARITY.DAY,
            event_type=EVENT_TYPE.TOTAL,
        )
        METRIC_HANDLER_MAP[billable_metric.metric_type].create_continuous_aggregate(
            billable_metric
        )
        time_created = now_utc() - relativedelta(days=45)
        customer = setup_dict["customer"]
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
            cust_id=customer.customer_id,
            _quantity=19,
        )
        billing_plan = PlanVersion.objects.create(
            organization=setup_dict["org"],
            version=1,
            plan=setup_dict["plan"],
        )
        plan_component = PlanComponent.objects.create(
            billable_metric=billable_metric,
            plan_version=billing_plan,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.FREE,
            range_start=0,
            range_end=3,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.PER_UNIT,
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
            subscription_record = add_subscription_record_to_org(
                setup_dict["org"], billing_plan, customer, time_created
            )
        usage_revenue_dict = plan_component.calculate_total_revenue(subscription_record)
        # 3 * (4-3) + 3* (5-3) + 3 * (6-3) = 18 user*days ... it costs 100 per 1 month of
        # user days, so should be between 18/28*100 and 18/31*100
        assert usage_revenue_dict["revenue"] >= Decimal(100) * (
            Decimal(18) / Decimal(31) - Decimal(3) / Decimal(31)
        )
        assert usage_revenue_dict["revenue"] <= Decimal(100) * Decimal(18) / Decimal(28)

    def test_rate_hourly_granularity(
        self, billable_metric_test_common_setup, add_subscription_record_to_org
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
        METRIC_HANDLER_MAP[billable_metric.metric_type].create_continuous_aggregate(
            billable_metric
        )
        time_created = now_utc() - relativedelta(days=14, hour=0)
        customer = setup_dict["customer"]
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
            cust_id=customer.customer_id,
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
            cust_id=customer.customer_id,
            _quantity=18,
        )
        billing_plan = PlanVersion.objects.create(
            organization=setup_dict["org"],
            version=1,
            plan=setup_dict["plan"],
        )
        plan_component = PlanComponent.objects.create(
            billable_metric=billable_metric,
            plan_version=billing_plan,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.FREE,
            range_start=0,
            range_end=3,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.PER_UNIT,
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
            subscription_record = add_subscription_record_to_org(
                setup_dict["org"],
                billing_plan,
                customer,
                now - relativedelta(days=31),
            )
        usage_revenue_dict = plan_component.calculate_total_revenue(subscription_record)
        # 1 dollar per for 64 rows - 3 free rows = 61 rows * 1 dollar = 61 dollars
        assert usage_revenue_dict["revenue"] == Decimal(61)

    def test_gauge_daily_granularity_delta_event(
        self, billable_metric_test_common_setup, add_subscription_record_to_org
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
            metric_type=METRIC_TYPE.GAUGE,
            granularity=METRIC_GRANULARITY.MONTH,
            event_type=EVENT_TYPE.DELTA,
            proration=METRIC_GRANULARITY.DAY,
        )
        METRIC_HANDLER_MAP[billable_metric.metric_type].create_continuous_aggregate(
            billable_metric
        )
        time_created = now_utc() - relativedelta(days=45)
        customer = setup_dict["customer"]
        event_times = [time_created + relativedelta(days=i) for i in range(8)]
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
            cust_id=customer.customer_id,
            _quantity=8,
        )
        billing_plan = PlanVersion.objects.create(
            organization=setup_dict["org"],
            version=1,
            plan=setup_dict["plan"],
        )
        plan_component = PlanComponent.objects.create(
            billable_metric=billable_metric,
            plan_version=billing_plan,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.FREE,
            range_start=0,
            range_end=3,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.PER_UNIT,
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
            subscription_record = add_subscription_record_to_org(
                setup_dict["org"], billing_plan, customer, time_created
            )

        usage_revenue_dict = plan_component.calculate_total_revenue(subscription_record)
        # 2 * (4-3) + 2* (5-3) + 2 * (6-3) = 12 user*days abvoe the free tier... it costs 100
        # per 1 month of user*days, so should be between 12/28*100 and 12/31*100
        assert Decimal(100) * Decimal(12) / Decimal(28) >= usage_revenue_dict["revenue"]
        assert (
            Decimal(100) * (Decimal(12) / Decimal(31) - Decimal(3) / Decimal(31))
            <= usage_revenue_dict["revenue"]
        )


@pytest.mark.django_db(transaction=True)
class TestCalculateMetricProrationForGauge:
    def test_proration_and_metric_granularity_sub_day(
        self, billable_metric_test_common_setup, add_subscription_record_to_org
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
            metric_type=METRIC_TYPE.GAUGE,
            granularity=METRIC_GRANULARITY.HOUR,
            proration=METRIC_GRANULARITY.MINUTE,
            event_type=EVENT_TYPE.TOTAL,
        )
        METRIC_HANDLER_MAP[billable_metric.metric_type].create_continuous_aggregate(
            billable_metric
        )
        time_created = now_utc() - relativedelta(days=45)
        customer = setup_dict["customer"]
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
            cust_id=customer.customer_id,
            _quantity=11,
        )
        billing_plan = PlanVersion.objects.create(
            organization=setup_dict["org"],
            version=1,
            plan=setup_dict["plan"],
        )
        plan_component = PlanComponent.objects.create(
            billable_metric=billable_metric,
            plan_version=billing_plan,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.FREE,
            range_start=0,
            range_end=1,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.PER_UNIT,
            range_start=1,
            cost_per_batch=100,
            metric_units_per_batch=1,
        )
        now = now_utc()
        time_created = now - relativedelta(days=45)
        with (
            mock.patch("metering_billing.models.now_utc", return_value=time_created),
            mock.patch(
                "metering_billing.tests.test_billable_metric.now_utc",
                return_value=time_created,
            ),
        ):
            subscription_record = add_subscription_record_to_org(
                setup_dict["org"],
                billing_plan,
                customer,
                time_created,
            )

        usage_revenue_dict = plan_component.calculate_total_revenue(subscription_record)
        calculated_amt = (Decimal(87) - Decimal(60)) / Decimal(60) * Decimal(100)
        assert abs(usage_revenue_dict["revenue"] - calculated_amt) < Decimal(0.01)

        response = setup_dict["client"].get(
            reverse("cost_analysis"),
            {
                "customer_id": customer.customer_id,
                "start_date": subscription_record.start_date.date(),
                "end_date": subscription_record.end_date.date(),
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
        self, billable_metric_test_common_setup, add_subscription_record_to_org
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
            metric_type=METRIC_TYPE.GAUGE,
            granularity=METRIC_GRANULARITY.DAY,
            proration=METRIC_GRANULARITY.HOUR,
            event_type=EVENT_TYPE.TOTAL,
        )
        METRIC_HANDLER_MAP[billable_metric.metric_type].create_continuous_aggregate(
            billable_metric
        )
        time_created = now_utc() - relativedelta(days=45)
        customer = setup_dict["customer"]
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
            cust_id=customer.customer_id,
            _quantity=11,
        )
        billing_plan = PlanVersion.objects.create(
            organization=setup_dict["org"],
            version=1,
            plan=setup_dict["plan"],
        )
        plan_component = PlanComponent.objects.create(
            billable_metric=billable_metric,
            plan_version=billing_plan,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.FREE,
            range_start=0,
            range_end=1,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.PER_UNIT,
            range_start=1,
            cost_per_batch=100,
            metric_units_per_batch=1,
        )
        now = now_utc()
        with (
            mock.patch("metering_billing.models.now_utc", return_value=time_created),
            mock.patch(
                "metering_billing.tests.test_billable_metric.now_utc",
                return_value=time_created,
            ),
        ):
            subscription_record = add_subscription_record_to_org(
                setup_dict["org"],
                billing_plan,
                customer,
                now - relativedelta(days=46),
            )

        usage_revenue_dict = plan_component.calculate_total_revenue(subscription_record)
        supposed_revenue = (Decimal(72) - Decimal(24)) / Decimal(24) * Decimal(100)
        assert abs(usage_revenue_dict["revenue"] - supposed_revenue) < Decimal(0.01)

        {}
        response = setup_dict["client"].get(
            reverse("cost_analysis"),
            {
                "customer_id": customer.customer_id,
                "start_date": subscription_record.start_date.date(),
                "end_date": subscription_record.end_date.date(),
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
        self, billable_metric_test_common_setup, add_subscription_record_to_org
    ):
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="api_key",
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
            metric_type=METRIC_TYPE.GAUGE,
            granularity=METRIC_GRANULARITY.MONTH,
            proration=METRIC_GRANULARITY.HOUR,
            event_type=EVENT_TYPE.TOTAL,
        )
        METRIC_HANDLER_MAP[billable_metric.metric_type].create_continuous_aggregate(
            billable_metric
        )
        time_created = now_utc() - relativedelta(months=3, days=21)
        customer = setup_dict["customer"]
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
            cust_id=customer.customer_id,
            _quantity=11,
        )
        billing_plan = PlanVersion.objects.create(
            organization=setup_dict["org"],
            version=1,
            plan=setup_dict["plan"],
        )
        plan_component = PlanComponent.objects.create(
            billable_metric=billable_metric,
            plan_version=billing_plan,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.FREE,
            range_start=0,
            range_end=1,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.PER_UNIT,
            range_start=1,
            cost_per_batch=100,
            metric_units_per_batch=1,
        )
        now = now_utc()
        tc = now - relativedelta(months=4, days=23)
        with (
            mock.patch("metering_billing.models.now_utc", return_value=tc),
            mock.patch(
                "metering_billing.tests.test_billable_metric.now_utc",
                return_value=tc,
            ),
        ):
            subscription_record = add_subscription_record_to_org(
                setup_dict["org"],
                billing_plan,
                customer,
                tc,
            )

        usage_revenue_dict = plan_component.calculate_total_revenue(subscription_record)
        assert Decimal(100) > usage_revenue_dict["revenue"] > Decimal(0)

        {}
        response = setup_dict["client"].get(
            reverse("cost_analysis"),
            {
                "customer_id": customer.customer_id,
                "start_date": subscription_record.start_date.date(),
                "end_date": subscription_record.end_date.date(),
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


@pytest.mark.django_db(transaction=True)
class TestCalculateMetricWithFilters:
    def test_count_unique_with_filters(
        self, billable_metric_test_common_setup, add_subscription_record_to_org
    ):
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
            usage_aggregation_type=METRIC_AGGREGATION.UNIQUE,
            metric_type=METRIC_TYPE.COUNTER,
        )
        METRIC_HANDLER_MAP[billable_metric.metric_type].create_continuous_aggregate(
            billable_metric
        )
        numeric_filter = NumericFilter.objects.create(
            organization=setup_dict["org"],
            property_name="test_filter_property",
            operator=NUMERIC_FILTER_OPERATORS.GT,
            comparison_value=10,
        )
        billable_metric.numeric_filters.add(numeric_filter)
        billable_metric.refresh_materialized_views()
        time_created = now_utc()
        customer = setup_dict["customer"]
        baker.make(
            Event,
            event_name="test_event",
            properties={"test_property": "foo", "test_filter_property": 11},
            organization=setup_dict["org"],
            time_created=time_created,
            cust_id=customer.customer_id,
            _quantity=5,
        )
        baker.make(
            Event,
            event_name="test_event",
            properties={"test_property": "bar", "test_filter_property": 11},
            organization=setup_dict["org"],
            time_created=time_created,
            cust_id=customer.customer_id,
            _quantity=5,
        )
        baker.make(
            Event,
            event_name="test_event",
            properties={"test_property": "baz", "test_filter_property": 9},
            organization=setup_dict["org"],
            time_created=time_created,
            cust_id=customer.customer_id,
            _quantity=5,
        )
        billing_plan = PlanVersion.objects.create(
            organization=setup_dict["org"],
            version=1,
            plan=setup_dict["plan"],
        )
        plan_component = PlanComponent.objects.create(
            billable_metric=billable_metric,
            plan_version=billing_plan,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.FREE,
            range_start=0,
            range_end=3,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.PER_UNIT,
            range_start=3,
            cost_per_batch=100,
            metric_units_per_batch=1,
        )
        now = now_utc()
        with (
            mock.patch(
                "metering_billing.models.now_utc",
                return_value=now - relativedelta(days=1),
            ),
            mock.patch(
                "metering_billing.tests.test_billable_metric.now_utc",
                return_value=now - relativedelta(days=1),
            ),
        ):
            subscription_record = add_subscription_record_to_org(
                setup_dict["org"],
                billing_plan,
                customer,
                now - relativedelta(days=1),
            )
        metric_usage = billable_metric.get_subscription_record_total_billable_usage(
            subscription_record
        )
        assert metric_usage == 2

    def test_gauge_total_granularity_with_filters(
        self, billable_metric_test_common_setup, add_subscription_record_to_org
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
            metric_type=METRIC_TYPE.GAUGE,
            event_type=EVENT_TYPE.TOTAL,
        )
        METRIC_HANDLER_MAP[billable_metric.metric_type].create_continuous_aggregate(
            billable_metric
        )
        numeric_filter = NumericFilter.objects.create(
            organization=setup_dict["org"],
            property_name="test_filter_property",
            operator=NUMERIC_FILTER_OPERATORS.EQ,
            comparison_value=10,
        )
        billable_metric.numeric_filters.add(numeric_filter)
        billable_metric.refresh_materialized_views()
        time_created = now_utc() - relativedelta(days=45)
        customer = setup_dict["customer"]
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
            cust_id=customer.customer_id,
            _quantity=20,
        )
        billing_plan = PlanVersion.objects.create(
            organization=setup_dict["org"],
            version=1,
            plan=setup_dict["plan"],
        )
        plan_component = PlanComponent.objects.create(
            billable_metric=billable_metric,
            plan_version=billing_plan,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.FREE,
            range_start=0,
            range_end=3,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.PER_UNIT,
            range_start=3,
            cost_per_batch=100,
            metric_units_per_batch=1,
        )
        now = now_utc()
        time_created = now - relativedelta(days=46)
        with (
            mock.patch("metering_billing.models.now_utc", return_value=time_created),
            mock.patch(
                "metering_billing.tests.test_billable_metric.now_utc",
                return_value=time_created,
            ),
        ):
            subscription_record = add_subscription_record_to_org(
                setup_dict["org"], billing_plan, customer, time_created
            )

        usage_revenue_dict = plan_component.calculate_total_revenue(subscription_record)
        assert usage_revenue_dict["revenue"] == Decimal(300)

    def test_gauge_daily_granularity_with_filters(
        self, billable_metric_test_common_setup, add_subscription_record_to_org
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
            event_type=EVENT_TYPE.TOTAL,
            usage_aggregation_type=METRIC_AGGREGATION.MAX,
            metric_type=METRIC_TYPE.GAUGE,
            granularity=METRIC_GRANULARITY.MONTH,
            proration=METRIC_GRANULARITY.DAY,
        )
        categorical_filter = CategoricalFilter.objects.create(
            organization=setup_dict["org"],
            property_name="test_filter_property",
            operator=CATEGORICAL_FILTER_OPERATORS.ISIN,
            comparison_value=["a", "b", "c"],
        )
        billable_metric.categorical_filters.add(categorical_filter)
        billable_metric.refresh_materialized_views()
        time_created = now_utc() - relativedelta(days=31)
        customer = setup_dict["customer"]
        event_times = [time_created + relativedelta(days=i) for i in range(21)]
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
            cust_id=customer.customer_id,
            _quantity=20,
        )
        billing_plan = PlanVersion.objects.create(
            organization=setup_dict["org"],
            version=1,
            plan=setup_dict["plan"],
        )
        plan_component = PlanComponent.objects.create(
            billable_metric=billable_metric,
            plan_version=billing_plan,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.FREE,
            range_start=0,
            range_end=3,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.PER_UNIT,
            range_start=3,
            cost_per_batch=100,
            metric_units_per_batch=1,
        )
        METRIC_HANDLER_MAP[billable_metric.metric_type].create_continuous_aggregate(
            billable_metric
        )
        with (
            mock.patch("metering_billing.models.now_utc", return_value=time_created),
            mock.patch(
                "metering_billing.tests.test_billable_metric.now_utc",
                return_value=time_created,
            ),
        ):
            subscription_record = add_subscription_record_to_org(
                setup_dict["org"], billing_plan, customer, time_created
            )
        usage_revenue_dict = plan_component.calculate_total_revenue(subscription_record)
        # 3 * (4-3) + 3* (5-3) + 3 * (6-3) = 18 user*days ... it costs 100 per 1 month of
        # user days, so should be between 18/28*100 and 18/31*100...\
        assert usage_revenue_dict["revenue"] >= Decimal(100) * (
            Decimal(18) / Decimal(31) - Decimal(3) / Decimal(31)
        )
        assert usage_revenue_dict["revenue"] <= Decimal(100) * Decimal(18) / Decimal(28)

    def test_rate_hourly_granularity_with_filters(
        self, billable_metric_test_common_setup, add_subscription_record_to_org
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
        METRIC_HANDLER_MAP[billable_metric.metric_type].create_continuous_aggregate(
            billable_metric
        )
        numeric_filter = CategoricalFilter.objects.create(
            organization=setup_dict["org"],
            property_name="test_filter_property",
            operator=CATEGORICAL_FILTER_OPERATORS.ISNOTIN,
            comparison_value=["a", "b", "c"],
        )
        billable_metric.categorical_filters.add(numeric_filter)
        billable_metric.refresh_materialized_views()
        time_created = now_utc() - relativedelta(days=14, hour=0)
        customer = setup_dict["customer"]

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
        )  # = 67 but 3 shouldn't count, 64 really
        baker.make(
            Event,
            event_name="rows_inserted",
            properties=iter(properties),
            organization=setup_dict["org"],
            time_created=iter(event_times),
            cust_id=customer.customer_id,
            _quantity=20,
        )
        # 65 in an hour, 5 days ago
        time_created = now_utc() - relativedelta(days=5, hour=0)
        event_times = [time_created + relativedelta(minutes=i) for i in range(20)]
        properties = (
            5 * [{"num_rows": 1}]
            + 3 * [{"num_rows": 2}]
            + 3 * [{"num_rows": 3}]
            + 3 * [{"num_rows": 4}]
            + 3 * [{"num_rows": 5}]
            + 3 * [{"num_rows": 6}]
        )  # = 65
        baker.make(
            Event,
            event_name="rows_inserted",
            properties=iter(properties),
            organization=setup_dict["org"],
            time_created=iter(event_times),
            cust_id=customer.customer_id,
            _quantity=20,
        )
        billing_plan = PlanVersion.objects.create(
            organization=setup_dict["org"],
            version=1,
            plan=setup_dict["plan"],
        )
        plan_component = PlanComponent.objects.create(
            billable_metric=billable_metric,
            plan_version=billing_plan,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.FREE,
            range_start=0,
            range_end=3,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.PER_UNIT,
            range_start=3,
            cost_per_batch=1,
            metric_units_per_batch=1,
        )
        now = now_utc()
        subscription_record = add_subscription_record_to_org(
            setup_dict["org"],
            billing_plan,
            customer,
            now - relativedelta(days=21),
        )
        usage_revenue_dict = plan_component.calculate_total_revenue(subscription_record)
        # 1 dollar per for 67 rows - 3 free rows - 3 uncoutned rows = 61 rows * 1 dollar =$61
        assert usage_revenue_dict["revenue"] == Decimal(62)


@pytest.mark.django_db(transaction=True)
class TestCustomSQLMetrics:
    def test_insert_custom(
        self, get_billable_metrics_in_org, billable_metric_test_common_setup
    ):
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )

        insert_billable_metric_payload = {
            "metric_type": METRIC_TYPE.CUSTOM,
            "metric_name": "test_billable_metric",
            "custom_sql": "SELECT COUNT(*) AS usage_qty FROM events",
        }

        response = setup_dict["client"].post(
            reverse("metric-list"),
            data=json.dumps(insert_billable_metric_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        print(response.data)
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0  # check that the response is not empty
        assert len(get_billable_metrics_in_org(setup_dict["org"])) == 1

    def test_count_all(
        self,
        get_billable_metrics_in_org,
        billable_metric_test_common_setup,
        add_subscription_record_to_org,
    ):
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )

        insert_billable_metric_payload = {
            "metric_type": METRIC_TYPE.CUSTOM,
            "metric_name": "test_billable_metric",
            "custom_sql": "SELECT COUNT(*) AS usage_qty FROM events",
        }

        response = setup_dict["client"].post(
            reverse("metric-list"),
            data=json.dumps(insert_billable_metric_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0  # check that the response is not empty
        assert len(get_billable_metrics_in_org(setup_dict["org"])) == 1

        billable_metric = Metric.objects.all().first()
        time_created = now_utc()
        customer = setup_dict["customer"]
        baker.make(
            Event,
            event_name="test_event",
            properties={"test_property": "foo"},
            organization=setup_dict["org"],
            time_created=time_created,
            cust_id=customer.customer_id,
            _quantity=5,
        )
        baker.make(
            Event,
            event_name="test_event",
            properties={"test_property": "bar"},
            organization=setup_dict["org"],
            time_created=time_created,
            cust_id=customer.customer_id,
            _quantity=5,
        )
        billing_plan = PlanVersion.objects.create(
            organization=setup_dict["org"],
            version=1,
            plan=setup_dict["plan"],
        )
        plan_component = PlanComponent.objects.create(
            billable_metric=billable_metric,
            plan_version=billing_plan,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.FREE,
            range_start=0,
            range_end=3,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.PER_UNIT,
            range_start=3,
            cost_per_batch=100,
            metric_units_per_batch=1,
        )
        now = now_utc()
        with (
            mock.patch(
                "metering_billing.models.now_utc",
                return_value=now - relativedelta(days=1),
            ),
            mock.patch(
                "metering_billing.tests.test_billable_metric.now_utc",
                return_value=now - relativedelta(days=1),
            ),
        ):
            subscription_record = add_subscription_record_to_org(
                setup_dict["org"],
                billing_plan,
                customer,
                now - relativedelta(days=1),
            )
        billable_metric.get_subscription_record_total_billable_usage(
            subscription_record
        )

        payload = {
            "name": "test_subscription",
            "start_date": now_utc() - relativedelta(days=5),
            "customer_id": customer.customer_id,
            "plan_id": billing_plan.plan.plan_id,
        }
        response = setup_dict["client"].post(
            reverse("subscription-add"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        total_usage = billable_metric.get_subscription_record_total_billable_usage(
            subscription_record
        )

        assert total_usage == 10

    def test_count_distinct(
        self,
        get_billable_metrics_in_org,
        billable_metric_test_common_setup,
        add_subscription_record_to_org,
    ):
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )

        insert_billable_metric_payload = {
            "metric_type": METRIC_TYPE.CUSTOM,
            "metric_name": "test_billable_metric",
            "custom_sql": "SELECT COUNT(DISTINCT properties ->> 'test_property') AS usage_qty FROM events",
        }

        response = setup_dict["client"].post(
            reverse("metric-list"),
            data=json.dumps(insert_billable_metric_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0  # check that the response is not empty
        assert len(get_billable_metrics_in_org(setup_dict["org"])) == 1

        billable_metric = Metric.objects.all().first()
        time_created = now_utc()
        customer = setup_dict["customer"]
        baker.make(
            Event,
            event_name="test_event",
            properties={"test_property": "foo"},
            organization=setup_dict["org"],
            time_created=time_created,
            cust_id=customer.customer_id,
            _quantity=5,
        )
        baker.make(
            Event,
            event_name="test_event",
            properties={"test_property": "bar"},
            organization=setup_dict["org"],
            time_created=time_created,
            cust_id=customer.customer_id,
            _quantity=5,
        )
        billing_plan = PlanVersion.objects.create(
            organization=setup_dict["org"],
            version=1,
            plan=setup_dict["plan"],
        )
        plan_component = PlanComponent.objects.create(
            billable_metric=billable_metric,
            plan_version=billing_plan,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.FREE,
            range_start=0,
            range_end=3,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.PER_UNIT,
            range_start=3,
            cost_per_batch=100,
            metric_units_per_batch=1,
        )
        now = now_utc()
        with (
            mock.patch(
                "metering_billing.models.now_utc",
                return_value=now - relativedelta(days=1),
            ),
            mock.patch(
                "metering_billing.tests.test_billable_metric.now_utc",
                return_value=now - relativedelta(days=1),
            ),
        ):
            subscription_record = add_subscription_record_to_org(
                setup_dict["org"],
                billing_plan,
                customer,
                now - relativedelta(days=1),
            )
        billable_metric.get_subscription_record_total_billable_usage(
            subscription_record
        )

        payload = {
            "name": "test_subscription",
            "start_date": now_utc() - relativedelta(days=5),
            "customer_id": customer.customer_id,
            "plan_id": billing_plan.plan.plan_id,
        }
        response = setup_dict["client"].post(
            reverse("subscription-add"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        total_usage = billable_metric.get_subscription_record_total_billable_usage(
            subscription_record
        )

        assert total_usage == 2

    def test_max_with_filters(
        self,
        get_billable_metrics_in_org,
        billable_metric_test_common_setup,
        add_subscription_record_to_org,
    ):
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )

        insert_billable_metric_payload = {
            "metric_type": METRIC_TYPE.CUSTOM,
            "metric_name": "test_billable_metric",
            "custom_sql": "SELECT MAX((properties ->> 'qty_property')::text::decimal) AS usage_qty FROM events WHERE properties ->> 'test_property' = 'foo'",
        }

        response = setup_dict["client"].post(
            reverse("metric-list"),
            data=json.dumps(insert_billable_metric_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0  # check that the response is not empty
        assert len(get_billable_metrics_in_org(setup_dict["org"])) == 1

        billable_metric = Metric.objects.all().first()
        time_created = now_utc()
        customer = setup_dict["customer"]
        baker.make(
            Event,
            event_name="test_event",
            properties={"test_property": "foo", "qty_property": 5},
            organization=setup_dict["org"],
            time_created=time_created,
            cust_id=customer.customer_id,
            _quantity=5,
        )
        baker.make(
            Event,
            event_name="test_event",
            properties={"test_property": "bar", "qty_property": 10},
            organization=setup_dict["org"],
            time_created=time_created,
            cust_id=customer.customer_id,
            _quantity=5,
        )
        billing_plan = PlanVersion.objects.create(
            organization=setup_dict["org"],
            version=1,
            plan=setup_dict["plan"],
        )
        plan_component = PlanComponent.objects.create(
            billable_metric=billable_metric,
            plan_version=billing_plan,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.FREE,
            range_start=0,
            range_end=3,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.PER_UNIT,
            range_start=3,
            cost_per_batch=100,
            metric_units_per_batch=1,
        )
        now = now_utc()
        with (
            mock.patch(
                "metering_billing.models.now_utc",
                return_value=now - relativedelta(days=1),
            ),
            mock.patch(
                "metering_billing.tests.test_billable_metric.now_utc",
                return_value=now - relativedelta(days=1),
            ),
        ):
            subscription_record = add_subscription_record_to_org(
                setup_dict["org"],
                billing_plan,
                customer,
                now - relativedelta(days=1),
            )
        billable_metric.get_subscription_record_total_billable_usage(
            subscription_record
        )

        payload = {
            "name": "test_subscription",
            "start_date": now_utc() - relativedelta(days=5),
            "customer_id": customer.customer_id,
            "plan_id": billing_plan.plan.plan_id,
        }
        response = setup_dict["client"].post(
            reverse("subscription-add"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        total_usage = billable_metric.get_subscription_record_total_billable_usage(
            subscription_record
        )

        assert total_usage == 5

    def test_cte_with_partitions(
        self,
        get_billable_metrics_in_org,
        billable_metric_test_common_setup,
        add_subscription_record_to_org,
    ):
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )

        insert_billable_metric_payload = {
            "metric_type": METRIC_TYPE.CUSTOM,
            "metric_name": "test_billable_metric",
            "custom_sql": """
            WITH new_filter AS (
                SELECT
                    properties ->> 'test_property' AS test_property,
                    SUM((properties ->> 'qty_property')::text::decimal)
                    OVER(PARTITION BY properties ->> 'test_property') AS qty_partition
                FROM events
            ), sum_per_partition AS (
                SELECT
                    SUM(qty_partition) AS total_sum,
                    test_property
                FROM
                    new_filter
                GROUP BY
                    test_property
                HAVING
                    SUM(qty_partition) < 250
            )
            SELECT
                MAX(total_sum) AS usage_qty
            FROM
                sum_per_partition
            """,
        }

        response = setup_dict["client"].post(
            reverse("metric-list"),
            data=json.dumps(insert_billable_metric_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0  # check that the response is not empty
        assert len(get_billable_metrics_in_org(setup_dict["org"])) == 1

        billable_metric = Metric.objects.all().first()
        time_created = now_utc()
        customer = setup_dict["customer"]
        baker.make(
            Event,
            event_name="test_event",
            properties={"test_property": "foo", "qty_property": 5},
            organization=setup_dict["org"],
            time_created=time_created,
            cust_id=customer.customer_id,
            _quantity=5,
        )
        baker.make(
            Event,
            event_name="test_event",
            properties={"test_property": "bar", "qty_property": 10},
            organization=setup_dict["org"],
            time_created=time_created,
            cust_id=customer.customer_id,
            _quantity=5,
        )
        billing_plan = PlanVersion.objects.create(
            organization=setup_dict["org"],
            version=1,
            plan=setup_dict["plan"],
        )
        plan_component = PlanComponent.objects.create(
            billable_metric=billable_metric,
            plan_version=billing_plan,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.FREE,
            range_start=0,
            range_end=3,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.PER_UNIT,
            range_start=3,
            cost_per_batch=100,
            metric_units_per_batch=1,
        )
        now = now_utc()
        with (
            mock.patch(
                "metering_billing.models.now_utc",
                return_value=now - relativedelta(days=1),
            ),
            mock.patch(
                "metering_billing.tests.test_billable_metric.now_utc",
                return_value=now - relativedelta(days=1),
            ),
        ):
            subscription_record = add_subscription_record_to_org(
                setup_dict["org"],
                billing_plan,
                customer,
                now - relativedelta(days=1),
            )
        billable_metric.get_subscription_record_total_billable_usage(
            subscription_record
        )

        payload = {
            "name": "test_subscription",
            "start_date": now_utc() - relativedelta(days=5),
            "customer_id": customer.customer_id,
            "plan_id": billing_plan.plan.plan_id,
        }
        response = setup_dict["client"].post(
            reverse("subscription-add"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        total_usage = billable_metric.get_subscription_record_total_billable_usage(
            subscription_record
        )

        assert total_usage == 125

    def test_realistic_use_case_with_end_dates(
        self,
        get_billable_metrics_in_org,
        billable_metric_test_common_setup,
        add_subscription_record_to_org,
    ):
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )

        insert_billable_metric_payload = {
            "metric_type": METRIC_TYPE.CUSTOM,
            "metric_name": "test_billable_metric",
            "custom_sql": """
            WITH experiment_key_days AS (
            SELECT
                properties ->> 'experiment_key' as experiment_key,
                date_trunc('day', time_created) AS day
            FROM
                events
            WHERE
                properties ->> 'status' = 'successful_refresh'
                AND (properties ->> 'assignment_volume')::text::decimal > 1000
                AND time_created < end_date
                AND date_trunc('day', time_created) > start_date - INTERVAL '2 days'
            )
            , second_table as (
            SELECT
                COUNT(DISTINCT day) AS num_days,
                experiment_key
            FROM experiment_key_days
            GROUP BY experiment_key
            )
            SELECT
                COUNT(*) AS usage_qty
            FROM
                second_table
            WHERE
                num_days >= 3
            """,
        }

        response = setup_dict["client"].post(
            reverse("metric-list"),
            data=json.dumps(insert_billable_metric_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0  # check that the response is not empty
        assert len(get_billable_metrics_in_org(setup_dict["org"])) == 1

        billable_metric = Metric.objects.all().first()
        time_created = now_utc()
        customer = setup_dict["customer"]
        baker.make(
            Event,
            event_name="test_event",
            properties={
                "experiment_key": "1",
                "status": "successful_refresh",
                "assignment_volume": 2000,
            },
            organization=setup_dict["org"],
            time_created=itertools.cycle(
                [time_created - relativedelta(days=i) for i in range(5)]
            ),
            cust_id=customer.customer_id,
            _quantity=5,
        )  # this one should count
        baker.make(
            Event,
            event_name="test_event",
            properties={
                "experiment_key": "2",
                "status": "successful_refresh",
                "assignment_volume": 2000,
            },
            organization=setup_dict["org"],
            time_created=itertools.cycle(
                [time_created - relativedelta(days=i) for i in range(2, 7)]
            ),
            cust_id=customer.customer_id,
            _quantity=5,
        )  # this one shouldn't as it goes before the start_date
        baker.make(
            Event,
            event_name="test_event",
            properties=itertools.cycle(
                [
                    {
                        "experiment_key": "3",
                        "status": "successful_refresh" if i < 3 else "failed_refresh",
                        "assignment_volume": 2000,
                    }
                    for i in range(5)
                ]
            ),
            organization=setup_dict["org"],
            time_created=itertools.cycle(
                [time_created - relativedelta(days=i) for i in range(5)]
            ),
            cust_id=customer.customer_id,
            _quantity=5,
        )  # this one should work as the failed refresh is before the start date
        baker.make(
            Event,
            event_name="test_event",
            properties=itertools.cycle(
                [
                    {
                        "experiment_key": "4",
                        "status": "successful_refresh" if i > 3 else "failed_refresh",
                        "assignment_volume": 2000,
                    }
                    for i in range(5)
                ]
            ),
            organization=setup_dict["org"],
            time_created=itertools.cycle(
                [time_created - relativedelta(days=i) for i in range(5)]
            ),
            cust_id=customer.customer_id,
            _quantity=5,
        )  # this one shouldnt as it fails
        baker.make(
            Event,
            event_name="test_event",
            properties=itertools.cycle(
                [
                    {
                        "experiment_key": "5",
                        "status": "successful_refresh",
                        "assignment_volume": 2000 if i != 2 else 50,
                    }
                    for i in range(5)
                ]
            ),
            organization=setup_dict["org"],
            time_created=itertools.cycle(
                [time_created - relativedelta(days=i) for i in range(5)]
            ),
            cust_id=customer.customer_id,
            _quantity=5,
        )  # this one also shouldnt as it doesn't have the volume on one of the days in the query
        billing_plan = PlanVersion.objects.create(
            organization=setup_dict["org"],
            version=1,
            plan=setup_dict["plan"],
        )
        plan_component = PlanComponent.objects.create(
            billable_metric=billable_metric,
            plan_version=billing_plan,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.FREE,
            range_start=0,
            range_end=3,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.PER_UNIT,
            range_start=3,
            cost_per_batch=100,
            metric_units_per_batch=1,
        )
        now = now_utc()
        with (
            mock.patch(
                "metering_billing.models.now_utc",
                return_value=now - relativedelta(days=1),
            ),
            mock.patch(
                "metering_billing.tests.test_billable_metric.now_utc",
                return_value=now - relativedelta(days=1),
            ),
        ):
            subscription_record = add_subscription_record_to_org(
                setup_dict["org"],
                billing_plan,
                customer,
                now - relativedelta(days=1),
            )
        billable_metric.get_subscription_record_total_billable_usage(
            subscription_record
        )

        payload = {
            "name": "test_subscription",
            "start_date": now_utc() - relativedelta(days=5),
            "customer_id": customer.customer_id,
            "plan_id": billing_plan.plan.plan_id,
        }
        response = setup_dict["client"].post(
            reverse("subscription-add"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        total_usage = billable_metric.get_subscription_record_total_billable_usage(
            subscription_record
        )

        assert total_usage == 2

    def test_reject_if_using_table_name(
        self,
        get_billable_metrics_in_org,
        billable_metric_test_common_setup,
        add_subscription_record_to_org,
    ):
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )

        insert_billable_metric_payload = {
            "metric_type": METRIC_TYPE.CUSTOM,
            "metric_name": "test_billable_metric",
            "custom_sql": """SELECT COUNT(*) AS usage_qty FROM \"metering_billing_usageevent\"""",
        }

        response = setup_dict["client"].post(
            reverse("metric-list"),
            data=json.dumps(insert_billable_metric_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert len(response.data) > 0  # check that the response is not empty
        assert len(get_billable_metrics_in_org(setup_dict["org"])) == 0

        insert_billable_metric_payload = {
            "metric_type": METRIC_TYPE.CUSTOM,
            "metric_name": "test_billable_metric",
            "custom_sql": """SELECT COUNT(*) AS usage_qty FROM metering_billing_usageevent""",
        }

        response = setup_dict["client"].post(
            reverse("metric-list"),
            data=json.dumps(insert_billable_metric_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert len(response.data) > 0  # check that the response is not empty
        assert len(get_billable_metrics_in_org(setup_dict["org"])) == 0

        insert_billable_metric_payload = {
            "metric_type": METRIC_TYPE.CUSTOM,
            "metric_name": "test_billable_metric",
            "custom_sql": """SELECT COUNT(*) AS usage_qty FROM metering_billing_customer""",
        }

        response = setup_dict["client"].post(
            reverse("metric-list"),
            data=json.dumps(insert_billable_metric_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert len(response.data) > 0  # check that the response is not empty
        assert len(get_billable_metrics_in_org(setup_dict["org"])) == 0


@pytest.mark.django_db(transaction=True)
class TestRegressions:
    def test_granularity_ratio_total_fails(
        self, billable_metric_test_common_setup, add_subscription_record_to_org
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
            metric_type=METRIC_TYPE.GAUGE,
            granularity=METRIC_GRANULARITY.TOTAL,
            proration=METRIC_GRANULARITY.MINUTE,
            event_type=EVENT_TYPE.TOTAL,
        )
        METRIC_HANDLER_MAP[billable_metric.metric_type].create_continuous_aggregate(
            billable_metric
        )
        time_created = now_utc() - relativedelta(days=45)
        customer = setup_dict["customer"]
        event_times = [
            time_created + relativedelta(days=1) + relativedelta(hour=23, minute=i)
            for i in range(55, 60)
        ]
        event_times += [
            time_created + relativedelta(days=2) + relativedelta(hour=0, minute=i)
            for i in range(6)
        ]
        properties = (
            3 * [{"number": 800}]  # 55-56, 56-57, 57-58 at 8
            + 2 * [{"number": 900}]  # 58-59, 59-60 at 9
            + 1 * [{"number": 1000}]  # 60-61 at 10
            + 1 * [{"number": 1100}]  # 61-62 at 11
            + 2 * [{"number": 600}]  # 62-63, 63-64 at 6
            + 1 * [{"number": 1200}]  # 64-65 at 12
            + [{"number": 0}]  # everything else back to 0
        )  # this should total 3*8 + 2*9 + 1*10 + 1*11 + 2*6 + 1*12 = 8700
        baker.make(
            Event,
            event_name="number_of_users",
            properties=iter(properties),
            organization=setup_dict["org"],
            time_created=iter(event_times),
            cust_id=customer.customer_id,
            _quantity=11,
        )
        billing_plan = PlanVersion.objects.create(
            organization=setup_dict["org"],
            version=1,
            plan=setup_dict["plan"],
        )
        plan_component = PlanComponent.objects.create(
            billable_metric=billable_metric,
            plan_version=billing_plan,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.PER_UNIT,
            range_start=0,
            cost_per_batch=100,
            metric_units_per_batch=1,
        )
        now = now_utc()
        time_created = now - relativedelta(days=45)
        with (
            mock.patch("metering_billing.models.now_utc", return_value=time_created),
            mock.patch(
                "metering_billing.tests.test_billable_metric.now_utc",
                return_value=time_created,
            ),
        ):
            subscription_record = add_subscription_record_to_org(
                setup_dict["org"],
                billing_plan,
                customer,
                time_created,
            )

        usage_revenue_dict = plan_component.calculate_total_revenue(subscription_record)
        assert usage_revenue_dict["revenue"] >= Decimal(8700) / (
            Decimal(60) * Decimal(24) * Decimal(31)
        ) * Decimal(100)
        assert usage_revenue_dict["revenue"] <= Decimal(8700) / (
            Decimal(60) * Decimal(24) * Decimal(28)
        ) * Decimal(100)
