import json
import uuid

import pytest
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from rest_framework import status

from metering_billing.kafka.consumer import write_batch_events_to_db
from metering_billing.utils import now_utc


@pytest.fixture
def track_event_test_common_setup(
    generate_org_and_api_key,
    add_customers_to_org,
    api_client_with_api_key_auth,
    create_events_with_org_customer,
):
    def do_track_event_test_common_setup(
        *, idempotency_already_created, customer_id_exists
    ):
        # set up organizations and api keys
        org, key = generate_org_and_api_key()
        setup_dict = {
            "org": org,
            "key": key,
        }

        # set up the client with the appropriate api key spec
        client = api_client_with_api_key_auth(key)
        setup_dict["client"] = client

        # set up customers
        (customer,) = add_customers_to_org(org, n=1)
        setup_dict["customer"] = customer

        # set up existing events
        num_events_in = 10
        setup_dict["num_events_in"] = num_events_in
        event_set = create_events_with_org_customer(org, customer, num_events_in)

        # setup repeat idempotency id
        if idempotency_already_created:
            idempotency_id = event_set[0].idempotency_id
        else:
            idempotency_id = str(uuid.uuid4())
        setup_dict["idempotency_id"] = idempotency_id

        # setup whether customer id exists
        if customer_id_exists:
            customer_id = customer.customer_id
        else:
            customer_id = "foobar"
        setup_dict["customer_id"] = customer_id

        return setup_dict

    return do_track_event_test_common_setup


@pytest.fixture
def track_event_payload():
    def generate_track_event_payload(idempotency_id, time_created, customer_id):
        payload = {
            "event_name": "test_event_name",
            "properties": {
                "test_field_1": "test_value_1",
                "test_field_2": "test_value_2",
            },
            "idempotency_id": idempotency_id,
            "time_created": time_created,  # "2022-07-25T01:11:42.535Z",
            "customer_id": customer_id,
        }
        return payload

    return generate_track_event_payload


@pytest.mark.django_db
class TestTrackEvent:
    """Testing the function-based view track_event
    POST: Return list of customers associated with the organization with API key / user.
    partitions:
        idempotency_already_created = true, false
        customer_id_exists = true, false
    """

    def test_valid_track_event_creates_event(
        self,
        track_event_test_common_setup,
        track_event_payload,
        get_events_with_org_customer_id,
    ):
        # idempotency_already_created=false, customer_id_exists = true
        setup_dict = track_event_test_common_setup(
            idempotency_already_created=False, customer_id_exists=True
        )
        time_created = now_utc()

        payload = track_event_payload(
            setup_dict["idempotency_id"], time_created, setup_dict["customer_id"]
        )
        response = setup_dict["client"].post(
            reverse("track_event"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        # test batch insert after
        events_list = []
        for event in [payload]:
            events_list.append(
                {
                    "idempotency_id": event["idempotency_id"],
                    "event_name": event["event_name"],
                    "properties": event["properties"],
                    "time_created": event["time_created"],
                    "organization": setup_dict["org"],
                    "cust_id": setup_dict["customer"].customer_id,
                }
            )
        write_batch_events_to_db(events_list, setup_dict["org"].pk)
        customer_org_events = get_events_with_org_customer_id(
            setup_dict["org"], setup_dict["customer_id"]
        )
        assert len(customer_org_events) == setup_dict["num_events_in"] + 1
        assert [
            getattr(event, "idempotency_id") for event in customer_org_events
        ].count(setup_dict["idempotency_id"]) == 1

    def test_batch_track_event_creates_event(
        self,
        track_event_test_common_setup,
        track_event_payload,
        get_events_with_org_customer_id,
    ):
        # batch_events=true
        setup_dict = track_event_test_common_setup(
            idempotency_already_created=False, customer_id_exists=True
        )
        time_created = now_utc()

        # test asynchrounous response first
        idem1 = str(uuid.uuid4())
        payload1 = track_event_payload(idem1, time_created, setup_dict["customer_id"])
        idem2 = str(uuid.uuid4())
        payload2 = track_event_payload(idem2, time_created, setup_dict["customer_id"])
        batch_payload = [payload1, payload2]
        response = setup_dict["client"].post(
            reverse("track_event"),
            data=json.dumps(batch_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED

        # test batch insert after
        events_list = []
        for event in batch_payload:
            events_list.append(
                {
                    "idempotency_id": event["idempotency_id"],
                    "cust_id": event["customer_id"],
                    "event_name": event["event_name"],
                    "properties": event["properties"],
                    "time_created": event["time_created"],
                    "organization": setup_dict["org"],
                }
            )
        write_batch_events_to_db(events_list, setup_dict["org"].pk)
        customer_org_events = get_events_with_org_customer_id(
            setup_dict["org"], setup_dict["customer_id"]
        )
        assert len(customer_org_events) == setup_dict["num_events_in"] + 2
        assert [
            getattr(event, "idempotency_id") for event in customer_org_events
        ].count(idem1) == 1
        assert [
            getattr(event, "idempotency_id") for event in customer_org_events
        ].count(idem2) == 1
