import base64
import json
from re import S
from typing import Dict, Union

from django.core.cache import cache
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponseBadRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from metering_billing.exceptions import RepeatedEventIdempotency
from metering_billing.models import Customer, Event

from ..auth_utils import get_organization_from_key
from ..permissions import HasUserAPIKey


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
    Event.objects.create(**event_kwargs)

    return JsonResponse({"status": "Success"}, status=201)


@csrf_exempt
def track_event(request):
    key = HasUserAPIKey().get_key(request)
    prefix, _, _ = key.partition(".")
    organization_pk = cache.get(prefix)
    if not organization_pk:
        organization_pk = get_organization_from_key(key).pk
        cache.set(prefix, organization_pk, 60 * 60 * 24)

    data = load_event(request)
    if not data:
        return HttpResponseBadRequest("No data provided")

    customer_id = data["customer_id"]
    customer_pk_list = Customer.objects.filter(
        organization=organization_pk, customer_id=customer_id
    ).values_list("id", flat=True)
    if len(customer_pk_list) == 0:
        return HttpResponseBadRequest("Customer does not exist")
    else:
        customer_pk = customer_pk_list[0]

    event_idem_list = Event.objects.filter(
        idempotency_id=data["idempotency_id"],
    ).values_list("id", flat=True)
    if len(event_idem_list) > 0:
        return HttpResponseBadRequest("Event idempotency already exists")

    return ingest_event(
        data=data, customer_pk=customer_pk, organization_pk=organization_pk
    )
