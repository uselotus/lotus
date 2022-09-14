import base64
import datetime
import json
import logging
import time
from datetime import timezone
from re import S
from typing import Dict, Union

from django.core.cache import cache
from django.http import HttpRequest, HttpResponseBadRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from metering_billing.models import APIToken, Customer, Event
from metering_billing.tasks import write_batch_events_to_db
from rest_framework.decorators import api_view

from ..permissions import HasUserAPIKey

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
    if event_data is None:
        return None

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
@api_view(http_method_names=["POST"])
def track_event(request):
    key = HasUserAPIKey().get_key(request)
    if key is None:
        return HttpResponseBadRequest("No API key provided")
    prefix, _, _ = key.partition(".")
    organization_pk = cache.get(prefix)
    if not organization_pk:
        api_token = APIToken.objects.filter(prefix=prefix).values_list(
            "organization", "expiry_date"
        )
        if len(api_token) == 0:
            return HttpResponseBadRequest("Invalid API key")
        organization_pk = api_token[0][0]
        expiry_date = api_token[0][1]
        timeout = (
            60 * 60 * 25 * 7
            if expiry_date is None
            else (
                expiry_date - datetime.datetime.now(timezone.utc).astimezone()
            ).total_seconds()
        )
        cache.set(prefix, organization_pk, timeout)

    event_list = load_event(request)
    if not event_list:
        return HttpResponseBadRequest("No data provided")
    if type(event_list) != list:
        event_list = [event_list]
    bad_events = {}
    events_to_insert = []
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

        events_to_insert.append(ingest_event(data, customer_pk, organization_pk))

    cache_tup = cache.get("events_to_insert")
    now = datetime.datetime.now(timezone.utc).astimezone()
    cached_events, last_flush_dt = cache_tup if cache_tup else ([], now)
    cached_events.extend(events_to_insert)
    if len(cached_events) >= 100:
        write_batch_events_to_db.delay(cached_events)
        last_flush_dt = now
        cached_events = []
    cache.set("events_to_insert", (cached_events, last_flush_dt), None)
    if len(bad_events) > 0:
        return JsonResponse(bad_events, status=400)
    else:
        return JsonResponse({"success": True}, status=201)
