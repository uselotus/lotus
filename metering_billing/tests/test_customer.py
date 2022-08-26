import json

import pytest
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from metering_billing.models import User
from model_bakery import baker
from rest_framework import status


@pytest.mark.django_db
class TestGetCustomers():
    """Testing the GET of Customer endpoint:
    GET: Return list of customers associated with the organization with API key.
        
        partitions:
        has_org_api_key: true, false
        user_in_org: true, false
        num_customers: 0, >0
        user_org_and_api_key_org_mismatch: true, false
        authenticated = true, false
    """
    def test_user_in_org_valid_org_api_key_can_access_customers_empty(self, generate_org_and_api_key, add_customers_to_org, add_users_to_org, api_client_with_api_key_auth):
        #covers num customers = 0, has_org_api_key=true, user_in_org=true, user_org_and_api_key_org_mismatch=false, authenticated=true
        num_customers = 5
        org, key = generate_org_and_api_key
        add_customers_to_org(org, n=num_customers)
        user, = add_users_to_org(org, n=1)
        client = api_client_with_api_key_auth(key)
        client.force_authenticate(user=user)

        payload = {}
        response = client.get(reverse("customer"), payload)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == num_customers

    def test_user_in_org_valid_org_api_key_can_access_customers_multiple(self, generate_org_and_api_key, add_customers_to_org, add_users_to_org, api_client_with_api_key_auth):
        #covers num customers > 0
        num_customers = 5
        org, key = generate_org_and_api_key
        add_customers_to_org(org, n=num_customers)
        user, = add_users_to_org(org, n=1)
        client = api_client_with_api_key_auth(key)
        client.force_authenticate(user=user)

        payload = {}
        response = client.get(reverse("customer"), payload)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == num_customers

    def test_user_not_in_org_but_valid_org_api_key_reject_access(self, generate_org_and_api_key, add_customers_to_org, add_users_to_org, api_client_with_api_key_auth):
        #covers user_in_org = false
        num_customers = 5
        org, key = generate_org_and_api_key
        add_customers_to_org(org, n=num_customers)
        user, = baker.make(User, _quantity=1)
        client = api_client_with_api_key_auth(key)
        client.force_authenticate(user=user)

        payload = {}
        response = client.get(reverse("customer"), payload)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_user_in_org_but_invalid_org_api_key_reject_access(self, generate_org_and_api_key, add_customers_to_org, add_users_to_org, api_client_with_api_key_auth):
        #covers has_org_api_key = false
        num_customers = 5
        org, _ = generate_org_and_api_key
        add_customers_to_org(org, n=num_customers)
        user, = add_users_to_org(org, n=1)
        client = api_client_with_api_key_auth("bogus-key")
        client.force_authenticate(user=user)

        payload = {}
        response = client.get(reverse("customer"), payload)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_user_org_and_api_key_different_reject_access(self, generate_org_and_api_key, add_customers_to_org, add_users_to_org, api_client_with_api_key_auth):
        #covers user_org_and_api_key_org_mismatch = false
        num_customers = 5
        org1, _ = generate_org_and_api_key
        org2, key2 = generate_org_and_api_key
        add_customers_to_org(org1, n=num_customers)
        add_customers_to_org(org2, n=num_customers)
        user, = add_users_to_org(org1, n=1)
        client = api_client_with_api_key_auth(key2)
        client.force_authenticate(user=user)

        payload = {}
        response = client.get(reverse("customer"), payload)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_user_not_authenticated_reject_access(self, generate_org_and_api_key, add_customers_to_org, add_users_to_org, api_client_with_api_key_auth):
        #covers authenticated = false
        num_customers = 5
        org, key = generate_org_and_api_key
        add_customers_to_org(org, n=num_customers)
        _, = add_users_to_org(org, n=1)
        client = api_client_with_api_key_auth(key)

        payload = {}
        response = client.get(reverse("customer"), payload)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.django_db
class TestInsertCustomer():
    """Testing the POST of Customer endpoint:
    POST: Return list of customers associated with the organization with API key / user.
        
        partitions:
        has_org_api_key: true, false
        user_in_org: true, false
        user_org_and_api_key_org_mismatch: true, false
        authenticated = true, false
        num_customers_before_insert = 0, >0

    """
    def test_user_in_org_valid_org_api_key_can_create_customer_empty_before(self, generate_org_and_api_key, add_users_to_org, api_client_with_api_key_auth, get_customers_in_org):
        #covers num_customers_before_insert = 0, has_org_api_key=true, user_in_org=true, user_org_and_api_key_org_mismatch=false, authenticated=true
        org, key = generate_org_and_api_key
        user, = add_users_to_org(org, n=1)
        client = api_client_with_api_key_auth(key)
        client.force_authenticate(user=user)

        payload = {
            "name":"test_customer",
            "customer_id":"test_customer_id",
            "billing_id":"test_billing_id",
            "balance":30,
            "currency":"USD",
            "payment_provider_id":"test_payment_provider_id",
            "properties": {}
        }
        response = client.post(
            reverse("customer"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0 #check that the response is not empty
        assert len(get_customers_in_org(org)) == 1

    def test_user_in_org_valid_org_api_key_can_create_customer_nonempty_before(self, generate_org_and_api_key, add_customers_to_org, add_users_to_org, api_client_with_api_key_auth, get_customers_in_org):
        #covers num_customers_before_insert = 0, has_org_api_key=true, user_in_org=true, user_org_and_api_key_org_mismatch=false, authenticated=true
        num_customers = 5
        org, key = generate_org_and_api_key
        add_customers_to_org(org, n=num_customers)
        user, = add_users_to_org(org, n=1)
        client = api_client_with_api_key_auth(key)
        client.force_authenticate(user=user)

        payload = {
            "name":"test_customer",
            "customer_id":"test_customer_id",
            "billing_id":"test_billing_id",
            "balance":30,
            "currency":"USD",
            "payment_provider_id":"test_payment_provider_id",
            "properties": {}
        }
        response = client.post(
            reverse("customer"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0
        assert len(get_customers_in_org(org)) == num_customers+1

    def test_user_not_in_org_but_valid_org_api_key_reject_insert(self, generate_org_and_api_key, add_customers_to_org, api_client_with_api_key_auth, get_customers_in_org):
        #covers user_in_org = false
        num_customers = 5
        org, key = generate_org_and_api_key
        add_customers_to_org(org, n=num_customers)
        user, = baker.make(User, _quantity=1)
        client = api_client_with_api_key_auth(key)
        client.force_authenticate(user=user)

        payload = {
            "name":"test_customer",
            "customer_id":"test_customer_id",
            "billing_id":"test_billing_id",
            "balance":30,
            "currency":"USD",
            "payment_provider_id":"test_payment_provider_id",
            "properties": {}
        }
        response = client.post(
            reverse("customer"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert len(get_customers_in_org(org)) == num_customers

    def test_user_in_org_but_invalid_org_api_key_reject_access(self, generate_org_and_api_key, add_customers_to_org, add_users_to_org, api_client_with_api_key_auth, get_customers_in_org):
        #covers has_org_api_key = false
        num_customers = 5
        org, _ = generate_org_and_api_key
        add_customers_to_org(org, n=num_customers)
        user, = add_users_to_org(org, n=1)
        client = api_client_with_api_key_auth("bogus-key")
        client.force_authenticate(user=user)

        payload = {
            "name":"test_customer",
            "customer_id":"test_customer_id",
            "billing_id":"test_billing_id",
            "balance":30,
            "currency":"USD",
            "payment_provider_id":"test_payment_provider_id",
            "properties": {}
        }
        response = client.post(
            reverse("customer"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert len(get_customers_in_org(org)) == num_customers

    def test_user_org_and_api_key_different_reject_access(self, generate_org_and_api_key, add_customers_to_org, add_users_to_org, api_client_with_api_key_auth, get_customers_in_org):
        #covers user_org_and_api_key_org_mismatch = false
        num_customers = 5
        org1, _ = generate_org_and_api_key
        org2, key2 = generate_org_and_api_key
        add_customers_to_org(org1, n=num_customers)
        add_customers_to_org(org2, n=num_customers)
        user, = add_users_to_org(org1, n=1)
        client = api_client_with_api_key_auth(key2)
        client.force_authenticate(user=user)

        payload = {
            "name":"test_customer",
            "customer_id":"test_customer_id",
            "billing_id":"test_billing_id",
            "balance":30,
            "currency":"USD",
            "payment_provider_id":"test_payment_provider_id",
            "properties": {}
        }
        response = client.post(
            reverse("customer"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert len(get_customers_in_org(org1)) == num_customers
        assert len(get_customers_in_org(org2)) == num_customers

    def test_user_not_authenticated_reject_access(self, generate_org_and_api_key, add_customers_to_org, add_users_to_org, api_client_with_api_key_auth):
        #covers authenticated = false
        num_customers = 5
        org, key = generate_org_and_api_key
        add_customers_to_org(org, n=num_customers)
        _, = add_users_to_org(org, n=1)
        client = api_client_with_api_key_auth(key)

        payload = {
            "name":"test_customer",
            "customer_id":"test_customer_id",
            "billing_id":"test_billing_id",
            "balance":30,
            "currency":"USD",
            "payment_provider_id":"test_payment_provider_id",
            "properties": {}
        }
        response = client.post(
            reverse("customer"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
