import json

import pytest
from dateutil.relativedelta import relativedelta
from django.urls import reverse
from metering_billing.models import (
    AddOnSpecification,
    Customer,
    Feature,
    Invoice,
    Plan,
    PlanVersion,
    PricingUnit,
    RecurringCharge,
    SubscriptionRecord,
)
from metering_billing.serializers.serializer_utils import DjangoJSONEncoder
from metering_billing.utils import now_utc
from rest_framework import status
from rest_framework.test import APIClient


@pytest.fixture
def customer_test_common_setup(
    generate_org_and_api_key,
    add_customers_to_org,
    add_users_to_org,
    api_client_with_api_key_auth,
):
    def do_customer_test_common_setup(
        *, num_customers, auth_method, user_org_and_api_key_org_different
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

        # set up number of customers
        if num_customers > 0:
            setup_dict["org_customers"] = add_customers_to_org(org, n=num_customers)
            setup_dict["org2_customers"] = add_customers_to_org(org2, n=num_customers)

        premium_support_feature = Feature.objects.create(
            organization=org,
            feature_name="premium_support",
            feature_description="premium support",
        )
        flat_fee_addon_spec = AddOnSpecification.objects.create(
            organization=org,
            billing_frequency=AddOnSpecification.BillingFrequency.ONE_TIME,
            flat_fee_invoicing_behavior_on_attach=AddOnSpecification.FlatFeeInvoicingBehaviorOnAttach.INVOICE_ON_ATTACH,
        )
        flat_fee_addon = Plan.addons.create(
            organization=org, plan_name="flat_fee_addon", is_addon=True
        )
        flat_fee_addon_version = PlanVersion.addon_versions.create(
            organization=org,
            plan=flat_fee_addon,
            addon_spec=flat_fee_addon_spec,
            plan_version_name="flat_fee_addon_version",
            currency=PricingUnit.objects.get(organization=org, code="USD"),
        )
        RecurringCharge.objects.create(
            organization=org,
            plan_version=flat_fee_addon_version,
            charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
            charge_behavior=RecurringCharge.ChargeBehaviorType.PRORATE,
            amount=10,
            pricing_unit=flat_fee_addon_version.currency,
        )
        flat_fee_addon_version.features.add(premium_support_feature)
        setup_dict["flat_fee_addon"] = flat_fee_addon
        setup_dict["flat_fee_addon_version"] = flat_fee_addon_version
        setup_dict["premium_support_feature"] = premium_support_feature
        setup_dict["flat_fee_addon_spec"] = flat_fee_addon_spec

        return setup_dict

    return do_customer_test_common_setup


@pytest.mark.django_db
class TestGetCustomers:
    """Testing the GET of Customer endpoint:
    GET: Return list of customers associated with the organization with API key.
        partitions:
        auth_method: api_key, session_auth, both
        num_customers: 0, >0
        user_org_and_api_key_org_different: true, false
    """

    def test_api_key_can_access_customers_empty(self, customer_test_common_setup):
        # covers num_customers=0, auth_method=api_key, user_org_and_api_key_org_different=false
        num_customers = 0
        setup_dict = customer_test_common_setup(
            num_customers=0,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )

        payload = {}
        response = setup_dict["client"].get(reverse("customer-list"), payload)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == num_customers

    def test_session_auth_can_access_customers_multiple(
        self, customer_test_common_setup
    ):
        # covers num customers > 0, auth_method=session_auth
        num_customers = 5
        setup_dict = customer_test_common_setup(
            num_customers=num_customers,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )

        payload = {}
        response = setup_dict["client"].get(reverse("customer-list"), payload)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == num_customers


@pytest.fixture
def insert_customer_payload():
    payload = {
        "customer_name": "test_customer",
        "customer_id": "test_customer_id",
        "email": "test@test.com",
        # "payment_provider_id": "test_payment_provider_id",
        # "payment_provider": "stripe",
        # "properties": {},
    }
    return payload


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("turn_off_stripe_connection")
class TestInsertCustomer:
    """Testing the POST of Customer endpoint:
    POST: Return list of customers associated with the organization with API key / user.
    partitions:
        auth_method: api_key, session_auth, both
        num_customers_before_insert: 0, >0
        user_org_and_api_key_org_different: true, false
        customer_id
    """

    def test_api_key_can_create_customer_empty_before(
        self,
        customer_test_common_setup,
        insert_customer_payload,
        get_customers_in_org,
    ):
        # covers num_customers_before_insert = 0, has_org_api_key=true, user_in_org=true, user_org_and_api_key_org_different=false
        num_customers = 0
        setup_dict = customer_test_common_setup(
            num_customers=num_customers,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )

        response = setup_dict["client"].post(
            reverse("customer-list"),
            data=json.dumps(insert_customer_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0  # check that the response is not empty
        assert len(get_customers_in_org(setup_dict["org"])) == 1

    def test_session_auth_can_create_customer_nonempty_before(
        self, customer_test_common_setup, insert_customer_payload, get_customers_in_org
    ):
        # covers num_customers_before_insert = 0, has_org_api_key=true, user_in_org=true, user_org_and_api_key_org_different=false, authenticated=true
        num_customers = 5
        setup_dict = customer_test_common_setup(
            num_customers=num_customers,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )

        response = setup_dict["client"].post(
            reverse("customer-list"),
            data=json.dumps(insert_customer_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0
        assert len(get_customers_in_org(setup_dict["org"])) == num_customers + 1

    def test_customer_id_already_exists_within_org_reject_creation(
        self, customer_test_common_setup, insert_customer_payload, get_customers_in_org
    ):
        num_customers = 3
        setup_dict = customer_test_common_setup(
            num_customers=num_customers,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )

        payload = insert_customer_payload
        payload["customer_id"] = setup_dict["org_customers"][0].customer_id
        response = setup_dict["client"].post(
            reverse("customer-list"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert len(get_customers_in_org(setup_dict["org"])) == num_customers
        assert len(get_customers_in_org(setup_dict["org2"])) == num_customers

    def test_customer_id_already_exists_not_in_org_accept_creation(
        self, customer_test_common_setup, insert_customer_payload, get_customers_in_org
    ):
        num_customers = 3
        setup_dict = customer_test_common_setup(
            num_customers=num_customers,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )

        Customer.objects.create(
            organization=setup_dict["org2"],
            customer_id=insert_customer_payload["customer_id"],
        )
        response = setup_dict["client"].post(
            reverse("customer-list"),
            data=json.dumps(insert_customer_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0  # check that the response is not empty
        assert len(get_customers_in_org(setup_dict["org"])) == num_customers + 1


@pytest.mark.django_db(transaction=True)
class TestDeleteCustomer:
    def test_can_delete_customer_with_subscriptions(
        self,
        customer_test_common_setup,
        insert_customer_payload,
        get_customers_in_org,
        add_product_to_org,
        add_plan_to_product,
        add_plan_version_to_plan,
    ):
        # covers num_customers_before_insert = 0, has_org_api_key=true, user_in_org=true, user_org_and_api_key_org_different=false
        num_customers = 0
        setup_dict = customer_test_common_setup(
            num_customers=num_customers,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )

        response = setup_dict["client"].post(
            reverse("customer-list"),
            data=json.dumps(insert_customer_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0  # check that the response is not empty
        assert len(get_customers_in_org(setup_dict["org"])) == 1

        customer = Customer.objects.get(
            customer_id=insert_customer_payload["customer_id"]
        )
        product = add_product_to_org(setup_dict["org"])
        plan = add_plan_to_product(product)
        plan_version = add_plan_version_to_plan(plan)
        plan_version.target_customers.add(customer)
        sr = SubscriptionRecord.create_subscription_record(
            start_date=now_utc(),
            end_date=now_utc() + relativedelta(days=30),
            billing_plan=plan_version,
            customer=customer,
            organization=setup_dict["org"],
        )
        addon_sr = SubscriptionRecord.create_addon_subscription_record(
            parent_subscription_record=sr,
            addon_billing_plan=setup_dict["flat_fee_addon_version"],
        )
        invoices_before = Invoice.objects.all().count()
        response = setup_dict["client"].post(
            reverse("customer-delete", kwargs={"customer_id": customer.customer_id}),
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(get_customers_in_org(setup_dict["org"])) == 0

        # subscription doesn't get deleted
        invoices_after = Invoice.objects.all().count()
        sr_updated = SubscriptionRecord.objects.get(id=sr.id)
        addon_sr_updated = SubscriptionRecord.objects.get(id=addon_sr.id)
        assert sr_updated.end_date < now_utc()
        assert invoices_before == invoices_after
        assert addon_sr_updated.end_date < now_utc()
        assert customer not in plan_version.target_customers.all()
