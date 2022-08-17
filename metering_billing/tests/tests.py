from django.test import TestCase
from stripe import Plan
from ..models import (
    Customer,
    Subscription,
    BillingPlan,
    BillableMetric,
    PlanComponent,
    User,
    APIToken,
    Event,
    Organization,
)
import uuid
import json
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework_api_key.models import APIKey


class SubscriptionTest(TestCase):
    """
    Testcases for the subscription views.
    """

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        organization_object = Organization.objects.create(
            company_name="Test Company",
        )
        user_object = User.objects.create_user(username="test", email="")
        organization_object.save()

        organization_object.users.add(user_object)
        customer = Customer.objects.create(
            customer_id="7fa09280-957c-4a5f-925a-6a3498a1d299",
            organization=organization_object,
        )
        api_key, key = APIToken.objects.create(name="test-api-key", user=user_object)
        self.authorization_header = {
            "Authorization": "Api-Key" + " " + key,
        }
        metric = BillableMetric.objects.create(
            event_name="Emails", property_name="amount", aggregation_type="count"
        )

        plan = BillingPlan.objects.create(name="Standard", plan_id="1")
        plan_component = PlanComponent.objects.create(
            billable_metric=metric, billing_plan=plan, cost_per_metric=1
        )

        # self.client.credentials(HTTP_AUTHORIZATION="Api-Key" + " " + key)

        self.valid_payload = {
            "plan_id": "1",
            "start_date": "2022-07-25T01:11:42.535Z",
            "customer_id": "7fa09280-957c-4a5f-925a-6a3498a1d299",
        }
        self.invalid_payload_start_date = {
            "plan_id": "1",
            "start_date": "2022-07-25T01:11:42.535Z",
            "customer_id": "7fa09280-957c-3w5f-925a-6a3498a1d299",
        }

    def test_subscription_create_success(self):
        """
        Test that subscription post view works correctly.
        """
        response = self.client.post(
            reverse("subscription"),
            data=json.dumps(self.valid_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
            **self.authorization_header,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        subscription = Subscription.objects.all().filter(billing_plan="1")
        self.assertEqual(len(subscription), 1)

    def test_usage_get_for_subscription(self):
        """
        Test that usage get view works correctly.
        """

        payload = {
            "event_name": "Emails",
            "properties": {"count": 1},
            "idempotency_id": uuid.uuid4,
            "time_created": "2022-07-26T01:11:42.535Z",
            "customer_id": "7fa09280-957c-4a5f-925a-6a3498a1d299",
        }

        response = self.client.post(
            reverse("track_event"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
            **self.authorization_header,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        usage_payload = {"customer_id": "7fa09280-957c-4a5f-925a-6a3498a1d299"}

        response = self.client.get(
            reverse("usage"),
            data=json.dumps(usage_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
            **self.authorization_header,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.body, 1)


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
