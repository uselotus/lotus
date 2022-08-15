from re import S
from metering_billing.models import Event, Customer, BillingPlan
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse, HttpRequest
from rest_framework.authtoken.models import Token
from rest_framework.parsers import JSONParser
from django.db import IntegrityError
from django.views.decorators.csrf import csrf_exempt
import json
import base64
from urllib.parse import urlparse
from typing import Dict, Union, List
from rest_framework.decorators import permission_classes
from .permissions import HasUserAPIKey
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view


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


def ingest_event(request, data: dict, customer: Customer) -> None:

    idepotency_id_query = Event.objects.filter(idempotency_id=data["idempotency_id"]).count()
    print(idepotency_id_query)
    if idepotency_id_query > 0:
        return JsonResponse({"detail": "This event record already exists", "status": "Failure"}, status=409)


    db_event = Event.objects.create(
        event_name=data["event_name"],
        idempotency_id=data["idempotency_id"],
        customer=customer,
        time_created=data["time_created"],
    )
    if "properties" in data:
        db_event.properties = data["properties"]
    db_event.save()
    return JsonResponse({"status": "Success"}, status=200)


@csrf_exempt
def track_event(request):
    # Check Permissions
    permissions = HasUserAPIKey()
    if not (permissions.has_permission(request, "track_event")):
        return HttpResponseBadRequest("Invalid API Key or No API Key provided")

    data = load_event(request)
    if not data:
        return HttpResponseBadRequest("No data provided")
    customer_id = data["customer_id"]
    try:
        customer = Customer.objects.get(customer_id=customer_id)
    except Customer.DoesNotExist:
        return HttpResponseBadRequest("Customer does not exist")

    if isinstance(data, list):
        for i in data:
            try:
                return ingest_event(request=request, data=i, customer=customer)
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
        return ingest_event(request=request, data=data, customer=customer)

