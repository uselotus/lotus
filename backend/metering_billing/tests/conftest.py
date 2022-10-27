import uuid

import posthog
import pytest
from metering_billing.utils import now_utc
from metering_billing.utils.enums import *
from model_bakery import baker


@pytest.fixture(autouse=True)
def run_around_tests():
    # Code that will run before your test, for example:
    posthog.disabled = True
    # A test function will be run at this point
    yield
    # Code that will run after your test, for example:
    posthog.disabled = False


@pytest.fixture(autouse=True)
def use_dummy_cache_backend(settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache",
        }
    }
    settings.CELERY_BROKER_URL = "memory://"
    settings.CELERY_RESULT_BACKEND = "db+sqlite:///results.sqlite"


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
def add_subscription_to_org():
    from metering_billing.models import Subscription

    def do_add_subscription_to_org(organization, billing_plan, customer):
        sub = Subscription.objects.create(
            organization=organization,
            billing_plan=billing_plan,
            customer=customer,
            start_date=now_utc(),
            status=SUBSCRIPTION_STATUS.ACTIVE,
        )
        return sub

    return do_add_subscription_to_org


@pytest.fixture
def get_subscriptions_in_org():
    from metering_billing.models import Subscription

    def do_get_subscriptions_in_org(organization):
        return Subscription.objects.filter(organization=organization)

    return do_get_subscriptions_in_org


@pytest.fixture
def add_product_to_org():
    from metering_billing.models import Product

    def do_add_product_to_org(organization):
        product = baker.make(
            Product,
            organization=organization,
            name="test-product",
            description="test-product-description",
            status=PRODUCT_STATUS.ACTIVE,
        )
        return product

    return do_add_product_to_org


@pytest.fixture
def add_plan_to_product():
    from metering_billing.models import Plan

    def do_add_plan_to_product(product):
        (plan,) = baker.make(
            Plan,
            organization=product.organization,
            plan_name="test-plan",
            parent_product=product,
            status=PLAN_STATUS.ACTIVE,
            plan_duration=PLAN_DURATION.MONTH,
            _quantity=1,
        )
        return plan

    return do_add_plan_to_product


@pytest.fixture
def add_plan_version_to_plan():
    from metering_billing.models import PlanVersion

    def do_add_planversion_to_plan(plan):
        (plan_version,) = baker.make(
            PlanVersion,
            organization=plan.organization,
            description="test-plan-version-description",
            version=1,
            flat_fee_billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
            usage_billing_type=USAGE_BILLING_TYPE.IN_ARREARS,
            plan=plan,
            status=PLAN_VERSION_STATUS.ACTIVE,
            flat_rate=30,
            _quantity=1,
        )
        return plan_version

    return do_add_planversion_to_plan
