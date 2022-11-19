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
from metering_billing.models import APIToken, Customer, Event
from metering_billing.permissions import HasUserAPIKey
from metering_billing.serializers.model_serializers import *
from metering_billing.tasks import write_batch_events_to_db
from metering_billing.utils import now_utc
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.response import Response

EVENT_CACHE_FLUSH_COUNT = settings.EVENT_CACHE_FLUSH_COUNT

PRODUCER = settings.PRODUCER
EVENTS_TOPIC = settings.EVENTS_TOPIC

logger = logging.getLogger("app_api")  # from LOGGING.loggers in settings.py


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
        if type(event_list) == dict and "batch" in event_list:
            event_list = event_list["batch"]
        else:
            event_list = [event_list]
    bad_events = {}
    events_to_insert = {}

    idem_ids = list(x.get("idempotency_id") for x in event_list)
    repeat_idem = Event.objects.filter(
        idempotency_id__in=idem_ids,
    ).exists()
    for data in event_list:
        customer_id = data.get("customer_id")
        idempotency_id = data.get("idempotency_id", None)
        if not customer_id or not idempotency_id:
            if not idempotency_id:
                bad_events["no_idempotency_id"] = "No idempotency_id provided"
            else:
                bad_events[idempotency_id] = "No customer_id provided"
            continue

        if repeat_idem:
            event_idem_exists = Event.objects.filter(
                idempotency_id=idempotency_id,
            ).exists()
            if event_idem_exists:
                bad_events[idempotency_id] = "Event idempotency already exists"
                continue

        if idempotency_id in events_to_insert:
            bad_events[idempotency_id] = "Duplicate event idempotency in request"
            continue
        try:
            events_to_insert[idempotency_id] = ingest_event(
                data, customer_id, organization_pk
            )

            ## Sent to Redpanda Topic
            PRODUCER.send(
                topic=EVENTS_TOPIC,
                key=customer_id.encode("utf-8"),
                value=json.dumps(events_to_insert[idempotency_id]).encode("utf-8"),
            )

        except Exception as e:
            bad_events[idempotency_id] = str(e)
            continue

    # get the events currently in cache
    cache_tup = cache.get("events_to_insert")
    now = now_utc()
    cached_events, cached_idems, last_flush_dt = (
        cache_tup if cache_tup else ([], set(), now)
    )
    # check that none of the cached events idem_id clashes with this batch's idem
    intersecting_events = set(events_to_insert.keys()).intersection(cached_idems)
    for repeated_idem in intersecting_events:
        bad_events[repeated_idem] = "Event idempotency already exists"
        events_to_insert.pop(repeated_idem)
    # add to insert events
    cached_events.extend(events_to_insert.values())
    cached_idems.update(events_to_insert.keys())
    # check if its necessary to flush
    if len(cached_events) >= EVENT_CACHE_FLUSH_COUNT:
        write_batch_events_to_db.delay(cached_events)
        last_flush_dt = now
        cached_events = []
        cached_idems = set()
    cache.set("events_to_insert", (cached_events, cached_idems, last_flush_dt), None)

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
