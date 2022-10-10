import itertools
import json
from datetime import datetime, timedelta

import pytest
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from djmoney.money import Money
from metering_billing.models import (
    BillableMetric,
    BillingPlan,
    PlanComponent,
    Subscription,
)
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APIClient


@pytest.fixture
def subscription_test_common_setup(
    generate_org_and_api_key,
    add_users_to_org,
    api_client_with_api_key_auth,
    add_subscriptions_to_org,
    add_customers_to_org,
):
    def do_subscription_test_common_setup(
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
            PlanComponent,
            billable_metric=itertools.cycle(metric_set),
            free_metric_units=itertools.cycle([50, 0, 1]),
            cost_per_batch=itertools.cycle([5, 0.05, 2]),
            metric_units_per_batch=itertools.cycle([100, 1, 1]),
            _quantity=3,
        )
        setup_dict["plan_components"] = plan_component_set
        billing_plan.components.add(*plan_component_set)
        billing_plan.save()
        setup_dict["billing_plan"] = billing_plan

        (customer,) = add_customers_to_org(org, n=1)
        if num_subscriptions > 0:
            setup_dict["org_subscriptions"] = add_subscriptions_to_org(
                org, billing_plan, customer, n=num_subscriptions
            )
        payload = {
            "name": "test_subscription",
            "balance": 30,
            "start_date": datetime.now().date() - timedelta(days=35),
            "status": "active",
            "customer_id": customer.customer_id,
            "billing_plan_id": billing_plan.billing_plan_id,
        }
        setup_dict["payload"] = payload
        setup_dict["customer"] = customer

        return setup_dict

    return do_subscription_test_common_setup


@pytest.mark.django_db(transaction=True)
class TestInsertSubscription:
    """Testing the POST of subscription endpoint:
    POST: Return list of subscriptions associated with the organization with API key / user.
    partitions:
        auth_method: api_key, session_auth, both
        num_subscriptions_before_insert: 0, >0
        user_org_and_api_key_org_different: true, false
        subscription_id
    """

    def test_api_key_can_create_subscription_empty_before(
        self, subscription_test_common_setup, get_subscriptions_in_org
    ):
        # covers num_subscriptions_before_insert = 0, has_org_api_key=true, user_in_org=true, user_org_and_api_key_org_different=false
        num_subscriptions = 0
        setup_dict = subscription_test_common_setup(
            num_subscriptions=num_subscriptions,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )

        response = setup_dict["client"].post(
            reverse("subscription-list"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0  # check that the response is not empty
        assert len(get_subscriptions_in_org(setup_dict["org"])) == 1

    def test_session_auth_can_create_subscription_nonempty_before(
        self, subscription_test_common_setup, get_subscriptions_in_org
    ):
        # covers num_subscriptions_before_insert = 0, has_org_api_key=true, user_in_org=true, user_org_and_api_key_org_different=false, authenticated=true
        num_subscriptions = 5
        setup_dict = subscription_test_common_setup(
            num_subscriptions=num_subscriptions,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )

        response = setup_dict["client"].post(
            reverse("subscription-list"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0
        assert len(get_subscriptions_in_org(setup_dict["org"])) == num_subscriptions + 1

    def test_user_org_and_api_key_different_reject_creation(
        self, subscription_test_common_setup, get_subscriptions_in_org
    ):
        # covers user_org_and_api_key_org_different = True
        num_subscriptions = 3
        setup_dict = subscription_test_common_setup(
            num_subscriptions=num_subscriptions,
            auth_method="both",
            user_org_and_api_key_org_different=True,
        )

        response = setup_dict["client"].post(
            reverse("subscription-list"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_406_NOT_ACCEPTABLE
        assert len(get_subscriptions_in_org(setup_dict["org"])) == num_subscriptions

    def test_deny_overlapping_subscriptions(
        self, subscription_test_common_setup, get_subscriptions_in_org
    ):
        # covers user_org_and_api_key_org_different = True
        num_subscriptions = 0
        setup_dict = subscription_test_common_setup(
            num_subscriptions=num_subscriptions,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )
        Subscription.objects.create(
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
            billing_plan=setup_dict["billing_plan"],
            status="active",
            start_date=datetime.now().date() - timedelta(days=20),
        )

        response = setup_dict["client"].post(
            reverse("subscription-list"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert len(get_subscriptions_in_org(setup_dict["org"])) == num_subscriptions + 1

    def test_deny_customer_and_bp_different_currency(
        self, subscription_test_common_setup, get_subscriptions_in_org
    ):
        # covers user_org_and_api_key_org_different = True
        num_subscriptions = 3
        setup_dict = subscription_test_common_setup(
            num_subscriptions=num_subscriptions,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )
        setup_dict["customer"].balance = Money(0, "GBP")
        setup_dict["customer"].save()

        response = setup_dict["client"].post(
            reverse("subscription-list"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert len(get_subscriptions_in_org(setup_dict["org"])) == num_subscriptions
