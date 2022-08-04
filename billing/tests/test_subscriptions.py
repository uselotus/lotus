from django.test import TestCase
from stripe import Plan
from ..models import Customer, Subscription, BillingPlan, BillableMetric, PlanComponent
import uuid
import json
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework_api_key.models import APIKey
from tenant.models import User, APIToken
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient


class SubscriptionTest(TenantTestCase):
    """
    Testcases for the subscription views.
    """

    def setUp(self):
        super().setUp()
        self.client = TenantClient(self.tenant)
        user_object = User.objects.create_user(username="test", email="")
        Customer.objects.create(customer_id="7fa09280-957c-4a5f-925a-6a3498a1d299")
        api_key, key = APIToken.objects.create_key(name="test-api-ke", user=user_object)
        self.authorization_header = {
            "Authorization": "Api-Key" + " " + key,
        }
        metric = BillableMetric.objects.create(
            event_name="Emails", property_name="amount", aggregation_type="count"
        )

        plan = BillingPlan.objects.create(
            billable_metric=metric, metric_amount=1, name="Standard", plan_id="1"
        )
        plan_component = PlanComponent.objects.create(
            billable_metric=metric, billing_plan=plan, cost_per_metric=1
        )

        self.client.credentials(HTTP_AUTHORIZATION="Api-Key" + " " + key)

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
