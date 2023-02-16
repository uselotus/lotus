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

from metering_billing.models import Customer, Invoice
from metering_billing.payment_processors import PAYMENT_PROCESSOR_MAP
from metering_billing.utils.enums import PAYMENT_PROCESSORS

STRIPE_WEBHOOK_SECRET = settings.STRIPE_WEBHOOK_SECRET
STRIPE_TEST_SECRET_KEY = settings.STRIPE_TEST_SECRET_KEY
STRIPE_LIVE_SECRET_KEY = settings.STRIPE_LIVE_SECRET_KEY


def _invoice_paid_handler(event):
    invoice = event["data"]["object"]
    id = invoice.id
    matching_invoice = Invoice.objects.filter(
        external_payment_obj_type=PAYMENT_PROCESSORS.STRIPE, external_payment_obj_id=id
    ).first()
    if matching_invoice:
        matching_invoice.payment_status = Invoice.PaymentStatus.PAID
        matching_invoice.save()


def _payment_method_refresh_handler(stripe_customer_id):
    matching_customer = Customer.objects.filter(
        integrations__stripe__id=stripe_customer_id
    ).first()
    if matching_customer:
        organization = matching_customer.organization
        if organization.OrganizationType == organization.OrganizationType.PRODUCTION:
            stripe.api_key = STRIPE_LIVE_SECRET_KEY
        else:
            stripe.api_key = STRIPE_TEST_SECRET_KEY
        integrations_dict = matching_customer.integrations
        stripe_payment_methods = []
        if PAYMENT_PROCESSOR_MAP[PAYMENT_PROCESSORS.STRIPE].self_hosted:
            payment_methods = stripe.Customer.list_payment_methods(stripe_customer_id)
        else:
            payment_methods = stripe.Customer.list_payment_methods(
                customer=stripe_customer_id,
                stripe_account=organization.payment_provider_ids.get(
                    PAYMENT_PROCESSORS.STRIPE, {}
                ).get("id"),
            )
        for payment_method in payment_methods.auto_paging_iter():
            pm_dict = {
                "id": payment_method.id,
                "type": payment_method.type,
                "details": {},
            }
            if payment_method.type == "card":
                pm_dict["details"]["brand"] = payment_method.card.brand
                pm_dict["details"]["exp_month"] = payment_method.card.exp_month
                pm_dict["details"]["exp_year"] = payment_method.card.exp_year
                pm_dict["details"]["last4"] = payment_method.card.last4
            stripe_payment_methods.append(pm_dict)
        integrations_dict[PAYMENT_PROCESSORS.STRIPE][
            "payment_methods"
        ] = stripe_payment_methods


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
    if event["type"].startswith("payment_method."):
        payment_method = event["data"]["object"]
        customer = payment_method["customer"]
        _payment_method_refresh_handler(customer)

    # Passed signature verification
    return Response(status=status.HTTP_200_OK)
