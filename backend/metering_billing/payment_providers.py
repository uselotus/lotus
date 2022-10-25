import abc
from decimal import Decimal
from typing import Optional, Union

import stripe
from django.conf import settings
from django.db.models import Q
from metering_billing.serializers.payment_provider_serializers import (
    PaymentProviderPostResponseSerializer,
)
from metering_billing.utils import turn_decimal_into_cents
from metering_billing.utils.enums import INVOICE_STATUS, PAYMENT_PROVIDERS
from requests import Response
from rest_framework import serializers, status

SELF_HOSTED = settings.SELF_HOSTED
STRIPE_SECRET_KEY = settings.STRIPE_SECRET_KEY


class PaymentProvider(abc.ABC):
    @abc.abstractmethod
    def __init__(self):
        """This method will be called from settings.py when checking to see if the payment processor is allowed. You should implement this to capture the necessary credentials from the environment variables and store them in the class instance."""
        pass

    @abc.abstractmethod
    def customer_connected(self, customer) -> bool:
        """This method will be called in order to gate calls to generate_payment_object."""
        pass

    @abc.abstractmethod
    def organization_connected(self, organization) -> bool:
        """This method will be called in order to gate calls to generate_payment_object. If the organization is not connected, then won't generate a payment object for the organization."""
        pass

    @abc.abstractmethod
    def working(self) -> bool:
        """In order to prevent errors on object creation, this method will be called to decide whether this payment processor is connected to this instance of Lotus."""
        pass

    @abc.abstractmethod
    def generate_payment_object(
        self, customer, amount: Decimal, on_behalf_of: Optional[str] = None
    ) -> str:
        """This method will be called when an external payment object needs to be generated (this can vary greatly depending on the payment processor). It should return the id of this object as a string so that the status of the payment can later be updated."""
        pass

    @abc.abstractmethod
    def update_payment_object_status(
        self, payment_object_id: str
    ) -> Union[INVOICE_STATUS.PAID, INVOICE_STATUS.UNPAID]:
        """This method will be called periodically when the status of a payment object needs to be updated. It should return the status of the payment object, which should be either paid or unpaid."""
        pass

    @abc.abstractmethod
    def import_customers(self, organization) -> int:
        """This method will be called periodically to match customers from the payment processor with customers in Lotus. Keep in mind that Customers have a payment_provider field that can be used to determine which payment processor the customer should be connected to, and that the payment_provider_id field can be used to store the id of the customer in the associated payment processor. Return the number of customers that were imported."""
        pass

    @abc.abstractmethod
    def get_post_data_serializer(self) -> serializers.Serializer:
        """This method will be called when a POST request is made to the payment provider endpoint. It should return a serializer that can be used to validate the data that is sent in the POST request. The data sent in the request will naturally be dependent on the payment processor, so we use this method to dynamically use the serializer."""
        pass

    @abc.abstractmethod
    def handle_post(self, data, organization) -> PaymentProviderPostResponseSerializer:
        """This method will be called when a POST request is made to the payment provider endpoint. It should return a response that will be sent back to the user."""
        pass


class StripeConnector(PaymentProvider):
    def __init__(self):
        self.secret_key = STRIPE_SECRET_KEY
        self.self_hosted = SELF_HOSTED

    def working(self):
        return self.secret_key != "" and self.secret_key != None

    def customer_connected(self, customer):
        pp_ids = customer.payment_providers
        stripe_dict = pp_ids.get(PAYMENT_PROVIDERS.STRIPE, None)
        stripe_id = stripe_dict.get("id", None)
        return stripe_id is not None

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
            "customer": customer.payment_providers[PAYMENT_PROVIDERS.STRIPE]["id"],
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
            return INVOICE_STATUS.PAID
        else:
            return INVOICE_STATUS.UNPAID

    def import_customers(self, organization):
        """
        Imports customers from Stripe. If they already exist (by checking that either they already have their Stripe ID in our system, or seeing that they have the same email address), then we update the Stripe section of payment_providers dict to reflect new information. If they don't exist, we create them (not as a Lotus customer yet, just as a Stripe customer).
        """
        from metering_billing.models import Customer

        num_cust_added = 0
        org_ppis = organization.payment_provider_ids

        stripe_cust_kwargs = {}
        if org_ppis.get(PAYMENT_PROVIDERS.STRIPE) != "":
            stripe_cust_kwargs["stripe_account"] = org_ppis.get(
                PAYMENT_PROVIDERS.STRIPE
            )
        try:
            stripe_customers_response = stripe.Customer.list(**stripe_cust_kwargs)
            for stripe_customer in stripe_customers_response.auto_paging_iter():
                stripe_id = stripe_customer.id
                stripe_email = stripe_customer.email
                stripe_metadata = stripe_customer.metadata
                stripe_name = stripe_customer.name
                stripe_name = stripe_name if stripe_name else "no_stripe_name"
                stripe_currency = stripe_customer.currency
                customer = Customer.objects.filter(
                    Q(payment_providers__stripe__id=stripe_id) | Q(email=stripe_email),
                    organization=organization,
                ).first()
                if customer:  # customer exists in system already
                    cur_pp_dict = customer.payment_providers[PAYMENT_PROVIDERS.STRIPE]
                    cur_pp_dict["id"] = stripe_id
                    cur_pp_dict["email"] = stripe_email
                    cur_pp_dict["metadata"] = stripe_metadata
                    cur_pp_dict["name"] = stripe_name
                    cur_pp_dict["currency"] = stripe_currency
                    customer.payment_providers[PAYMENT_PROVIDERS.STRIPE] = cur_pp_dict
                    cur_sources = customer.sources
                    if len(cur_sources) == 0:
                        cur_sources = []
                    if PAYMENT_PROVIDERS.STRIPE not in cur_sources:
                        cur_sources.append(PAYMENT_PROVIDERS.STRIPE)
                    customer.sources = cur_sources
                    customer.save()
                else:
                    customer_kwargs = {
                        "organization": organization,
                        "name": stripe_name,
                        "email": stripe_email,
                        "payment_providers": {
                            PAYMENT_PROVIDERS.STRIPE: {
                                "id": stripe_id,
                                "email": stripe_email,
                                "metadata": stripe_metadata,
                                "name": stripe_name,
                                "currency": stripe_currency,
                            }
                        },
                        "sources": [PAYMENT_PROVIDERS.STRIPE],
                    }
                    customer = Customer.objects.create(**customer_kwargs)
                    num_cust_added += 1
        except Exception as e:
            print(e)

        return num_cust_added

    def get_post_data_serializer(self) -> serializers.Serializer:
        class StripePostRequestDataSerializer(serializers.Serializer):
            authorization_code = serializers.CharField()
            stripe_user_id = serializers.CharField()

        return StripePostRequestDataSerializer

    def handle_post(self, data, organization) -> PaymentProviderPostResponseSerializer:
        try:
            response = stripe.OAuth.token(
                grant_type="authorization_code",
                code=data["authorization_code"],
            )
        except:
            return Response(
                {"success": False, "details": "Invalid authorization code"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        org_pp_ids = organization.payment_provider_ids
        org_pp_ids[PAYMENT_PROVIDERS.STRIPE] = response["stripe_user_id"]
        organization.payment_provider_ids = org_pp_ids
        organization.save()
        self.import_customers(organization)

        response = {
            "payment_processor": PAYMENT_PROVIDERS.STRIPE,
            "data": {
                "success": True,
            },
        }
        serializer = PaymentProviderPostResponseSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        return Response(validated_data, status=status.HTTP_200_OK)


PAYMENT_PROVIDER_MAP = {
    PAYMENT_PROVIDERS.STRIPE: StripeConnector(),
}
