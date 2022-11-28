import base64
import datetime
import json
import logging
from datetime import timezone
from typing import Dict, Union

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponseBadRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema, inline_serializer
from metering_billing.auth.auth_utils import fast_api_key_validation_and_cache
from metering_billing.kafka.producer import Producer
from metering_billing.models import APIToken, Customer, Event
from metering_billing.permissions import HasUserAPIKey
from metering_billing.serializers.model_serializers import *
from metering_billing.utils import now_utc
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.response import Response

EVENT_CACHE_FLUSH_COUNT = settings.EVENT_CACHE_FLUSH_COUNT

logger = logging.getLogger("app_api")  # from LOGGING.loggers in settings.py
kafka_producer = Producer()


def load_event(request: HttpRequest) -> Union[None, Dict]:
    """
    Loads an event from the request body.
    """
    if request.content_type == "application/json":
        try:
            event_data = json.loads(request.body)
            return event_data
        except json.JSONDecodeError as e:
            print(e)
            # if not, it's probably base64 encoded from other libraries
            event_data = json.loads(
                base64.b64decode(request + "===")
                .decode("utf8", "surrogatepass")
                .encode("utf-16", "surrogatepass")
            )
    else:
        event_data = request.body.decode("utf8")

    return event_data


def ingest_event(data: dict, customer_id: str, organization_pk: int) -> None:
    event_kwargs = {
        "organization_id": organization_pk,
        "cust_id": customer_id,
        "event_name": data["event_name"],
        "idempotency_id": data["idempotency_id"],
        "time_created": data["time_created"],
        "properties": {},
    }
    if "properties" in data:
        event_kwargs["properties"] = data["properties"]
    return event_kwargs


@csrf_exempt
@extend_schema(
    request=inline_serializer(
        "BatchEventSerializer", fields={"batch": EventSerializer(many=True)}
    ),
    responses={
        201: inline_serializer(
            name="TrackEventSuccess",
            fields={
                "success": serializers.ChoiceField(choices=["all", "some"]),
                "failed_events": serializers.DictField(required=False),
            },
        ),
        400: inline_serializer(
            name="TrackEventFailure",
            fields={
                "success": serializers.ChoiceField(choices=["none"]),
                "failed_events": serializers.DictField(),
            },
        ),
    },
)
@api_view(http_method_names=["POST"])
@authentication_classes([])
@permission_classes([])
def track_event(request):
    result, success = fast_api_key_validation_and_cache(request)
    if not success:
        return result
    else:
        organization_pk = result

    try:
        event_list = load_event(request)
    except Exception as e:
        return HttpResponseBadRequest(f"Invalid event data: {e}")
    if not event_list:
        return HttpResponseBadRequest("No data provided")
    if type(event_list) != list:
        if "batch" in event_list:
            event_list = event_list["batch"]
        else:
            event_list = [event_list]

    bad_events = {}
    events_to_insert = set()
    events_by_customer = {}

    for data in event_list:
        customer_id = data.get("customer_id")
        idempotency_id = data.get("idempotency_id", None)
        if not customer_id or not idempotency_id:
            if not idempotency_id:
                bad_events["no_idempotency_id"] = "No idempotency_id provided"
            else:
                bad_events[idempotency_id] = "No customer_id provided"
            continue

        if idempotency_id in events_to_insert:
            bad_events[idempotency_id] = "Duplicate event idempotency in request"
            continue
        try:
            transformed_event = ingest_event(data, customer_id, organization_pk)
            events_to_insert.add(idempotency_id)
            if customer_id not in events_by_customer:
                events_by_customer[customer_id] = [transformed_event]
            else:
                events_by_customer[customer_id].append(transformed_event)
        except Exception as e:
            bad_events[idempotency_id] = str(e)
            continue

    ## Sent to Redpanda Topic
    for customer_id, events in events_by_customer.items():
        stream_events = {"events": events, "organization_id": organization_pk}
        kafka_producer.produce(customer_id, stream_events)

    if len(bad_events) == len(event_list):
        return Response(
            {"success": "none", "failed_events": bad_events},
            status=status.HTTP_400_BAD_REQUEST,
        )
    elif len(bad_events) > 0:
        return JsonResponse(
            {"success": "some", "failed_events": bad_events},
            status=status.HTTP_201_CREATED,
        )
    else:
        return JsonResponse({"success": "all"}, status=status.HTTP_201_CREATED)
