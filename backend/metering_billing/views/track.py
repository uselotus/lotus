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
from metering_billing.models import APIToken, Customer, Event
from metering_billing.serializers.internal_serializers import *
from metering_billing.serializers.model_serializers import *
from metering_billing.tasks import posthog_capture_track, write_batch_events_to_db
from metering_billing.utils import now_utc
from rest_framework.decorators import api_view

EVENT_CACHE_FLUSH_COUNT = settings.EVENT_CACHE_FLUSH_COUNT

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


def ingest_event(data: dict, customer_pk: int, organization_pk: int) -> None:
    event_kwargs = {
        "organization_id": organization_pk,
        "customer_id": customer_pk,
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
def track_event(request):
    try:
        key = request.META.get("HTTP_X_API_KEY")
    except KeyError:
        meta_dict = {k.lower(): v for k, v in request.META}
        if "http_x_api_key".lower() in meta_dict:
            key = meta_dict["http_x_api_key"]
        else:
            raise KeyError("No API key found in request")
    prefix, _, _ = key.partition(".")
    organization_pk = cache.get(prefix)
    if not organization_pk:
        api_token = APIToken.objects.filter(prefix=prefix).values_list(
            "organization",
            "expiry_date",
        )
        if len(api_token) == 0:
            return HttpResponseBadRequest("Invalid API key")
        organization_pk = api_token[0][0]
        expiry_date = api_token[0][1]
        timeout = (
            60 * 60 * 25 * 7
            if expiry_date is None
            else (expiry_date - now_utc()).total_seconds()
        )
        cache.set(prefix, organization_pk, timeout)
    event_list = load_event(request)
    if not event_list:
        return HttpResponseBadRequest("No data provided")
    if type(event_list) != list:
        if type(event_list) == dict and "batch" in event_list:
            event_list = event_list["batch"]
        else:
            event_list = [event_list]
    bad_events = {}
    events_to_insert = {}
    for data in event_list:
        customer_id = data["customer_id"]
        customer_cache_key = f"{organization_pk}-{customer_id}"
        customer_pk = cache.get(customer_cache_key)
        if customer_pk is None:
            customer_pk_list = Customer.objects.filter(
                organization=organization_pk, customer_id=customer_id
            ).values_list("id", flat=True)
            if len(customer_pk_list) == 0:
                bad_events[data["idempotency_id"]] = "Customer does not exist"
                continue
            else:
                customer_pk = customer_pk_list[0]
                cache.set(customer_cache_key, customer_pk, 60 * 60 * 24 * 7)

        event_idem_ct = (
            Event.objects.filter(
                idempotency_id=data["idempotency_id"],
            )
            .values_list("id", flat=True)
            .count()
        )
        if event_idem_ct > 0:
            bad_events[data["idempotency_id"]] = "Event idempotency already exists"
            continue

        if data["idempotency_id"] in events_to_insert:
            bad_events[
                data["idempotency_id"]
            ] = "Duplicate event idempotency in request"
            continue

        events_to_insert[data["idempotency_id"]] = ingest_event(
            data, customer_pk, organization_pk
        )

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
    posthog_capture_track.delay(organization_pk, len(event_list), len(events_to_insert))
    # check if its necessary to flush
    if len(cached_events) >= EVENT_CACHE_FLUSH_COUNT:
        write_batch_events_to_db.delay(cached_events)
        last_flush_dt = now
        cached_events = []
        cached_idems = set()
    cache.set("events_to_insert", (cached_events, cached_idems, last_flush_dt), None)

    if len(bad_events) == len(event_list):
        return JsonResponse(
            {"success": "none", "failed_events": bad_events}, status=400
        )
    elif len(bad_events) > 0:
        return JsonResponse(
            {"success": "some", "failed_events": bad_events}, status=201
        )
    else:
        return JsonResponse({"success": "all"}, status=201)
