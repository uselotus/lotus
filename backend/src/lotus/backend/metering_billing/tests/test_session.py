import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestSession:
    """Testing the function-based view track_event
    POST: Return list of customers associated with the organization with API key / user.
    partitions:
        idempotency_already_created = true, false
        customer_id_exists = true, false
    """

    def test_session_works(
        self,
    ):
        client = APIClient()
        response = client.post(
            reverse("api-session"),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
