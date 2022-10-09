import abc
from decimal import Decimal
from typing import Optional, Union

import stripe
from drf_spectacular.utils import extend_schema, inline_serializer
from lotus.settings import SELF_HOSTED, STRIPE_SECRET_KEY
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from metering_billing.auth_utils import parse_organization
from metering_billing.models import Customer, Organization
from metering_billing.utils import (
    INVOICE_STATUS_TYPES,
    PAYMENT_PROVIDERS,
    turn_decimal_into_cents,
)


class PaymentProvider(abc.ABC, APIView):
    @abc.abstractmethod
    def __init__(self):
        """This method will be called from settings.py when checking to see if the payment processor is allowed. You should implement this to capture the necessary credentials from the environment variables and store them in the class instance."""
        pass

    @abc.abstractmethod
    def customer_connected(self, customer: Customer) -> bool:
        """This method will be called in order to gate calls to generate_payment_object."""
        pass

    @abc.abstractmethod
    def organization_connected(self, organization: Organization) -> bool:
        """This method will be called in order to gate calls to generate_payment_object. If the organization is not connected, then won't generate a payment object for the organization."""
        pass

    @abc.abstractmethod
    def working(self) -> bool:
        """In order to prevent errors on object creation, this method will be called to decide whether this payment processor is connected to this instance of Lotus."""
        pass

    @abc.abstractmethod
    def generate_payment_object(
        self, customer: Customer, amount: Decimal, on_behalf_of: Optional[str] = None
    ) -> str:
        """This method will be called when an external payment object needs to be generated (this can vary greatly depending on the payment processor). It should return the id of this object as a string so that the status of the payment can later be updated."""
        pass

    @abc.abstractmethod
    def update_payment_object_status(
        self, payment_object_id: str
    ) -> Union[INVOICE_STATUS_TYPES.PAID, INVOICE_STATUS_TYPES.UNPAID]:
        """This method will be called periodically when the status of a payment object needs to be updated. It should return the status of the payment object, which should be either paid or unpaid."""
        pass

    @abc.abstractmethod
    @extend_schema(
        responses={
            200: inline_serializer(
                "PaymentProviderConnectedResponse",
                fields={"connected": serializers.BooleanField()},
            )
        },
    )
    def get(self, request, format=None) -> Response:
        """
        A payment processor's GET method will be used to determine whether the organization that sent the request is connected to the given payment processor.
        """
        pass

    @abc.abstractmethod
    def post(self, request, format=None) -> Response:
        """
        A payment processor's POST method will be used to connect the organization that sent the request to the given payment processor. You must access the payment_provider_ids field of the organization and the payment processor's name as a key and the organization's payment processor id as its value.
        """
        pass

    @abc.abstractmethod
    def import_customers(self, organization: Organization) -> int:
        """This method will be called periodically to match customers from the payment processor with customers in Lotus. Keep in mind that Customers have a payment_provider field that can be used to determine which payment processor the customer should be connected to, and that the payment_provider_id field can be used to store the id of the customer in the associated payment processor. Return the number of customers that were imported."""
        pass


class StripeConnector(PaymentProvider):
    permission_classes = [IsAuthenticated]

    def __init__(self):
        self.secret_key = STRIPE_SECRET_KEY
        self.self_hosted = SELF_HOSTED

    def working(self):
        return self.secret_key != "" and self.secret_key != None

    def customer_connected(self, customer):
        return (
            customer.payment_provider == PAYMENT_PROVIDERS.STRIPE
            and customer.payment_provider_id != ""
            and customer.payment_provider_id != None
        )

    def organization_connected(self, organization):
        if self.self_hosted:
            return self.secret_key != ""
        else:
            return (
                organization.payment_provider_ids.get(PAYMENT_PROVIDERS.STRIPE, "")
                != ""
            )

    def generate_payment_object(self, customer, amount, organization):
        stripe.api_key = self.secret_key
        amount_cents = turn_decimal_into_cents(amount * 100)
        payment_intent_kwargs = {
            "amount": amount_cents,
            "currency": customer.balance.currency,
            "customer": customer.payment_provider_id,
            "payment_method_types": ["card"],
        }
        if not self.self_hosted:
            payment_intent_kwargs[
                "stripe_account"
            ] = organization.payment_provider_ids.get(PAYMENT_PROVIDERS.STRIPE, "")

        payment_intent = stripe.PaymentIntent.create(**payment_intent_kwargs)
        external_payment_obj_id = payment_intent.id
        return external_payment_obj_id

    def update_payment_object_status(self, payment_object_id):
        stripe.api_key = self.secret_key
        payment_intent = stripe.PaymentIntent.retrieve(payment_object_id)
        if payment_intent.status == "succeeded":
            return INVOICE_STATUS_TYPES.PAID
        else:
            return INVOICE_STATUS_TYPES.UNPAID

    def get(self, request, format=None):
        organization = request.user.organization
        if self.organization_connected(organization):
            return Response({"connected": True})
        else:
            return Response({"connected": False})

    def post(self, request, format=None):
        data = request.data

        if data is None:
            return Response(
                {"success": False, "details": "No data provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        organization = parse_organization(request)
        stripe_code = data["authorization_code"]

        try:
            response = stripe.OAuth.token(
                grant_type="authorization_code",
                code=stripe_code,
            )
        except:
            return Response(
                {"success": False, "details": "Invalid authorization code"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if "error" in response:
            return Response(
                {"success": False, "details": response["error"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        connected_account_id = response["stripe_user_id"]

        org_pp_ids = organization.payment_provider_ids
        org_pp_ids[PAYMENT_PROVIDERS.STRIPE] = connected_account_id
        organization.payment_provider_ids = org_pp_ids
        organization.save()
        self.import_customers(organization)

        return Response({"success": True}, status=status.HTTP_201_CREATED)

    def import_customers(self, organization):
        """
        If customer exists in Stripe and also exists in Lotus (compared by matching names), then update the customer's payment provider ID from Stripe.
        """
        num_cust_added = 0
        org_ppis = organization.payment_provider_ids

        stripe_cust_kwargs = {}
        if org_ppis.get(PAYMENT_PROVIDERS.STRIPE) != "":
            stripe_cust_kwargs["stripe_account"] = org_ppis.get(
                PAYMENT_PROVIDERS.STRIPE
            )
        stripe_customers_response = stripe.Customer.list(**stripe_cust_kwargs)
        for stripe_customer in stripe_customers_response.auto_paging_iter():
            try:
                customer = Customer.objects.get(
                    organization=organization,
                    name=stripe_customer.name,
                    payment_provider=PAYMENT_PROVIDERS.STRIPE,
                )
                customer.payment_provider_id = stripe_customer.id
                customer.save()
                num_cust_added += 1
            except Customer.DoesNotExist:
                pass

        return num_cust_added
