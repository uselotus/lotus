import json
import uuid
from datetime import datetime

import pytest
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from metering_billing.models import Event
from model_bakery import baker
from rest_framework import status


@pytest.fixture
def track_event_test_common_setup(generate_org_and_api_key, add_customers_to_org, api_client_with_api_key_auth, create_events_with_org_customer):
    def do_track_event_test_common_setup(*, idempotency_already_created, customer_id_exists):
        #set up organizations and api keys
        org, key = generate_org_and_api_key()
        setup_dict = {
            "org":org,
            "key":key,
        }

        #set up the client with the appropriate api key spec
        client = api_client_with_api_key_auth(key)
        setup_dict["client"] = client

        #set up customers
        customer, = add_customers_to_org(org, n=1)
        setup_dict["customer"] = customer

        #set up existing events
        num_events_in = 10
        setup_dict["num_events_in"] = num_events_in
        event_set = create_events_with_org_customer(org, customer, num_events_in)                

        #setup repeat idempotency id
        if idempotency_already_created:
            idempotency_id = event_set[0].idempotency_id
        else:
            idempotency_id = str(uuid.uuid4())
        setup_dict["idempotency_id"] = idempotency_id
        
        #setup whether customer id exists
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
                        "test_field_2": "test_value_2"
            },
            "idempotency_id": idempotency_id,
            "time_created": time_created,#"2022-07-25T01:11:42.535Z",
            "customer_id": customer_id,
        }
        return payload
    return generate_track_event_payload

@pytest.mark.django_db
class TestTrackEvent():
    """Testing the function-based view track_event
    POST: Return list of customers associated with the organization with API key / user.
    partitions:
        idempotency_already_created = true, false
        customer_id_exists = true, false
    """
    def test_valid_track_event_creates_event(self, track_event_test_common_setup, track_event_payload, get_events_with_org_customer_id):
        #idempotency_already_created=false, customer_id_exists = true
        setup_dict = track_event_test_common_setup(
            idempotency_already_created = False,
            customer_id_exists = True
        )
        time_created = datetime.now()

        payload = track_event_payload(setup_dict["idempotency_id"], time_created, setup_dict["customer_id"])
        response = setup_dict['client'].post(
            reverse("track_event"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        customer_org_events = get_events_with_org_customer_id(setup_dict['org'], setup_dict['customer_id'])
        assert len(customer_org_events) == setup_dict['num_events_in']+1
        assert [getattr(event, "idempotency_id") for event in customer_org_events].count(setup_dict['idempotency_id']) == 1

    def test_request_invalid_if_customer_dont_exist(self, track_event_test_common_setup, track_event_payload, get_events_with_org_customer_id, get_events_with_org):
        #idempotency_already_created=false, customer_id_exists = true
        setup_dict = track_event_test_common_setup(
            idempotency_already_created = False,
            customer_id_exists = False
        )
        time_created = datetime.now()

        payload = track_event_payload(setup_dict["idempotency_id"], time_created, setup_dict["customer_id"])
        response = setup_dict['client'].post(
            reverse("track_event"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        customer_org_events = get_events_with_org_customer_id(setup_dict['org'], setup_dict['customer_id'])
        assert len(customer_org_events) == 0
        org_events = get_events_with_org(setup_dict['org'])
        assert len(org_events) == setup_dict["num_events_in"]

    def test_request_invalid_if_idempotency_id_repeared(self, track_event_test_common_setup, track_event_payload, get_events_with_org_customer_id, get_events_with_org):
        #idempotency_already_created=false, customer_id_exists = true
        setup_dict = track_event_test_common_setup(
            idempotency_already_created = True,
            customer_id_exists = True
        )
        time_created = datetime.now()

        payload = track_event_payload(setup_dict["idempotency_id"], time_created, setup_dict["customer_id"])
        response = setup_dict['client'].post(
            reverse("track_event"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        customer_org_events = get_events_with_org_customer_id(setup_dict['org'], setup_dict['customer_id'])
        assert len(customer_org_events) == setup_dict['num_events_in']
        assert [getattr(event, "idempotency_id") for event in customer_org_events].count(setup_dict['idempotency_id']) == 1
