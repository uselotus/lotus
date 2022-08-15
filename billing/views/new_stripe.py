from telnetlib import STATUS
from django.forms.models import model_to_dict
import dateutil.parser as parser
from ..models import Customer, Event, Subscription, BillingPlan
from tenant.models import Tenant
from ..serializers import EventSerializer, SubscriptionSerializer, CustomerSerializer
from rest_framework.views import APIView
from ..tasks import generate_invoice
from django.db import connection
from http import JsonResponse


from rest_framework import viewsets
from ..permissions import HasUserAPIKey
import stripe
import os

stripe_api_key = os.environ["STRIPE_API_KEY"]


def import_stripe_customers(tenant):
    """
    If customer exists in Stripe and also exists in Lotus (compared by matching names), then update the customer's payment provider ID from Stripe.
    """

    stripe.api_key = tenant.stripe_api_key

    stripe_customers_response = stripe.Customer.list()

    customer_list = stripe_customers_response.data

    for stripe_customer in customer_list.auto_paging_iter():
        try:
            customer = Customer.objects.get(name=stripe_customer["name"])
            customer.payment_provider_id = stripe_customer["id"]
            customer.save()
        except Customer.DoesNotExist:
            pass


def issue_stripe_payment_intent(tenant, invoice):

    stripe.api_key = tenant.stripe_api_key

    cost_due = int(invoice.cost_due)
    currency = invoice.currency

    stripe.PaymentIntent.create(
        amount=cost_due,
        currency=currency,
        payment_method_types=["card"],
    )


class InitializeStripeView(APIView):
    permission_classes = [HasUserAPIKey]

    def get(self, request, format=None):
        """
        Check to see if user has connected their Stripe account.
        """
        pass

    def post(self, request, format=None):
        """
        Initialize Stripe after user inputs an API key.
        """
        data = request.data
        stripe_code = data["authorization_code"]

        response = stripe.OAuth.token(
            grant_type="authorization_code",
            code=stripe_code,
        )

        if "error" in response:
            return JsonResponse(
                {"success": False, "Error": response["error"]}, status=400
            )

        connected_account_id = response["stripe_user_id"]

        organization.stripe_id = connected_account_id

        import_stripe_customers(organization)

        return JsonResponse({"Success": True})
