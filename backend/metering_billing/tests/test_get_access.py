import itertools

import pytest
from dateutil.relativedelta import relativedelta
from django.urls import reverse
from metering_billing.models import (
    BillableMetric,
    Event,
    Feature,
    PlanComponent,
    PlanVersion,
    Subscription,
)
from metering_billing.utils import now_utc
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
        event_set = baker.make(
            Event,
            organization=org,
            customer=customer,
            event_name="email_sent",
            time_created=now_utc() - relativedelta(days=1),
            _quantity=5,
        )
        deny_limit_metric_set = baker.make(
            BillableMetric,
            organization=org,
            event_name="email_sent",
            property_name=itertools.cycle([""]),
            aggregation_type=itertools.cycle(["count"]),
            _quantity=1,
        )
        setup_dict["deny_limit_metrics"] = deny_limit_metric_set
        event_set = baker.make(
            Event,
            organization=org,
            customer=customer,
            event_name="api_call",
            time_created=now_utc() - relativedelta(days=1),
            _quantity=5,
        )
        allow_limit_metric_set = baker.make(
            BillableMetric,
            organization=org,
            event_name="api_call",
            property_name=itertools.cycle([""]),
            aggregation_type=itertools.cycle(["count"]),
            _quantity=1,
        )
        setup_dict["allow_limit_metrics"] = allow_limit_metric_set
        allow_free_metric_set = baker.make(
            BillableMetric,
            organization=org,
            event_name="bogus_event",
            property_name=itertools.cycle([""]),
            aggregation_type=itertools.cycle(["count"]),
            _quantity=1,
        )
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
        plan_component_set = baker.make(
            PlanComponent,  # sum char (over), max bw (ok), count (ok)
            billable_metric=itertools.cycle(
                deny_limit_metric_set + allow_limit_metric_set + allow_free_metric_set
            ),
            free_metric_units=itertools.cycle([1, 1, 20]),
            cost_per_batch=itertools.cycle([10, 10, 10]),
            metric_units_per_batch=itertools.cycle([1, 1, 1]),
            max_metric_units=itertools.cycle([3, 6, 20]),
            _quantity=3,
        )
        feature_set = baker.make(
            Feature,
            organization=org,
            feature_name=itertools.cycle(["feature1", "feature2"]),
            _quantity=2,
        )
        setup_dict["plan_components"] = plan_component_set
        billing_plan.components.add(*plan_component_set)
        billing_plan.save()
        setup_dict["features"] = feature_set
        billing_plan.features.add(*feature_set[:1])
        billing_plan.save()
        setup_dict["billing_plan"] = billing_plan
        subscription = baker.make(
            Subscription,
            organization=org,
            customer=customer,
            billing_plan=billing_plan,
            start_date=now_utc().date() - relativedelta(days=3),
            status="active",
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
            "event_limit_type": "total",
        }
        response = setup_dict["client"].get(reverse("customer_access"), payload)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["access"] == True

    def test_get_access_limit_bm_deny(self, get_access_test_common_setup):
        setup_dict = get_access_test_common_setup(auth_method="api_key")

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "event_name": setup_dict["deny_limit_metrics"][0].event_name,
            "event_limit_type": "total",
        }
        response = setup_dict["client"].get(reverse("customer_access"), payload)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["access"] == False

    def test_get_access_free_bm_allow(self, get_access_test_common_setup):
        setup_dict = get_access_test_common_setup(auth_method="api_key")

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "event_name": setup_dict["allow_free_metrics"][0].event_name,
            "event_limit_type": "free",
        }
        response = setup_dict["client"].get(reverse("customer_access"), payload)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["access"] == True

    def test_get_access_free_bm_deny(self, get_access_test_common_setup):
        setup_dict = get_access_test_common_setup(auth_method="api_key")

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "event_name": setup_dict["allow_limit_metrics"][0].event_name,
            "event_limit_type": "free",
        }
        response = setup_dict["client"].get(reverse("customer_access"), payload)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["access"] == False

    def test_get_access_feature_allow(self, get_access_test_common_setup):
        setup_dict = get_access_test_common_setup(auth_method="api_key")

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "feature_name": setup_dict["features"][0].feature_name,
        }
        response = setup_dict["client"].get(reverse("customer_access"), payload)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["access"] == True

    def test_get_access_feature_deny(self, get_access_test_common_setup):
        setup_dict = get_access_test_common_setup(auth_method="api_key")

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "feature_name": setup_dict["features"][1].feature_name,
        }
        response = setup_dict["client"].get(reverse("customer_access"), payload)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["access"] == False
