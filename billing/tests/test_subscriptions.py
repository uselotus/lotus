from django.test import TestCase
from ..models import Customer, Subscription, BillingPlan, BillableMetric
import uuid
import json
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework_api_key.models import APIKey
from tenant.models import User, APIToken


class SubscriptionTest(TestCase):
    """
    Testcases for the subscription views.
    """

    def setUp(self):

        user_object = User.objects.create_user(username="test", email="")
        Customer.objects.create(customer_id="7fa09280-957c-4a5f-925a-6a3498a1d299")
        api_key, key = APIToken.objects.create_key(name="test-api-ke", user=user_object)
        self.authorization_header = {
            "Authorization": "Api-Key" + " " + key,
        }
        metric = BillableMetric.objects.create(
            event_name="Emails", property_name="amount", aggregation_type="count"
        )
        BillingPlan.objects.create(
            billable_metric=metric, metric_amount=1, name="Standard", plan_id="1"
        )

        self.client = APIClient()
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
