from django.forms.models import model_to_dict
import dateutil.parser as parser
from ..models import Customer, Event, Subscription, BillingPlan
from ..serializers import EventSerializer, SubscriptionSerializer, CustomerSerializer
from rest_framework.views import APIView
from django_q.tasks import async_task
from ..tasks import generate_invoice

from rest_framework import viewsets
from ..permissions import HasUserAPIKey
from rest_framework.response import Response


def import_stripe_customers(user):
    pass


class InitializeStripeView(APIView):
    permission_classes = [HasUserAPIKey]

    def post(self, request, format=None):
        """
        Initialize Stripe.
        """
        data = request.data
        user = request.user
        customer = Customer.objects.get(customer_id=data["customer_id"])
        customer.payment_provider = "stripe"
        customer.payment_provider_id = data["stripe_id"]
        customer.save()
        return Response({"success": True})
