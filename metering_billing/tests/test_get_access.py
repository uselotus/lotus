import datetime
import itertools
import json

import pytest
from dateutil.relativedelta import relativedelta
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from metering_billing.models import (
    BillableMetric,
    BillingPlan,
    Event,
    Feature,
    PlanComponent,
    Subscription,
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
        event_properties = (
            {"num_characters": 350, "peak_bandwith": 65},
            {"num_characters": 125, "peak_bandwith": 148},
            {"num_characters": 543, "peak_bandwith": 16},
        )
        event_set = baker.make(
            Event,
            organization=org,
            customer=customer,
            event_name="email_sent",
            time_created=datetime.datetime.now() - relativedelta(days=1),
            properties=itertools.cycle(event_properties),
            _quantity=3,
        )
        metric_set = baker.make(
            BillableMetric,
            organization=org,
            event_name="email_sent",
            property_name=itertools.cycle(["num_characters", "peak_bandwith", ""]),
            aggregation_type=itertools.cycle(["sum", "max", "count"]),
            _quantity=3,
        )
        setup_dict["metrics"] = metric_set
        billing_plan = baker.make(
            BillingPlan,
            organization=org,
            interval="month",
            name="test_plan",
            description="test_plan for testing",
            flat_rate=30.0,
            pay_in_advance=False,
        )
        plan_component_set = baker.make(
            PlanComponent,  # sum char (over), max bw (ok), count (ok)
            billable_metric=itertools.cycle(metric_set),
            free_metric_quantity=itertools.cycle([50, 0, 1]),
            cost_per_batch=itertools.cycle([5, 0.05, 2]),
            metric_units_per_batch=itertools.cycle([100, 1, 1]),
            max_metric_units=itertools.cycle([500, 250, 100]),
            _quantity=3,
        )
        feature_set = baker.make(
            Feature,
            organization=org,
            feature_name=itertools.cycle(["feature1", "feature2", "feature3"]),
            _quantity=3,
        )
        setup_dict["plan_components"] = plan_component_set
        billing_plan.components.add(*plan_component_set)
        billing_plan.save()
        setup_dict["features"] = feature_set
        billing_plan.features.add(*feature_set[:2])
        billing_plan.save()
        setup_dict["billing_plan"] = billing_plan
        subscription = baker.make(
            Subscription,
            organization=org,
            customer=customer,
            billing_plan=billing_plan,
            start_date=datetime.datetime.now().date() - relativedelta(days=3),
            status="active",
        )
        setup_dict["subscription"] = subscription
        return setup_dict

    return do_get_access_test_common_setup


@pytest.mark.django_db(transaction=True)
class TestGetAccess:
    def test_get_access_bm_allow(self, get_access_test_common_setup):
        setup_dict = get_access_test_common_setup(auth_method="api_key")

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "billable_metric_name": setup_dict["metrics"][1].billable_metric_name,
        }
        response = setup_dict["client"].get(reverse("customer_access"), payload)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["access"] == True

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "billable_metric_name": setup_dict["metrics"][2].billable_metric_name,
        }
        response = setup_dict["client"].get(reverse("customer_access"), payload)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["access"] == True

    def test_get_access_bm_deny(self, get_access_test_common_setup):
        setup_dict = get_access_test_common_setup(auth_method="api_key")

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "billable_metric_name": setup_dict["metrics"][0].billable_metric_name,
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

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "feature_name": setup_dict["features"][1].feature_name,
        }
        response = setup_dict["client"].get(reverse("customer_access"), payload)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["access"] == True

    def test_get_access_feature_deny(self, get_access_test_common_setup):
        setup_dict = get_access_test_common_setup(auth_method="api_key")

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "feature_name": setup_dict["features"][2].feature_name,
        }
        response = setup_dict["client"].get(reverse("customer_access"), payload)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["access"] == False
