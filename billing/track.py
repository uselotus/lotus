from re import S
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
from rest_framework.decorators import permission_classes
from rest_framework_api_key.permissions import HasAPIKey
from rest_framework.permissions import IsAuthenticated


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
            event_data = request.POST

    if event_data is None:
        return None

    if not isinstance(event_data, str):
        return event_data

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


def ingest_event(request, data: dict, customer: Customer) -> None:

    db_event = Event.objects.create(
        event_name=data["event_name"],
        idempotency_id=data["idempotency_id"],
        properties=data["properties"],
        customer=customer,
        time_created=data["time_created"],
    )
    db_event.save()


@csrf_exempt
@permission_classes((IsAuthenticated, HasAPIKey))
def track_event(request):
    print(request.keys())
    data = load_event(request)
    if not data:
        return HttpResponseBadRequest("No data provided")
    # token = _get_token(data, request)
    # if not token  :
    #     return HttpResponseBadRequest("No api_key set")

    if not isinstance(data, list) and data.get(
        "batch"
    ):  # posthog-python and posthog-ruby
        data = data["batch"]

    customer_id = data["customer_id"]
    try:
        customer = Customer.objects.get(external_id=customer_id)
    except Customer.DoesNotExist:
        return HttpResponseBadRequest("Customer does not exist")

    if isinstance(data, list):
        for i in data:
            try:
                ingest_event(request=request, data=i, customer=customer)
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
        ingest_event(request=request, data=data, customer=customer)

    return JsonResponse({"status": "Success"}, status=200)
