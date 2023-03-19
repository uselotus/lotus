import itertools

import pytest
from dateutil.relativedelta import relativedelta
from django.urls import reverse
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APIClient

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
from metering_billing.utils.enums import EVENT_TYPE, METRIC_AGGREGATION, METRIC_TYPE


@pytest.fixture
def get_access_test_common_setup(
    generate_org_and_api_key,
    add_users_to_org,
    api_client_with_api_key_auth,
    add_customers_to_org,
    add_product_to_org,
    add_plan_to_product,
    add_subscription_record_to_org,
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
            cust_id=customer.customer_id,
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
            cust_id=customer.customer_id,
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
            plan=plan,
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
        add_subscription_record_to_org(
            organization=org,
            customer=customer,
            billing_plan=billing_plan,
            start_date=now_utc() - relativedelta(days=3),
        )
        return setup_dict

    return do_get_access_test_common_setup


@pytest.mark.django_db(transaction=True)
class TestGetAccess:
    def test_get_access_limit_bm_allow(self, get_access_test_common_setup):
        setup_dict = get_access_test_common_setup(auth_method="api_key")
        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "metric_id": setup_dict["allow_limit_metrics"][0].metric_id,
        }
        response = setup_dict["client"].get(reverse("metric_access"), payload)
        assert response.status_code == status.HTTP_200_OK
        response = response.json()
        assert (
            response["metric"]["event_name"]
            == setup_dict["allow_limit_metrics"][0].event_name
        )
        assert (
            response["access_per_subscription"][0]["metric_usage"]
            < response["access_per_subscription"][0]["metric_total_limit"]
        )
        assert response["access"] is True

    def test_get_access_limit_bm_deny(self, get_access_test_common_setup):
        setup_dict = get_access_test_common_setup(auth_method="api_key")

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "metric_id": setup_dict["deny_limit_metrics"][0].metric_id,
        }
        response = setup_dict["client"].get(reverse("metric_access"), payload)
        assert response.status_code == status.HTTP_200_OK
        response = response.json()
        assert (
            response["metric"]["event_name"]
            == setup_dict["deny_limit_metrics"][0].event_name
        )
        assert not (
            response["access_per_subscription"][0]["metric_usage"]
            < response["access_per_subscription"][0]["metric_total_limit"]
        )
        assert response["access"] is False

    def test_get_access_free_bm_allow(self, get_access_test_common_setup):
        setup_dict = get_access_test_common_setup(auth_method="api_key")

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "metric_id": setup_dict["allow_free_metrics"][0].metric_id,
        }
        response = setup_dict["client"].get(reverse("metric_access"), payload)
        assert response.status_code == status.HTTP_200_OK
        response = response.json()
        assert (
            response["metric"]["event_name"]
            == setup_dict["allow_free_metrics"][0].event_name
        )
        assert (
            response["access_per_subscription"][0]["metric_usage"]
            < response["access_per_subscription"][0]["metric_free_limit"]
        )
        assert response["access"] is True

    def test_get_access_free_bm_deny(self, get_access_test_common_setup):
        setup_dict = get_access_test_common_setup(auth_method="api_key")

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "metric_id": setup_dict["allow_limit_metrics"][0].metric_id,
        }
        response = setup_dict["client"].get(reverse("metric_access"), payload)
        assert response.status_code == status.HTTP_200_OK
        response = response.json()
        assert (
            response["metric"]["event_name"]
            == setup_dict["allow_limit_metrics"][0].event_name
        )
        assert not (
            response["access_per_subscription"][0]["metric_usage"]
            < response["access_per_subscription"][0]["metric_free_limit"]
        )
        assert (
            response["access"] is True
        )  # should still be true bc outer level checks for total

    def test_get_access_feature_allow(self, get_access_test_common_setup):
        setup_dict = get_access_test_common_setup(auth_method="api_key")

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "feature_id": setup_dict["features"][0].feature_id,
        }
        response = setup_dict["client"].get(reverse("feature_access"), payload)

        assert response.status_code == status.HTTP_200_OK
        feature = response.json()
        assert (
            feature["feature"]["feature_name"] == setup_dict["features"][0].feature_name
        )
        assert feature["access"] is True

    def test_get_access_feature_deny(self, get_access_test_common_setup):
        setup_dict = get_access_test_common_setup(auth_method="api_key")

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "feature_id": setup_dict["features"][1].feature_id,
        }
        response = setup_dict["client"].get(reverse("feature_access"), payload)
        assert response.status_code == status.HTTP_200_OK
        feature = response.json()
        assert (
            feature["feature"]["feature_name"] == setup_dict["features"][1].feature_name
        )
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
            plan=plan,
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
        SubscriptionRecord.create_subscription_record(
            start_date=now_utc() - relativedelta(days=3),
            end_date=None,
            billing_plan=billing_plan,
            customer=setup_dict["customer"],
            organization=setup_dict["org"],
            subscription_filters=None,
            is_new=True,
            quantity=1,
        )
        # initial value, just 1 user
        Event.objects.create(
            organization=setup_dict["org"],
            event_name="log_num_users",
            properties={"num_users": 1},
            time_created=now_utc() - relativedelta(days=2),
            idempotency_id="1",
        )
        # now we suddenly have 10!
        Event.objects.create(
            organization=setup_dict["org"],
            event_name="log_num_users",
            properties={"num_users": 10},
            time_created=now_utc() - relativedelta(days=1),
            idempotency_id="2",
        )
        # now we go back to 1, so should still have access
        Event.objects.create(
            organization=setup_dict["org"],
            event_name="log_num_users",
            properties={"num_users": 1},
            time_created=now_utc() - relativedelta(hours=6),
            idempotency_id="3",
        )
        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "metric_id": metric.metric_id,
        }
        response = setup_dict["client"].get(reverse("metric_access"), payload)
        assert response.status_code == status.HTTP_200_OK
        response = response.json()
        assert response["metric"]["event_name"] == "log_num_users"
        for sub in response["access_per_subscription"]:
            if sub["metric_total_limit"] > 0 or sub["metric_total_limit"] is None:
                assert sub["metric_usage"] < sub["metric_total_limit"]
        assert response["access"] is True
