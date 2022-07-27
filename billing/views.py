from django.shortcuts import render
from django.forms.models import model_to_dict
from .models import Customer, Event, Subscription, BillingPlan
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


class UsageView(APIView):

    permission_classes = [HasUserAPIKey]

    def get(self, request, format=None):
        """
        Return current usage for a customer during a given billing period.
        """
        customer_id = request.query_params["customer_id"]
        customer = Customer.objects.get(customer_id=customer_id)

        customer_subscriptions = Subscription.objects.filter(
            customer=customer, status="active"
        )

        usage_summary = {}

        for subscription in customer_subscriptions:

            # TODO put these gets in the models
            plan = subscription.billing_plan
            plan_start_timestamp = plan.start_timestamp
            plan_end_timestamp = plan.end_timestamp
            event_name = plan.billable_metric.event_name
            aggregation_type = plan.billable_metric.aggregation_type

            events = Event.objects.filter(
                event_name=event_name,
                time_created__gte=plan_start_timestamp,
                time_created__lte=plan_end_timestamp,
            )

            subtotal_usage = 0.0
            if aggregation_type == "count":
                subtotal_usage = len(events)
            elif aggregation_type == "sum":
                property_name = plan.billable_metric.property_name
                for event in events:
                    subtotal_usage += float(event.properties[property_name])

            usage_summary[plan.name] = {
                "subtotal_usage": subtotal_usage,
                "billing_start_date": plan_start_timestamp,
                "billing_end_date": plan_end_timestamp,
            }

        return Response(usage_summary)
