import json

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.views.decorators.csrf import csrf_exempt
from djstripe import webhooks
from drf_spectacular.utils import extend_schema, inline_serializer
from metering_billing.models import Invoice
from metering_billing.services.user import user_service
from metering_billing.utils import now_utc
from metering_billing.utils.enums import INVOICE_STATUS, PAYMENT_PROVIDERS
from rest_framework.response import Response
from rest_framework.views import APIView


@csrf_exempt
@webhooks.handler("invoice.paid")
def paid_handler(event):
    invoice = event["data"]["object"]  # dj-stripe invoice object
    id = invoice.id
    print("waddup baby")
    matching_invoice = Invoice.objects.filter(
        external_payment_obj_type=PAYMENT_PROVIDERS.STRIPE, external_payment_obj_id=id
    ).first()
    if matching_invoice:
        matching_invoice.payment_status = INVOICE_STATUS.PAID
        matching_invoice.save()
