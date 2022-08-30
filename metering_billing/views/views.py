import math
from datetime import datetime

import dateutil.parser as parser
import stripe
from django.db import connection
from django.http import HttpResponseBadRequest, JsonResponse
from lotus.settings import STRIPE_SECRET_KEY
from metering_billing.models import (
    BillingPlan,
    Customer,
    Event,
    PlanComponent,
    Subscription,
)
from metering_billing.permissions import HasUserAPIKey
from metering_billing.serializers import (
    BillingPlanSerializer,
    CustomerSerializer,
    EventSerializer,
    PlanComponentSerializer,
    SubscriptionSerializer,
)
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..utils import get_customer_usage, parse_organization

stripe.api_key = STRIPE_SECRET_KEY


class PlansView(APIView):
    permission_classes = [IsAuthenticated | HasUserAPIKey]

    def get(self, request, format=None):

        parsed_org = parse_organization(request)
        if type(parsed_org) == Response:
            return parsed_org
        else:
            organization = parsed_org
        plans = BillingPlan.objects.filter(organization=organization)

        plans_list = []

        for plan in plans:
            plan_breakdown = {}
            plan_data = BillingPlanSerializer(plan).data
            plan_breakdown["name"] = plan_data["name"]

            components = PlanComponent.objects.filter(billing_plan=plan)

            components_list = []
            for component in components:
                component_breakdown = {}
                component_data = PlanComponentSerializer(component).data
                component_breakdown["free_metric_quantity"] = int(
                    component_data["free_metric_quantity"]
                )
                component_breakdown["cost_per_metric"] = component_data[
                    "cost_per_metric"
                ]
                component_breakdown["unit_per_cost"] = component_data[
                    "metric_amount_per_cost"
                ]
                component_breakdown[
                    "metric_name"
                ] = component.billable_metric.event_name
                component_breakdown[
                    "aggregation_type"
                ] = component.billable_metric.aggregation_type.upper()
                component_breakdown[
                    "property_name"
                ] = component.billable_metric.property_name

                components_list.append(component_breakdown)
            plan_breakdown["components"] = components_list
            plan_breakdown["billing_interval"] = plan_data["interval"]
            plan_breakdown["description"] = plan_data["description"]
            plan_breakdown["flat_rate"] = plan_data["flat_rate"]
        return JsonResponse(plans_list, safe=False)


class SubscriptionView(APIView):
    permission_classes = [IsAuthenticated | HasUserAPIKey]

    def get(self, request, format=None):
        """
        List active subscriptions. If customer_id is provided, only return subscriptions for that customer.
        """

        parsed_org = parse_organization(request)
        if type(parsed_org) == Response:
            return parsed_org
        else:
            organization = parsed_org
        if "customer_id" in request.query_params:
            customer_id = request.query_params["customer_id"]
            try:
                customer = Customer.objects.get(
                    customer_id=customer_id, organization=organization
                )
            except Customer.DoesNotExist:
                return HttpResponseBadRequest("Customer does not exist")
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
        parsed_org = parse_organization(request)
        if type(parsed_org) == Response:
            return parsed_org
        else:
            organization = parsed_org

        customer_qs = Customer.objects.filter(
            customer_id=data["customer_id"], organization=organization
        )
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

        plan_qs = BillingPlan.objects.filter(
            plan_id=data["plan_id"], organization=organization
        )
        if len(plan_qs) < 1:
            return Response(
                {
                    "error": "Plan with plan_id {} does not exist".format(
                        data["plan_id"]
                    )
                },
                status=400,
            )
        else:
            plan = plan_qs[0]

        start_date = parser.parse(data["start_date"])
        end_date = plan.subscription_end_date(start_date)

        overlapping_subscriptions = Subscription.objects.filter(
            organization=organization,
            customer=customer,
            start_date__lte=end_date,
            end_date__gte=start_date,
            billing_plan=plan,
        )
        if len(overlapping_subscriptions) != 0:
            return Response(
                {
                    "error": f"A subscription for customer {customer.name}, plan {plan.name} overlaps with specified date ranges {start_date} to {end_date}"
                },
                status=409,
            )
        subscription_kwargs = {
            "organization": organization,
            "customer": customer,
            "start_date": start_date,
            "end_date": end_date,
            "billing_plan": plan,
        }
        if data.get("auto_renew"):
            subscription_kwargs["auto_renew"] = data.get("auto_renew")
        if data.get("next_plan"):
            subscription_kwargs["next_plan"] = data.get("next_plan")
        if end_date < datetime.now():
            subscription_kwargs["status"] = "ended"
        elif start_date < datetime.now():
            subscription_kwargs["status"] = "active"
        subscription = Subscription.objects.create(**subscription_kwargs)
        serializer = SubscriptionSerializer(subscription)

        return Response(serializer.data, status=201)


class CustomerView(APIView):

    permission_classes = [IsAuthenticated | HasUserAPIKey]

    def get(self, request, format=None):
        """
        Return a list of all customers.
        """
        parsed_org = parse_organization(request)
        if type(parsed_org) == Response:
            return parsed_org
        else:
            organization = parsed_org

        customers = Customer.objects.filter(organization=organization)
        serializer = CustomerSerializer(customers, many=True)
        customer_list = []
        for customer in customers:
            serializer = CustomerSerializer(customer)
            cust_data = serializer.data
            cust_data["plan"] = {
                "name": customer.get_billing_plan_name(),
                "color": "green",
            }
            del cust_data["organization"]
            customer_list.append(cust_data)
        return Response(customer_list)

    def post(self, request, format=None):
        """
        Create a new customer.
        """
        parsed_org = parse_organization(request)
        if type(parsed_org) == Response:
            return parsed_org
        else:
            organization = parsed_org
        customer_data = request.data.copy()
        customer_data["organization"] = organization.pk
        serializer = CustomerSerializer(data=customer_data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class UsageViewForCustomer(APIView):

    permission_classes = [IsAuthenticated | HasUserAPIKey]

    def get(self, request, format=None):
        """
        Return current usage for a customer during a given billing period.
        """
        parsed_org = parse_organization(request)
        if type(parsed_org) == Response:
            return parsed_org
        else:
            organization = parsed_org

        customer_id = request.query_params["customer_id"]
        customer_qs = Customer.objects.filter(
            organization=organization, customer_id=customer_id
        )

        if len(customer_qs) < 1:
            return Response(
                {
                    "error": "Customer with customer_id {} does not exist".format(
                        customer_id
                    )
                },
                status=400,
            )
        else:
            customer = customer_qs[0]

        usage_summary = get_customer_usage(customer)

        usage_summary["# of Active Subscriptions"] = len(usage_summary)
        return Response(usage_summary)


def import_stripe_customers(organization):
    """
    If customer exists in Stripe and also exists in Lotus (compared by matching names), then update the customer's payment provider ID from Stripe.
    """

    stripe_customers_response = stripe.Customer.list(
        stripe_account=organization.stripe_id
    )

    for stripe_customer in stripe_customers_response.auto_paging_iter():
        try:
            customer = Customer.objects.get(name=stripe_customer["name"])
            customer.payment_provider_id = stripe_customer["id"]
            customer.save()
        except Customer.DoesNotExist:
            pass


def issue_stripe_payment_intent(invoice):

    cost_due = int(invoice.cost_due * 100)
    currency = (invoice.currency).lower()

    stripe.PaymentIntent.create(
        amount=cost_due,
        currency=currency,
        payment_method_types=["card"],
        stripe_account=invoice.organization.stripe_id,
    )


def retrive_stripe_payment_intent(invoice):
    payment_intent = stripe.PaymentIntent.retrieve(
        invoice.payment_intent_id,
        stripe_account=invoice.organization.stripe_id,
    )
    return payment_intent


class InitializeStripeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        """
        Check to see if user has connected their Stripe account.
        """

        organization = request.user.organization
        if organization is None:
            return Response({"error": "User does not have an organization"}, status=403)

        stripe_id = organization.stripe_id

        if stripe_id and len(stripe_id) > 0:
            return JsonResponse({"connected": True})
        else:
            return JsonResponse({"connected": False})

    def post(self, request, format=None):
        """
        Initialize Stripe after user inputs an API key.
        """

        data = request.data

        if data is None:
            return JsonResponse({"details": "No data provided"}, status=400)

        organization = request.user.organization
        if organization is None:
            return Response({"error": "User does not have an organization"}, status=403)
        stripe_code = data["authorization_code"]

        try:
            response = stripe.OAuth.token(
                grant_type="authorization_code",
                code=stripe_code,
            )
        except:
            return JsonResponse(
                {"success": False, "details": "Invalid authorization code"}, status=400
            )

        if "error" in response:
            return JsonResponse(
                {"success": False, "details": response["error"]}, status=400
            )

        connected_account_id = response["stripe_user_id"]

        organization.stripe_id = connected_account_id

        import_stripe_customers(organization)

        organization.save()

        return JsonResponse({"Success": True})


class SubscriptionView(APIView):
    permission_classes = [IsAuthenticated | HasUserAPIKey]

    def get(self, request, format=None):
        """
        List active subscriptions. If customer_id is provided, only return subscriptions for that customer.
        """

        parsed_org = parse_organization(request)
        if type(parsed_org) == Response:
            return parsed_org
        else:
            organization = parsed_org
        if "customer_id" in request.query_params:
            customer_id = request.query_params["customer_id"]
            try:
                customer = Customer.objects.get(
                    customer_id=customer_id, organization=organization
                )
            except Customer.DoesNotExist:
                return HttpResponseBadRequest("Customer does not exist")
            subscriptions = Subscription.objects.filter(
                customer=customer, status="active"
            )
            serializer = SubscriptionSerializer(subscriptions, many=True)
            return Response(serializer.data)
        else:
            subscriptions = Subscription.objects.filter(status="active")
            serializer = SubscriptionSerializer(subscriptions, many=True)
            return Response(serializer.data)
