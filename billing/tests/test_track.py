from django.test import TestCase
from ..models import Customer, Event
import uuid
import json
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework_api_key.models import APIKey
from tenant.models import User, APIToken

from ..track import track_event


class TrackEventTest(TestCase):
    """
    Testcases for the track_event function view.
    """

    def setUp(self):

        user_object = User.objects.create_user(username="test", email="")
        Customer.objects.create(customer_id="7fa09280-957c-4a5f-925a-6a3498a1d299")
        api_key, key = APIToken.objects.create_key(name="test-api-ke", user=user_object)
        self.authorization_header = {
            "Authorization": "Api-Key" + " " + key,
        }

        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION="Api-Key" + " " + key)
        idempotency_id = uuid.uuid4()

        self.valid_payload = {
            "event_name": "Emails",
            "properties": {"email": ""},
            "idempotency_id": idempotency_id,
            "time_created": "2022-07-25T01:11:42.535Z",
            "customer_id": "7fa09280-957c-4a5f-925a-6a3498a1d299",
        }
        self.invalid_payload = {
            "event_name": "Emails",
            "properties": {"email": ""},
            "idempotency_id": idempotency_id,
            "time_created": "2022-07-25T01:11:42.535Z",
            "customer_id": "7fa09280-957c-3w5f-925a-6a3498a1d299",
        }

    def test_track_event_if_customer_does_not_exist(self):
        """
        Test that track_event returns bad request with message "Customer does not exist" if the customer's customer_id does not exist in the database.
        """
        response = self.client.post(
            reverse("track_event"),
            data=json.dumps(self.invalid_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
            **self.authorization_header,
        )
        self.assertEqual(response.content, b"Customer does not exist")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_track_event_creates_event(self):
        """
        Test that track_event creates an event in the database.
        """
        self.assertEqual(
            Event.objects.all()
            .filter(idempotency_id=self.valid_payload["idempotency_id"])
            .count(),
            0,
        )
        response = self.client.post(
            reverse("track_event"),
            data=json.dumps(self.valid_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Event.objects.all()
            .filter(idempotency_id=self.valid_payload["idempotency_id"])
            .count(),
            1,
        )

    def test_idempotency_duplicate_does_not_create_multiple_events(self):
        """
        Test that track_event does not create multiple events in the database if the idempotency_id is duplicated.
        """
        self.assertEqual(
            Event.objects.all()
            .filter(idempotency_id=self.valid_payload["idempotency_id"])
            .count(),
            0,
        )
        response = self.client.post(
            reverse("track_event"),
            data=json.dumps(self.valid_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Event.objects.all()
            .filter(idempotency_id=self.valid_payload["idempotency_id"])
            .count(),
            1,
        )
        response = self.client.post(
            reverse("track_event"),
            data=json.dumps(self.valid_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Event.objects.all()
            .filter(idempotency_id=self.valid_payload["idempotency_id"])
            .count(),
            1,
        )
