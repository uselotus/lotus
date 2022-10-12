import uuid

import posthog
import pytest
from model_bakery import baker


@pytest.fixture(autouse=True)
def run_around_tests():
    # Code that will run before your test, for example:
    posthog.disabled = True
    # A test function will be run at this point
    yield
    # Code that will run after your test, for example:
    posthog.disabled = False


@pytest.fixture
def api_client_with_api_key_auth():
    from rest_framework.test import APIClient

    def do_api_client_with_api_key_auth(key):
        client = APIClient()
        client.credentials(HTTP_X_API_KEY=key)
        return client

    return do_api_client_with_api_key_auth


@pytest.fixture
def generate_org_and_api_key():
    from metering_billing.models import APIToken, Organization

    def do_generate_org_and_api_key():
        organization = baker.make(Organization)
        _, key = APIToken.objects.create_key(
            name="test-api-key", organization=organization
        )
        return organization, key

    return do_generate_org_and_api_key


@pytest.fixture
def add_customers_to_org():
    from metering_billing.models import Customer

    def do_add_customers_to_org(organization, n):
        customer_set = baker.make(
            Customer, _quantity=n, organization=organization, customer_id=uuid.uuid4
        )
        return customer_set

    return do_add_customers_to_org


@pytest.fixture
def get_customers_in_org():
    from metering_billing.models import Customer

    def do_get_customers_in_org(organization):
        return Customer.objects.filter(organization=organization)

    return do_get_customers_in_org


@pytest.fixture
def add_users_to_org():
    from metering_billing.models import User

    def do_add_users_to_org(organization, n):
        user_set = baker.make(User, _quantity=n, organization=organization)
        return user_set

    return do_add_users_to_org


@pytest.fixture
def create_events_with_org_customer():
    from metering_billing.models import Event

    def do_create_events_with_org_customer(organization, customer, n):
        event_set = baker.make(
            Event, _quantity=n, organization=organization, customer=customer
        )
        return event_set

    return do_create_events_with_org_customer


@pytest.fixture
def get_events_with_org_customer_id():
    from metering_billing.models import Event

    def do_get_events_with_org_customer_id(organization, customer_id):
        event_set = Event.objects.filter(
            organization=organization, customer__customer_id=customer_id
        )
        return event_set

    return do_get_events_with_org_customer_id


@pytest.fixture
def get_events_with_org():
    from metering_billing.models import Event

    def do_get_events_with_org(organization):
        event_set = Event.objects.filter(organization=organization)
        return event_set

    return do_get_events_with_org


@pytest.fixture
def add_billable_metrics_to_org():
    from metering_billing.models import BillableMetric

    def do_add_billable_metrics_to_org(organization, n):
        bm_set = baker.make(
            BillableMetric, _quantity=n, organization=organization, _fill_optional=True
        )
        return bm_set

    return do_add_billable_metrics_to_org


@pytest.fixture
def get_billable_metrics_in_org():
    from metering_billing.models import BillableMetric

    def do_get_billable_metrics_in_org(organization):
        return BillableMetric.objects.filter(organization=organization)

    return do_get_billable_metrics_in_org


@pytest.fixture
def add_subscriptions_to_org():
    from metering_billing.models import Subscription

    def do_add_subscriptions_to_org(organization, billing_plan, customer, n):
        bm_set = baker.make(
            Subscription,
            _quantity=n,
            organization=organization,
            billing_plan=billing_plan,
            customer=customer,
        )
        return bm_set

    return do_add_subscriptions_to_org


@pytest.fixture
def get_subscriptions_in_org():
    from metering_billing.models import Subscription

    def do_get_subscriptions_in_org(organization):
        return Subscription.objects.filter(organization=organization)

    return do_get_subscriptions_in_org
