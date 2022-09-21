import itertools
import json
import uuid
from datetime import datetime, timedelta

import pytest
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from lotus.urls import router
from metering_billing.models import (
    BillableMetric,
    BillingPlan,
    Event,
    Invoice,
    Organization,
    PlanComponent,
    Subscription,
    User,
)
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APIClient


@pytest.fixture
def event_preview_test_common_setup(
    generate_org_and_api_key,
    add_users_to_org,
    api_client_with_api_key_auth,
    add_subscriptions_to_org,
    add_customers_to_org,
):
    def do_event_preview_test_common_setup(
        *, num_subscriptions, auth_method, user_org_and_api_key_org_different
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
        (customer,) = add_customers_to_org(org, n=1)
        setup_dict["customer"] = customer

        return setup_dict

    return do_event_preview_test_common_setup


@pytest.mark.django_db(transaction=True)
class TestEventPreview:
    """Testing the Event Preview Endpoint"""

    def test_returns_correct_paginated_results(
        self, event_preview_test_common_setup, create_events_with_org_customer
    ):
        num_subscriptions = 0
        setup_dict = event_preview_test_common_setup(
            num_subscriptions=num_subscriptions,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )
        create_events_with_org_customer(setup_dict["org"], setup_dict["customer"], 400)

        payload = {
            "page": 1,
        }
        response = setup_dict["client"].get(reverse("event_preview"), payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        events = data["events"]
        total_pages = data["total_pages"]
        assert len(events) == 20
        assert total_pages == 20
