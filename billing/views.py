from django.shortcuts import render
from django.forms.models import model_to_dict
from .models import Customer, Event, Subscription
from .serializers import EventSerializer, SubscriptionSerializer, CustomerSerializer
from rest_framework.views import APIView

from rest_framework import viewsets
from .permissions import HasUserAPIKey
from rest_framework.response import Response


# Create your views here.


class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer


class SubscriptionViewSet(viewsets.ModelViewSet):
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer


class SubscriptionView(APIView):
    permission_classes = [HasUserAPIKey]

    def get(self, request, format=None):
        """
        List active subscriptions. If customer_id is provided, only return subscriptions for that customer.
        """
        if "customer_id" in request.query_params:
            customer_id = request.query_params["customer_id"]
            customer = Customer.objects.get(customer_id=customer_id)
            subscriptions = Subscription.objects.filter(
                customer=customer, status="active"
            )
            serializer = SubscriptionSerializer(subscriptions, many=True)
            return Response(serializer.data)
        else:
            subscriptions = Subscription.objects.filter(status="active")
            serializer = SubscriptionSerializer(subscriptions, many=True)
            return Response(serializer.data)

    def post(self, request, format=None):
        """
        Create a new subscription, joining a customer and a plan.
        """
        data = request.data
        customer_qs = Customer.objects.filter(customer_id=data["customer_id"])
        if len(customer_qs) < 1:
            return Response(
                {
                    "error": "Customer with customer_id {} does not exist".format(
                        data["customer_id"]
                    )
                },
                status=400,
            )
        else:
            customer = customer_qs[0]
        subscription = Subscription.objects.create(
            customer=customer,
            billing_plan=data["billing_plan"],
            status="active",
            time_created=data["time_created"],
        )
        subscription.save()
        serializer = SubscriptionSerializer(subscription)
        return Response(serializer.data)


class CustomerView(APIView):

    permission_classes = [HasUserAPIKey]

    def get(self, request, format=None):
        """
        Return a list of all customers.
        """
        customers = Customer.objects.all()
        serializer = CustomerSerializer(customers, many=True)
        return Response(serializer.data)

    def post(self, request, format=None):
        """
        Create a new customer.
        """
        serializer = CustomerSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)
