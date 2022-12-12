from django.views.decorators.csrf import csrf_exempt
from djstripe import webhooks
from metering_billing.models import Invoice
from metering_billing.utils.enums import INVOICE_STATUS, PAYMENT_PROVIDERS
from rest_framework.response import Response
from rest_framework.views import APIView


@csrf_exempt
@webhooks.handler("invoice.paid")
def paid_handler(event):
    invoice = event["data"]["object"]  # dj-stripe invoice object
    id = invoice.id
    matching_invoice = Invoice.objects.filter(
        external_payment_obj_type=PAYMENT_PROVIDERS.STRIPE, external_payment_obj_id=id
    ).first()
    if matching_invoice:
        matching_invoice.payment_status = INVOICE_STATUS.PAID
        matching_invoice.save()


# @api_view(http_method_names=["POST"])
# @csrf_exempt
# def stripe_webhook_endpoint(request):

#     payload = request.body
#     sig_header = request.META["HTTP_STRIPE_SIGNATURE"]
#     event = None

#     # Try to validate and create a local instance of the event
#     try:
#         event = stripe.Webhook.construct_event(
#             payload, sig_header, settings.STRIPE_SIGNING_SECRET
#         )
#     except ValueError as e:
#         # Invalid payload
#         return SuspiciousOperation(e)
#     except stripe.error.SignatureVerificationError as e:
#         # Invalid signature
#         return SuspiciousOperation(e)

#     # Handle the checkout.session.completed event
#     if event["type"] == "invoice.paid":
#         _invoice_paid_handler(event)

#     # Passed signature verification
#     return HttpResponse(status=200)
