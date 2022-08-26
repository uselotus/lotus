import pytest
from model_bakery import baker


@pytest.fixture
def api_client_with_api_key_auth():
    from rest_framework.test import APIClient 

    def do_api_client_with_api_key_auth(key):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Api-Key " + key)
        return client
    
    return do_api_client_with_api_key_auth

@pytest.fixture
def generate_org_and_api_key():
    from metering_billing.models import APIToken, Organization

    organization = baker.make(Organization)
    _, key = APIToken.objects.create_key(
            name="test-api-key", organization=organization
        )
    return organization, key

@pytest.fixture
def add_customers_to_org():
    from metering_billing.models import Customer

    def do_add_customers_to_org(organization, n):
        customer_set = baker.make(Customer, _quantity=n, organization=organization)
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
        organization.users.add(*user_set)
        organization.save()
        return user_set
    
    return do_add_users_to_org
