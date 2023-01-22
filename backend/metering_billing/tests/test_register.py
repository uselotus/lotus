import json

import pytest
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from metering_billing.models import Organization, User


@pytest.fixture
def registration_test_common_setup(
    generate_org_and_api_key,
    add_users_to_org,
):
    def do_registration_test_common_setup():
        # set up organizations and api keys
        org, key = generate_org_and_api_key()
        org2, key2 = generate_org_and_api_key()
        setup_dict = {
            "org": org,
            "key": key,
            "org2": org2,
            "key2": key2,
        }
        client = APIClient()
        setup_dict["client"] = client
        (user,) = add_users_to_org(org, n=1)
        setup_dict["user"] = user

        return setup_dict

    return do_registration_test_common_setup


@pytest.fixture
def register_payload():
    def generate_register_payload(
        organization_name, industry, email, password, username
    ):
        payload = {
            "register": {
                "organization_name": organization_name,
                "industry": industry,
                "email": email,
                "password": password,
                "username": username,
            }
        }
        return payload

    return generate_register_payload


@pytest.mark.django_db(transaction=True)
class TestRegister:
    """Testing the POST of Customer endpoint:
    POST: Return list of customers associated with the organization with API key / user.
    partitions:
        auth_method: api_key, session_auth, both
        num_customers_before_insert: 0, >0
        user_org_and_api_key_org_different: true, false
        customer_id
    """

    def test_register_valid(self, registration_test_common_setup, register_payload):
        # covers num_customers_before_insert = 0, has_org_api_key=true, user_in_org=true, user_org_and_api_key_org_different=false
        setup_dict = registration_test_common_setup()
        users_before = User.objects.all().count()
        organizations_before = Organization.objects.all().count()

        payload = register_payload(
            organization_name="test",
            industry="test",
            email="test",
            password="test",
            username="test",
        )

        response = setup_dict["client"].post(
            reverse("register"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        users_after = User.objects.all().count()
        organizations_after = Organization.objects.all().count()
        assert response.status_code == status.HTTP_201_CREATED
        assert users_before + 1 == users_after
        assert organizations_before + 1 == organizations_after
        organization = Organization.objects.get(organization_name="test")
        user = User.objects.get(username="test", email="test")
        assert user.organization == organization

    def test_register_org_exists(
        self, registration_test_common_setup, register_payload
    ):
        setup_dict = registration_test_common_setup()
        users_before = User.objects.all().count()
        organizations_before = Organization.objects.all().count()

        payload = register_payload(
            organization_name=setup_dict["org"].organization_name,
            industry="test",
            email="test",
            password="test",
            username="test",
        )

        response = setup_dict["client"].post(
            reverse("register"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        users_after = User.objects.all().count()
        organizations_after = Organization.objects.all().count()
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert users_before == users_after
        assert organizations_before == organizations_after

    def test_register_username_exists(
        self, registration_test_common_setup, register_payload
    ):
        setup_dict = registration_test_common_setup()
        users_before = User.objects.all().count()
        organizations_before = Organization.objects.all().count()

        payload = register_payload(
            organization_name=setup_dict["org"].organization_name,
            industry="test",
            email="test",
            password="test",
            username=setup_dict["user"].username,
        )

        response = setup_dict["client"].post(
            reverse("register"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        users_after = User.objects.all().count()
        organizations_after = Organization.objects.all().count()
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert users_before == users_after
        assert organizations_before == organizations_after

    def test_register_email_exists(
        self, registration_test_common_setup, register_payload
    ):
        setup_dict = registration_test_common_setup()
        users_before = User.objects.all().count()
        organizations_before = Organization.objects.all().count()

        payload = register_payload(
            organization_name=setup_dict["org"].organization_name,
            industry="test",
            email=setup_dict["user"].email,
            password="test",
            username="test",
        )

        response = setup_dict["client"].post(
            reverse("register"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        users_after = User.objects.all().count()
        organizations_after = Organization.objects.all().count()
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert users_before == users_after
        assert organizations_before == organizations_after
