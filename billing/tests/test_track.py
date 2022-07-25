from django.test import TestCase, Client
from ..models import Customer, Event
import uuid
import json
from django.urls import reverse
from rest_framework import status
from django.core.serializers.json import DjangoJSONEncoder


from ..track import track_event


class TrackEventTest(TestCase):
    """
    Testcases for the track_event function view.
    """

    def setUp(self):

        Customer.objects.create(external_id="7fa09280-957c-4a5f-925a-6a3498a1d299")

        self.client = Client()
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
        Test that track_event returns bad request with message "Customer does not exist" if the customer's external_id does not exist in the database.
        """
        response = self.client.post(
            reverse("track_event"),
            data=json.dumps(self.invalid_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        self.assertEqual(response.message, "Customer does not exist")

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
