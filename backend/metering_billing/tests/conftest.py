import uuid

import posthog
import pytest
from metering_billing.utils import now_utc
from metering_billing.utils.enums import (
    PLAN_DURATION,
    PLAN_STATUS,
    PLAN_VERSION_STATUS,
    PRODUCT_STATUS,
    USAGE_BILLING_FREQUENCY,
)
from model_bakery import baker


@pytest.fixture(autouse=True)
def run_around_tests():
    # Code that will run before your test, for example:
    posthog.disabled = True
    # A test function will be run at this point
    yield
    # Code that will run after your test, for example:


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
def turn_off_stripe_connection():
    from metering_billing.payment_processors import PAYMENT_PROCESSOR_MAP

    sk = PAYMENT_PROCESSOR_MAP["stripe"].test_secret_key
    PAYMENT_PROCESSOR_MAP["stripe"].test_secret_key = None

    yield

    PAYMENT_PROCESSOR_MAP["stripe"].test_secret_key = sk


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
        organization = baker.make(Organization, tax_rate=None)
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
            Customer,
            _quantity=n,
            organization=organization,
            customer_id=uuid.uuid4,
            customer_name="test_customer",
            tax_rate=None,
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
    from metering_billing.models import Metric

    def do_add_billable_metrics_to_org(organization, n):
        bm_set = baker.make(
            Metric, _quantity=n, organization=organization, _fill_optional=True
        )
        return bm_set

    return do_add_billable_metrics_to_org


@pytest.fixture
def get_billable_metrics_in_org():
    from metering_billing.models import Metric

    def do_get_billable_metrics_in_org(organization):
        return Metric.objects.filter(organization=organization)

    return do_get_billable_metrics_in_org


@pytest.fixture
def add_subscription_record_to_org():
    from metering_billing.models import SubscriptionRecord
    from metering_billing.utils import calculate_end_date

    def do_add_subscription_record_to_org(
        organization,
        billing_plan,
        customer,
        start_date=None,
        day_anchor=None,
        month_anchor=None,
        end_date=None,
    ):
        duration = billing_plan.plan.plan_duration
        start_date = start_date if start_date else now_utc()
        day_anchor = day_anchor if day_anchor else start_date.day
        month_anchor = (
            month_anchor
            if month_anchor
            else (
                start_date.month
                if duration in [PLAN_DURATION.QUARTERLY, PLAN_DURATION.YEARLY]
                else None
            )
        )
        end_date = end_date
        if not end_date:
            timezone = customer.timezone
            end_date = calculate_end_date(
                duration,
                start_date,
                timezone,
                day_anchor=day_anchor,
                month_anchor=month_anchor,
            )
        subscription_record = SubscriptionRecord.objects.create(
            organization=organization,
            customer=customer,
            billing_plan=billing_plan,
            start_date=start_date,
            auto_renew=True,
            is_new=True,
        )
        subscription_record.save()
        return subscription_record

    return do_add_subscription_record_to_org


@pytest.fixture
def get_subscription_records_in_org():
    from metering_billing.models import SubscriptionRecord

    def do_get_subscription_records_in_org(organization) -> list[SubscriptionRecord]:
        return SubscriptionRecord.objects.filter(organization=organization)

    return do_get_subscription_records_in_org


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
            plan_duration=PLAN_DURATION.MONTHLY,
            _quantity=1,
        )
        return plan

    return do_add_plan_to_product


@pytest.fixture
def add_plan_version_to_plan():
    from metering_billing.models import PlanVersion, RecurringCharge

    def do_add_planversion_to_plan(plan):
        (plan_version,) = baker.make(
            PlanVersion,
            organization=plan.organization,
            description="test-plan-version-description",
            version=1,
            usage_billing_frequency=USAGE_BILLING_FREQUENCY.MONTHLY,
            plan=plan,
            status=PLAN_VERSION_STATUS.ACTIVE,
            _quantity=1,
        )
        RecurringCharge.objects.create(
            organization=plan.organization,
            plan_version=plan_version,
            charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
            charge_behavior=RecurringCharge.ChargeBehaviorType.PRORATE,
            amount=30,
            pricing_unit=plan_version.pricing_unit,
        )
        return plan_version

    return do_add_planversion_to_plan
