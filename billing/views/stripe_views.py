from django.forms.models import model_to_dict
import dateutil.parser as parser
from ..models import Customer, Event, Subscription, BillingPlan
from tenant.models import Tenant
from ..serializers import EventSerializer, SubscriptionSerializer, CustomerSerializer
from rest_framework.views import APIView
from django_q.tasks import async_task
from ..tasks import generate_invoice
from django.db import connection


from rest_framework import viewsets
from ..permissions import HasUserAPIKey
from rest_framework.response import Response
import stripe


def import_stripe_customers(tenant):
    """
    If customer exists in Stripe and also exists in Lotus (compared by matching names), then update the customer's payment provider ID from Stripe.
    """

    stripe.api_key = tenant.stripe_api_key

    stripe_customers_response = stripe.Customer.list()

    customer_list = stripe_customers_response.data

    for stripe_customer in customer_list:
        try:
            customer = Customer.objects.get(name=stripe_customer["name"])
            customer.payment_provider_id = stripe_customer["id"]
            customer.save()
        except Customer.DoesNotExist:
            pass


def issue_stripe_payment_intent(tenant, invoice):

    stripe.api_key = tenant.stripe_api_key

    cost_due = float(invoice.cost_due)
    currency = invoice.currency

    stripe.PaymentIntent.create(
        amount=cost_due,
        currency=currency,
        payment_method_types=["card"],
    )


class InitializeStripeView(APIView):
    permission_classes = [HasUserAPIKey]

    def post(self, request, format=None):
        """
        Initialize Stripe after user inputs an API key.
        """
        schema_name = connection.schema_name
        tenant = Tenant.objects.get(schema_name=schema_name)
        data = request.data
        tenant.stripe_api_key = data["stripe-api-key"]
        tenant.save()

        import_stripe_customers(tenant)

        return Response({"Success": True})
