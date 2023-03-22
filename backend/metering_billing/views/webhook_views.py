import stripe
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.response import Response

from metering_billing.kafka.producer import Producer
from metering_billing.models import Invoice
from metering_billing.utils import now_utc
from metering_billing.utils.enums import PAYMENT_PROCESSORS

STRIPE_WEBHOOK_SECRET = settings.STRIPE_WEBHOOK_SECRET
STRIPE_TEST_SECRET_KEY = settings.STRIPE_TEST_SECRET_KEY
STRIPE_LIVE_SECRET_KEY = settings.STRIPE_LIVE_SECRET_KEY
kafka_producer = Producer()


def _invoice_paid_handler(event):
    invoice = event["data"]["object"]
    id = invoice.id
    matching_invoice = Invoice.objects.filter(
        external_payment_obj_type=PAYMENT_PROCESSORS.STRIPE, external_payment_obj_id=id
    ).first()
    if matching_invoice:
        matching_invoice.payment_status = Invoice.PaymentStatus.PAID
        matching_invoice.save()
        kafka_producer.produce_invoice_pay_in_full(
            invoice=matching_invoice,
            payment_date=now_utc(),
            source=PAYMENT_PROCESSORS.STRIPE,
        )


def _invoice_updated_handler(event):
    invoice = event["data"]["object"]
    id = invoice.id
    matching_invoice = Invoice.objects.filter(
        external_payment_obj_type=PAYMENT_PROCESSORS.STRIPE, external_payment_obj_id=id
    ).first()
    if matching_invoice:
        matching_invoice.external_payment_obj_status = invoice.status
        matching_invoice.save()


@api_view(http_method_names=["POST"])
@csrf_exempt
@permission_classes([])
@authentication_classes([])
def stripe_webhook_endpoint(request):
    payload = request.body
    sig_header = request.META["HTTP_STRIPE_SIGNATURE"]
    event = None

    # Try to validate and create a local instance of the event
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        return Response(f"Invalid payload: {e}", status=status.HTTP_400_BAD_REQUEST)
    except stripe.error.SignatureVerificationError as e:
        return Response(f"Invalid signature: {e}", status=status.HTTP_400_BAD_REQUEST)

    # Handle the checkout.session.completed event
    if event["type"] == "invoice.paid":
        _invoice_paid_handler(event)

    if event["type"] == "invoice.updated":
        _invoice_updated_handler(event)

    # Passed signature verification
    return Response(status=status.HTTP_200_OK)
