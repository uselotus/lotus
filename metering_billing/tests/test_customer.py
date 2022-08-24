import pytest
from django.urls import reverse
from model_bakery import baker


@pytest.fixture
def get_customers(api_client):
    def do_get_customers(payload):
        return api_client.get(reverse("customer"), payload)
    return do_get_customers

class TestGetCustomers():
    """Testing the GET of Customer endpoint:
    GET: Return list of customers associated with the organization with API key.
        
        partitions:
        auth_status: admin, user w/ org API Key, user w/o org API Key, no_auth
    """

    def test_admin_has_access_to_all(self, api_client, get_customers):
        pass
    def test_user_valid_org_api_key_can_access_customers(self, api_client, get_customers):
        pass
    def test_user_not_in_org_but_valid_org_api_key_cannot_access_customers(self, api_client, get_customers):
        pass
    def test_user_in_org_but_invalid_org_api_key_cannot_access_customers(self, api_client, get_customers):
        pass
    def test_user_not_authenticated_cannot_access_customers(self):
        pass
