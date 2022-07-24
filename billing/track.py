from .models import Event, Customer, BillingPlan
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse, HttpRequest
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from django.db import IntegrityError
from django.views.decorators.csrf import csrf_exempt
import json
import base64
from urllib.parse import urlparse
from typing import Dict, Union, List
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import permission_classes


def load_event(request: HttpRequest) -> Union[None, Dict]:
    """
    Loads an event from the request body.
    """
    if request.method != "POST":
        event_data = request.GET.get("data")
    else:
        if request.content_type == "application/json":
            event_data = request.body
        else:
            event_data = request.POST.get("data")
    if event_data is None:
        return None

    try:
        event_data = json.loads(event_data)
    except json.JSONDecodeError:
        # if not, it's probably base64 encoded from other libraries
        event_data = json.loads(
            base64.b64decode(event_data + "===")
            .decode("utf8", "surrogatepass")
            .encode("utf-16", "surrogatepass")
        )
    return event_data


def ingest_event(request, data: dict, user: User) -> None:

    customer_id = data["customer_id"]
    customer = Customer.objects.get(system_id=customer_id)

    db_event = Event.objects.create(
        event_name=data["event_name"],
        idempotency_id=data["idempotency_id"],
        properties=data["properties"],
        customer=customer.id,
        time_created=data["time_created"],
    )
    db_event.save()


@csrf_exempt
@permission_classes((IsAuthenticated))
def track_event(request):
    print(request.headers)
    data = load_event(request)
    if not data:
        return HttpResponseBadRequest("No data provided")
    # token = _get_token(data, request)
    # if not token:
    #     return HttpResponseBadRequest("No api_key set")

    if not isinstance(data, list) and data.get(
        "batch"
    ):  # posthog-python and posthog-ruby
        data = data["batch"]

    if "engage" in request.path_info:  # JS identify call
        data["event"] = "$identify"  # make sure it has an event name

    if isinstance(data, list):
        for i in data:
            try:
                ingest_event(request=request, data=i, ser=request.user)
            except KeyError:
                return JsonResponse(
                    {
                        "code": "validation",
                        "message": "You need to set a distinct_id.",
                        "item": data,
                    },
                    status=400,
                )
    else:
        ingest_event(request=request, data=data, user=request.user)

    return JsonResponse({"status": 1}, status=200)
