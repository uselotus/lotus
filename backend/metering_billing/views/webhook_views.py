import stripe
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from metering_billing.exceptions.exceptions import StripeWebhookFailure
from metering_billing.models import Invoice
from metering_billing.utils.enums import INVOICE_STATUS, PAYMENT_PROVIDERS
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.response import Response
from rest_framework.views import APIView

STRIPE_WEBHOOK_SECRET = settings.STRIPE_WEBHOOK_SECRET


def _invoice_paid_handler(event):
    invoice = event["data"]["object"]
    id = invoice.id
    matching_invoice = Invoice.objects.filter(
        external_payment_obj_type=PAYMENT_PROVIDERS.STRIPE, external_payment_obj_id=id
    ).first()
    if matching_invoice:
        matching_invoice.payment_status = INVOICE_STATUS.PAID
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
        return Response(
            "Invalid payload: {}".format(e), status=status.HTTP_400_BAD_REQUEST
        )
    except stripe.error.SignatureVerificationError as e:
        return Response(
            "Invalid signature: {}".format(e), status=status.HTTP_400_BAD_REQUEST
        )

    # Handle the checkout.session.completed event
    if event["type"] == "invoice.paid":
        _invoice_paid_handler(event)

    # Passed signature verification
    return Response(status=status.HTTP_200_OK)
