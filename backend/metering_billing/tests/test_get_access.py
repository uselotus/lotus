import itertools

import pytest
from dateutil.relativedelta import relativedelta
from django.urls import reverse
from metering_billing.aggregation.billable_metrics import METRIC_HANDLER_MAP
from metering_billing.models import (
    Event,
    Feature,
    Metric,
    PlanComponent,
    PlanVersion,
    PriceTier,
    SubscriptionRecord,
)
from metering_billing.utils import now_utc
from metering_billing.utils.enums import (
    EVENT_TYPE,
    METRIC_AGGREGATION,
    METRIC_TYPE,
)
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APIClient


@pytest.fixture
def get_access_test_common_setup(
    generate_org_and_api_key,
    add_users_to_org,
    api_client_with_api_key_auth,
    add_customers_to_org,
    add_product_to_org,
    add_plan_to_product,
    add_subscription_to_org,
):
    def do_get_access_test_common_setup(*, auth_method):
        setup_dict = {}
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
            (user,) = add_users_to_org(org, n=1)
            client.force_authenticate(user=user)
            setup_dict["user"] = user
        setup_dict["client"] = client
        (customer,) = add_customers_to_org(org, n=1)
        setup_dict["customer"] = customer
        baker.make(
            Event,
            organization=org,
            customer=customer,
            event_name="email_sent",
            time_created=now_utc() - relativedelta(days=1),
            _quantity=5,
        )
        deny_limit_metric_set = baker.make(
            Metric,
            organization=org,
            billable_metric_name="email_sent",
            event_name="email_sent",
            property_name=itertools.cycle([None]),
            usage_aggregation_type=itertools.cycle(["count"]),
            _quantity=1,
        )
        METRIC_HANDLER_MAP[
            deny_limit_metric_set[0].metric_type
        ].create_continuous_aggregate(deny_limit_metric_set[0])
        setup_dict["deny_limit_metrics"] = deny_limit_metric_set
        baker.make(
            Event,
            organization=org,
            customer=customer,
            event_name="api_call",
            time_created=now_utc() - relativedelta(days=1),
            _quantity=5,
        )
        allow_limit_metric_set = baker.make(
            Metric,
            organization=org,
            billable_metric_name="api_call",
            event_name="api_call",
            property_name=itertools.cycle([None]),
            usage_aggregation_type=itertools.cycle(["count"]),
            _quantity=1,
        )
        METRIC_HANDLER_MAP[
            allow_limit_metric_set[0].metric_type
        ].create_continuous_aggregate(allow_limit_metric_set[0])
        setup_dict["allow_limit_metrics"] = allow_limit_metric_set
        allow_free_metric_set = baker.make(
            Metric,
            organization=org,
            billable_metric_name="bogus",
            event_name="bogus_event",
            property_name=itertools.cycle([None]),
            usage_aggregation_type=itertools.cycle(["count"]),
            _quantity=1,
        )
        METRIC_HANDLER_MAP[
            allow_free_metric_set[0].metric_type
        ].create_continuous_aggregate(allow_free_metric_set[0])
        setup_dict["allow_free_metrics"] = allow_free_metric_set
        product = add_product_to_org(org)
        plan = add_plan_to_product(product)
        billing_plan = baker.make(
            PlanVersion,
            organization=org,
            description="test_plan for testing",
            plan=plan,
            flat_rate=30.0,
        )
        metric_set = (
            deny_limit_metric_set + allow_limit_metric_set + allow_free_metric_set
        )
        # THIS IS FOR NO SEPARATE_BY
        for i, (fmu, cpb, mupb, range_end) in enumerate(
            zip([1, 1, 20], [10, 10, 10], [1, 1, 1], [3, 6, 20])
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
                range_end=range_end,
                cost_per_batch=cpb,
                metric_units_per_batch=mupb,
            )
        feature_set = baker.make(
            Feature,
            organization=org,
            feature_name=itertools.cycle(["feature1", "feature2"]),
            _quantity=2,
        )
        setup_dict["features"] = feature_set
        billing_plan.features.add(*feature_set[:1])
        billing_plan.save()
        setup_dict["billing_plan"] = billing_plan
        subscription, subscription_record = add_subscription_to_org(
            organization=org,
            customer=customer,
            billing_plan=billing_plan,
            start_date=now_utc() - relativedelta(days=3),
        )
        setup_dict["subscription"] = subscription
        return setup_dict

    return do_get_access_test_common_setup


@pytest.mark.django_db(transaction=True)
class TestGetAccess:
    def test_get_access_limit_bm_allow(self, get_access_test_common_setup):
        setup_dict = get_access_test_common_setup(auth_method="api_key")
        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "event_name": setup_dict["allow_limit_metrics"][0].event_name,
        }
        response = setup_dict["client"].get(reverse("customer_metric_access"), payload)
        assert response.status_code == status.HTTP_200_OK
        response = response.json()
        assert len(response) == 1
        assert (
            response[0]["usage_per_component"][0]["event_name"]
            == setup_dict["allow_limit_metrics"][0].event_name
        )
        assert (
            response[0]["usage_per_component"][0]["metric_usage"]
            < response[0]["usage_per_component"][0]["metric_total_limit"]
        )

    def test_get_access_limit_bm_deny(self, get_access_test_common_setup):
        setup_dict = get_access_test_common_setup(auth_method="api_key")

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "event_name": setup_dict["deny_limit_metrics"][0].event_name,
        }
        response = setup_dict["client"].get(reverse("customer_metric_access"), payload)
        assert response.status_code == status.HTTP_200_OK
        response = response.json()
        assert len(response) == 1
        assert (
            response[0]["usage_per_component"][0]["event_name"]
            == setup_dict["deny_limit_metrics"][0].event_name
        )
        assert (
            response[0]["usage_per_component"][0]["metric_usage"]
            < response[0]["usage_per_component"][0]["metric_total_limit"]
        ) is False

    def test_get_access_free_bm_allow(self, get_access_test_common_setup):
        setup_dict = get_access_test_common_setup(auth_method="api_key")

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "event_name": setup_dict["allow_free_metrics"][0].event_name,
        }
        response = setup_dict["client"].get(reverse("customer_metric_access"), payload)

        assert response.status_code == status.HTTP_200_OK
        response = response.json()
        assert len(response) == 1
        assert (
            response[0]["usage_per_component"][0]["event_name"]
            == setup_dict["allow_free_metrics"][0].event_name
        )
        assert (
            response[0]["usage_per_component"][0]["metric_usage"]
            < response[0]["usage_per_component"][0]["metric_free_limit"]
        )

    def test_get_access_free_bm_deny(self, get_access_test_common_setup):
        setup_dict = get_access_test_common_setup(auth_method="api_key")

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "event_name": setup_dict["allow_limit_metrics"][0].event_name,
        }
        response = setup_dict["client"].get(reverse("customer_metric_access"), payload)
        assert response.status_code == status.HTTP_200_OK
        response = response.json()
        assert len(response) == 1
        assert (
            response[0]["usage_per_component"][0]["event_name"]
            == setup_dict["allow_limit_metrics"][0].event_name
        )
        assert (
            response[0]["usage_per_component"][0]["metric_usage"]
            < response[0]["usage_per_component"][0]["metric_free_limit"]
        ) is False

    def test_get_access_feature_allow(self, get_access_test_common_setup):
        setup_dict = get_access_test_common_setup(auth_method="api_key")

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "feature_name": setup_dict["features"][0].feature_name,
        }
        response = setup_dict["client"].get(reverse("customer_feature_access"), payload)

        assert response.status_code == status.HTTP_200_OK
        feature = response.json()
        assert len(feature) == 1
        feature = feature[0]
        assert feature["feature_name"] == setup_dict["features"][0].feature_name

    def test_get_access_feature_deny(self, get_access_test_common_setup):
        setup_dict = get_access_test_common_setup(auth_method="api_key")

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "feature_name": setup_dict["features"][1].feature_name,
        }
        response = setup_dict["client"].get(reverse("customer_feature_access"), payload)

        assert response.status_code == status.HTTP_200_OK
        feature = response.json()[0]
        assert feature["access"] is False

    def test_get_access_gauge_with_max_reached_previously(
        self, get_access_test_common_setup, add_product_to_org, add_plan_to_product
    ):
        setup_dict = get_access_test_common_setup(auth_method="api_key")
        product = add_product_to_org(setup_dict["org"])
        plan = add_plan_to_product(product)
        billing_plan = baker.make(
            PlanVersion,
            organization=setup_dict["org"],
            description="test_plan for testing",
            plan=plan,
            flat_rate=30.0,
        )
        metric = Metric.objects.create(
            organization=setup_dict["org"],
            event_name="log_num_users",
            property_name="num_users",
            usage_aggregation_type=METRIC_AGGREGATION.MAX,
            metric_type=METRIC_TYPE.GAUGE,
            event_type=EVENT_TYPE.TOTAL,
        )
        METRIC_HANDLER_MAP[metric.metric_type].create_continuous_aggregate(metric)
        plan_component = PlanComponent.objects.create(
            billable_metric=metric,
            plan_version=billing_plan,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.PER_UNIT,
            range_start=0,
            range_end=10,
            cost_per_batch=5,
            metric_units_per_batch=1,
        )
        SubscriptionRecord.objects.create(
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
            billing_plan=billing_plan,
            start_date=now_utc() - relativedelta(days=3),
        )
        # initial value, just 1 user
        Event.objects.create(
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
            event_name="log_num_users",
            properties={"num_users": 1},
            time_created=now_utc() - relativedelta(days=2),
            idempotency_id="1",
        )
        # now we suddenly have 10!
        Event.objects.create(
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
            event_name="log_num_users",
            properties={"num_users": 10},
            time_created=now_utc() - relativedelta(days=1),
            idempotency_id="2",
        )
        # now we go back to 1, so should still have access
        Event.objects.create(
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
            event_name="log_num_users",
            properties={"num_users": 1},
            time_created=now_utc() - relativedelta(hours=6),
            idempotency_id="3",
        )

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "event_name": metric.event_name,
        }
        response = setup_dict["client"].get(reverse("customer_metric_access"), payload)

        assert response.status_code == status.HTTP_200_OK
        response = [
            x
            for x in response.json()
            if x["plan_id"] == "plan_" + billing_plan.plan.plan_id.hex
        ]
        assert len(response) == 1
        assert response[0]["usage_per_component"][0]["event_name"] == "log_num_users"
        assert (
            response[0]["usage_per_component"][0]["metric_usage"]
            < response[0]["usage_per_component"][0]["metric_total_limit"]
        )


@pytest.mark.django_db(transaction=True)
class TestGetAccessWithMetricID:
    def test_get_access_limit_bm_allow(self, get_access_test_common_setup):
        setup_dict = get_access_test_common_setup(auth_method="api_key")
        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "metric_id": "metric_" + setup_dict["allow_limit_metrics"][0].metric_id.hex,
        }
        response = setup_dict["client"].get(reverse("customer_metric_access"), payload)
        assert response.status_code == status.HTTP_200_OK
        response = response.json()
        assert len(response) == 1
        assert (
            response[0]["usage_per_component"][0]["event_name"]
            == setup_dict["allow_limit_metrics"][0].event_name
        )
        assert (
            response[0]["usage_per_component"][0]["metric_usage"]
            < response[0]["usage_per_component"][0]["metric_total_limit"]
        )

    def test_get_access_limit_bm_deny(self, get_access_test_common_setup):
        setup_dict = get_access_test_common_setup(auth_method="api_key")

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "metric_id": "metric_" + setup_dict["deny_limit_metrics"][0].metric_id.hex,
        }
        response = setup_dict["client"].get(reverse("customer_metric_access"), payload)
        assert response.status_code == status.HTTP_200_OK
        response = response.json()
        assert len(response) == 1
        assert (
            response[0]["usage_per_component"][0]["event_name"]
            == setup_dict["deny_limit_metrics"][0].event_name
        )
        assert (
            response[0]["usage_per_component"][0]["metric_usage"]
            < response[0]["usage_per_component"][0]["metric_total_limit"]
        ) is False

    def test_get_access_free_bm_allow(self, get_access_test_common_setup):
        setup_dict = get_access_test_common_setup(auth_method="api_key")

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "metric_id": "metric_" + setup_dict["allow_free_metrics"][0].metric_id.hex,
        }
        response = setup_dict["client"].get(reverse("customer_metric_access"), payload)

        assert response.status_code == status.HTTP_200_OK
        response = response.json()
        assert len(response) == 1
        assert (
            response[0]["usage_per_component"][0]["event_name"]
            == setup_dict["allow_free_metrics"][0].event_name
        )
        assert (
            response[0]["usage_per_component"][0]["metric_usage"]
            < response[0]["usage_per_component"][0]["metric_free_limit"]
        )

    def test_get_access_free_bm_deny(self, get_access_test_common_setup):
        setup_dict = get_access_test_common_setup(auth_method="api_key")

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "metric_id": "metric_" + setup_dict["allow_limit_metrics"][0].metric_id.hex,
        }
        response = setup_dict["client"].get(reverse("customer_metric_access"), payload)
        assert response.status_code == status.HTTP_200_OK
        response = response.json()
        assert len(response) == 1
        assert (
            response[0]["usage_per_component"][0]["event_name"]
            == setup_dict["allow_limit_metrics"][0].event_name
        )
        assert (
            response[0]["usage_per_component"][0]["metric_usage"]
            < response[0]["usage_per_component"][0]["metric_free_limit"]
        ) is False

    def test_get_access_gauge_with_max_reached_previously(
        self, get_access_test_common_setup, add_product_to_org, add_plan_to_product
    ):
        setup_dict = get_access_test_common_setup(auth_method="api_key")
        product = add_product_to_org(setup_dict["org"])
        plan = add_plan_to_product(product)
        billing_plan = baker.make(
            PlanVersion,
            organization=setup_dict["org"],
            description="test_plan for testing",
            plan=plan,
            flat_rate=30.0,
        )
        metric = Metric.objects.create(
            organization=setup_dict["org"],
            event_name="log_num_users",
            property_name="num_users",
            usage_aggregation_type=METRIC_AGGREGATION.MAX,
            metric_type=METRIC_TYPE.GAUGE,
            event_type=EVENT_TYPE.TOTAL,
        )
        METRIC_HANDLER_MAP[metric.metric_type].create_continuous_aggregate(metric)
        plan_component = PlanComponent.objects.create(
            billable_metric=metric,
            plan_version=billing_plan,
        )
        PriceTier.objects.create(
            plan_component=plan_component,
            type=PriceTier.PriceTierType.PER_UNIT,
            range_start=0,
            range_end=10,
            cost_per_batch=5,
            metric_units_per_batch=1,
        )
        SubscriptionRecord.objects.create(
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
            billing_plan=billing_plan,
            start_date=now_utc() - relativedelta(days=3),
        )
        # initial value, just 1 user
        Event.objects.create(
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
            event_name="log_num_users",
            properties={"num_users": 1},
            time_created=now_utc() - relativedelta(days=2),
            idempotency_id="1",
        )
        # now we suddenly have 10!
        Event.objects.create(
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
            event_name="log_num_users",
            properties={"num_users": 10},
            time_created=now_utc() - relativedelta(days=1),
            idempotency_id="2",
        )
        # now we go back to 1, so should still have access
        Event.objects.create(
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
            event_name="log_num_users",
            properties={"num_users": 1},
            time_created=now_utc() - relativedelta(hours=6),
            idempotency_id="3",
        )

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "metric_id": "metric_" + metric.metric_id.hex,
        }
        response = setup_dict["client"].get(reverse("customer_metric_access"), payload)

        assert response.status_code == status.HTTP_200_OK
        response = [
            x
            for x in response.json()
            if x["plan_id"] == "plan_" + billing_plan.plan.plan_id.hex
        ]
        assert len(response) == 1
        assert response[0]["usage_per_component"][0]["event_name"] == "log_num_users"
        assert (
            response[0]["usage_per_component"][0]["metric_usage"]
            < response[0]["usage_per_component"][0]["metric_total_limit"]
        )
