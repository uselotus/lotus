import itertools
import json
import urllib.parse
from datetime import datetime, timedelta

import dateutil.parser
import pytest
import pytz
from django.urls import reverse
from metering_billing.aggregation.billable_metrics import METRIC_HANDLER_MAP
from metering_billing.models import (
    Customer,
    Metric,
    Organization,
    PlanComponent,
    PlanVersion,
    PriceTier,
    SubscriptionRecord,
)
from metering_billing.serializers.serializer_utils import DjangoJSONEncoder
from metering_billing.utils import now_utc
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APIClient


@pytest.fixture
def timezone_test_common_setup(
    generate_org_and_api_key,
    add_users_to_org,
    api_client_with_api_key_auth,
    add_subscription_record_to_org,
    add_customers_to_org,
    add_product_to_org,
    add_plan_to_product,
):
    def do_timezone_test_common_setup(
        *, num_subscriptions, auth_method, user_org_and_api_key_org_different=False
    ):
        # set up organizations and api keys
        org, key = generate_org_and_api_key()
        org2, key2 = generate_org_and_api_key()
        setup_dict = {
            "org": org,
            "key": key,
            "org2": org2,
            "key2": key2,
        }
        # set up the client with the appropriate api key spec
        if auth_method == "api_key":
            client = api_client_with_api_key_auth(key)
        elif auth_method == "session_auth":
            client = APIClient()
            (user,) = add_users_to_org(org, n=1)
            client.force_authenticate(user=user)
            setup_dict["user"] = user
        else:
            client = api_client_with_api_key_auth(key)
            if user_org_and_api_key_org_different:
                (user,) = add_users_to_org(org2, n=1)
            else:
                (user,) = add_users_to_org(org, n=1)
            client.force_authenticate(user=user)
            setup_dict["user"] = user
        setup_dict["client"] = client

        metric_set = baker.make(
            Metric,
            organization=org,
            event_name="email_sent",
            property_name=itertools.cycle(["num_characters", "peak_bandwith", ""]),
            usage_aggregation_type=itertools.cycle(["sum", "max", "count"]),
            billable_metric_name=itertools.cycle(
                ["count_chars", "peak_bandwith", "email_sent"]
            ),
            _quantity=3,
        )
        for metric in metric_set:
            METRIC_HANDLER_MAP[metric.metric_type].create_continuous_aggregate(metric)
        setup_dict["metrics"] = metric_set
        product = add_product_to_org(org)
        setup_dict["product"] = product
        plan = add_plan_to_product(product)
        setup_dict["plan"] = plan
        billing_plan = baker.make(
            PlanVersion,
            organization=org,
            plan=plan,
        )
        plan.save()
        for i, (fmu, cpb, mupb) in enumerate(
            zip([50, 0, 1], [5, 0.05, 2], [100, 1, 1])
        ):
            pc = PlanComponent.objects.create(
                plan_version=billing_plan,
                billable_metric=metric_set[i],
            )
            start = 0
            if fmu > 0:
                PriceTier.objects.create(
                    plan_component=pc,
                    type=PriceTier.PriceTierType.FREE,
                    range_start=0,
                    range_end=fmu,
                )
                start = fmu
            PriceTier.objects.create(
                plan_component=pc,
                type=PriceTier.PriceTierType.PER_UNIT,
                range_start=start,
                cost_per_batch=cpb,
                metric_units_per_batch=mupb,
            )
        setup_dict["billing_plan"] = billing_plan

        (customer,) = add_customers_to_org(org, n=1)
        if num_subscriptions > 0:
            setup_dict["org_subscription"] = add_subscription_record_to_org(
                org, billing_plan, customer
            )
        payload = {
            "name": "test_subscription",
            "start_date": now_utc() - timedelta(days=5),
            "customer_id": customer.customer_id,
            "plan_id": billing_plan.plan.plan_id,
        }
        setup_dict["payload"] = payload
        setup_dict["customer"] = customer

        return setup_dict

    return do_timezone_test_common_setup


@pytest.mark.django_db(transaction=True)
class TestTimezones:
    def test_changing_organization_time_zone_changes_customer_time_zone(
        self, timezone_test_common_setup, get_subscription_records_in_org
    ):
        num_subscriptions = 0
        setup_dict = timezone_test_common_setup(
            num_subscriptions=num_subscriptions,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )

        payload = {"timezone": "America/Los_Angeles"}
        response = setup_dict["client"].patch(
            reverse(
                "organization-detail",
                kwargs={
                    "organization_id": "org_" + setup_dict["org"].organization_id.hex
                },
            ),
            json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        org = Organization.objects.get(
            organization_id=setup_dict["org"].organization_id
        )
        assert org.timezone == pytz.timezone("America/Los_Angeles")
        cust = Customer.objects.get(customer_id=setup_dict["customer"].customer_id)
        assert cust.timezone == pytz.timezone("America/Los_Angeles")

    def test_change_customer_timezone_dont_change_after_changing_org(
        self, timezone_test_common_setup, get_subscription_records_in_org
    ):
        num_subscriptions = 0
        setup_dict = timezone_test_common_setup(
            num_subscriptions=num_subscriptions,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )

        payload = {"timezone": "America/Los_Angeles"}
        response = setup_dict["client"].patch(
            reverse(
                "customer-detail",
                kwargs={"customer_id": setup_dict["customer"].customer_id},
            ),
            json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        org = Organization.objects.get(
            organization_id=setup_dict["org"].organization_id
        )
        assert org.timezone == pytz.timezone("UTC")
        cust = Customer.objects.get(customer_id=setup_dict["customer"].customer_id)
        assert cust.timezone == pytz.timezone("America/Los_Angeles")

        payload = {"timezone": "America/New_York"}
        response = setup_dict["client"].patch(
            reverse(
                "organization-detail",
                kwargs={
                    "organization_id": "org_" + setup_dict["org"].organization_id.hex
                },
            ),
            json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        org = Organization.objects.get(
            organization_id=setup_dict["org"].organization_id
        )
        assert org.timezone == pytz.timezone("America/New_York")
        cust = Customer.objects.get(customer_id=setup_dict["customer"].customer_id)
        assert cust.timezone == pytz.timezone("America/Los_Angeles")

    def test_timezones_in_subscription_objects_has_changed(
        self, timezone_test_common_setup, get_subscription_records_in_org
    ):
        num_subscriptions = 1
        setup_dict = timezone_test_common_setup(
            num_subscriptions=num_subscriptions,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )

        # get subscription before and check timezones
        payload = {
            "customer_id": setup_dict["customer"].customer_id,
        }
        response = setup_dict["client"].get(reverse("subscription-list"), payload)
        assert response.status_code == status.HTTP_200_OK
        subscription = response.json()[0]
        start_date = dateutil.parser.isoparse(subscription["start_date"])
        assert start_date.utcoffset() == pytz.timezone("UTC").utcoffset(
            start_date.replace(tzinfo=None)
        )

        payload = {"timezone": "America/Los_Angeles"}
        response = setup_dict["client"].patch(
            reverse(
                "organization-detail",
                kwargs={
                    "organization_id": "org_" + setup_dict["org"].organization_id.hex
                },
            ),
            json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        org = Organization.objects.get(
            organization_id=setup_dict["org"].organization_id
        )
        assert org.timezone == pytz.timezone("America/Los_Angeles")
        cust = Customer.objects.get(customer_id=setup_dict["customer"].customer_id)
        assert cust.timezone == pytz.timezone("America/Los_Angeles")

        # get subscription after and parse end date and start date
        payload = {
            "customer_id": setup_dict["customer"].customer_id,
        }
        response = setup_dict["client"].get(reverse("subscription-list"), payload)
        assert response.status_code == status.HTTP_200_OK
        subscription = response.json()[0]

        # Parse the start and end date string with timezone aware and check that they are in America/Los_Angeles
        start_date = dateutil.parser.isoparse(subscription["start_date"])
        end_date = dateutil.parser.isoparse(subscription["end_date"])
        assert start_date.utcoffset() == pytz.timezone("America/Los_Angeles").utcoffset(
            start_date.replace(tzinfo=None)
        )
        assert end_date.utcoffset() == pytz.timezone("America/Los_Angeles").utcoffset(
            end_date.replace(tzinfo=None)
        )

    def test_timezones_in_subscription_objects_has_changed_crossing_dst(
        self, timezone_test_common_setup, get_subscription_records_in_org
    ):
        num_subscriptions = 0
        setup_dict = timezone_test_common_setup(
            num_subscriptions=num_subscriptions,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )

        prev_subscription_records_len = SubscriptionRecord.objects.all().count()
        assert prev_subscription_records_len == 0

        timezone = pytz.timezone("America/Los_Angeles")
        start_date = datetime.now(timezone) - timedelta(days=5)

        transitions = timezone._utc_transition_times
        dst_transitions = [
            x for x in transitions if x > start_date.replace(tzinfo=None)
        ]
        dst_start, _ = dst_transitions[0], dst_transitions[1]

        start_date = dst_start - timedelta(days=1)
        payload = {
            "name": "test_subscription",
            "start_date": start_date.replace(tzinfo=timezone),
            "customer_id": setup_dict["customer"].customer_id,
            "plan_id": setup_dict["billing_plan"].plan.plan_id,
        }
        params = {"status": ["active", "not_started"]}
        response = setup_dict["client"].post(
            reverse("subscription-add") + "?" + urllib.parse.urlencode(params),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        after_subscription_records_len = SubscriptionRecord.objects.all().count()

        assert response.status_code == status.HTTP_201_CREATED
        assert after_subscription_records_len == prev_subscription_records_len + 1

        # get subscription before and check timezones
        payload = {
            "customer_id": setup_dict["customer"].customer_id,
        }
        response = setup_dict["client"].get(reverse("subscription-list"), payload)
        assert response.status_code == status.HTTP_200_OK
        subscription = response.json()[0]
        start_date = dateutil.parser.isoparse(subscription["start_date"])
        assert start_date.utcoffset() == pytz.timezone("UTC").utcoffset(
            start_date.replace(tzinfo=None)
        )

        payload = {"timezone": "America/Los_Angeles"}
        response = setup_dict["client"].patch(
            reverse(
                "organization-detail",
                kwargs={
                    "organization_id": "org_" + setup_dict["org"].organization_id.hex
                },
            ),
            json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        org = Organization.objects.get(
            organization_id=setup_dict["org"].organization_id
        )
        assert org.timezone == pytz.timezone("America/Los_Angeles")
        cust = Customer.objects.get(customer_id=setup_dict["customer"].customer_id)
        assert cust.timezone == pytz.timezone("America/Los_Angeles")

        # get subscription after and parse end date and start date
        payload = {
            "customer_id": setup_dict["customer"].customer_id,
        }
        response = setup_dict["client"].get(reverse("subscription-list"), payload)
        assert response.status_code == status.HTTP_200_OK
        subscription = response.json()[0]

        # Parse the start and end date string with timezone aware and check that they are in America/Los_Angeles
        start_date = dateutil.parser.isoparse(subscription["start_date"])
        end_date = dateutil.parser.isoparse(subscription["end_date"])
        assert start_date.utcoffset() == pytz.timezone("America/Los_Angeles").utcoffset(
            start_date.replace(tzinfo=None)
        )
        assert end_date.utcoffset() == pytz.timezone("America/Los_Angeles").utcoffset(
            end_date.replace(tzinfo=None)
        )
        assert start_date.utcoffset() != end_date.utcoffset()
