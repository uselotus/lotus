import abc
import datetime
from decimal import Decimal
from re import S
from typing import Union
from urllib.parse import urlencode

import pytz
import stripe
from django.conf import settings
from django.db.models import Q
from djmoney.money import Money
from metering_billing.serializers.payment_provider_serializers import (
    PaymentProviderPostResponseSerializer,
    SinglePaymentProviderSerializer,
)
from metering_billing.utils import decimal_to_cents
from metering_billing.utils.enums import INVOICE_STATUS, PAYMENT_PROVIDERS
from rest_framework import serializers, status
from rest_framework.response import Response

SELF_HOSTED = settings.SELF_HOSTED
STRIPE_SECRET_KEY = settings.STRIPE_SECRET_KEY
VITE_STRIPE_CLIENT = settings.VITE_STRIPE_CLIENT
VITE_API_URL = settings.VITE_API_URL


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
    def generate_payment_object(self, invoice) -> str:
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

    @abc.abstractmethod
    def get_redirect_url(self) -> str:
        """The link returned by this method will be called when a user clicks on the connect button for a payment processor. It should return a link that the user will be redirected to in order to connect their account to the payment processor."""
        pass

    @abc.abstractmethod
    def import_payment_objects(self, organization) -> dict[str, list[str]]:
        """Similar to the import_customers method, this method will be called periodically to match invoices from the payment processor with invoices in Lotus. Keep in mind that Invoices have a payment_provider field that can be used to determine which payment processor the invoice should be connected to, and that the payment_provider_id field can be used to store the id of the invoice in the associated payment processor. Return a dictionary mapping customer ids to lists of Lotus Invoice objects that were created from the imports."""
        pass


class StripeConnector(PaymentProvider):
    def __init__(self):
        self.secret_key = STRIPE_SECRET_KEY
        self.self_hosted = SELF_HOSTED
        redirect_dict = {
            "response_type": "code",
            "scope": "read_write",
            "client_id": VITE_STRIPE_CLIENT,
            "redirect_uri": VITE_API_URL + "redirectstripe",
        }
        qstr = urlencode(redirect_dict)
        if not self.self_hosted:
            self.redirect_url = "https://connect.stripe.com/oauth/authorize?" + qstr
        else:
            self.redirect_url = ""

    def working(self) -> bool:
        return self.secret_key != "" and self.secret_key != None

    def customer_connected(self, customer) -> bool:
        pp_ids = customer.integrations
        stripe_dict = pp_ids.get(PAYMENT_PROVIDERS.STRIPE, {})
        stripe_id = stripe_dict.get("id", None)
        return stripe_id is not None

    def organization_connected(self, organization) -> bool:
        if self.self_hosted:
            return self.secret_key != "" and self.secret_key != None
        else:
            return (
                organization.payment_provider_ids.get(PAYMENT_PROVIDERS.STRIPE, "")
                != ""
            )

    def update_payment_object_status(self, payment_object_id):
        stripe.api_key = self.secret_key
        invoice = stripe.PaymentIntent.retrieve(payment_object_id)
        if invoice.status == "succeeded":
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
        if org_ppis.get(PAYMENT_PROVIDERS.STRIPE) not in ["", None]:
            # this is to get "on behalf" of someone
            stripe_cust_kwargs["stripe_account"] = org_ppis.get(
                PAYMENT_PROVIDERS.STRIPE
            )
        try:
            stripe_customers_response = stripe.Customer.list(**stripe_cust_kwargs)
            for i, stripe_customer in enumerate(
                stripe_customers_response.auto_paging_iter()
            ):
                stripe_id = stripe_customer.id
                stripe_email = stripe_customer.email
                stripe_metadata = stripe_customer.metadata
                stripe_name = stripe_customer.customer_name
                stripe_name = stripe_name if stripe_name else "no_stripe_name"
                stripe_currency = stripe_customer.currency
                customer = Customer.objects.filter(
                    Q(integrations__stripe__id=stripe_id) | Q(email=stripe_email),
                    organization=organization,
                ).first()
                if customer:  # customer exists in system already
                    cur_pp_dict = customer.integrations.get(
                        PAYMENT_PROVIDERS.STRIPE, {}
                    )
                    cur_pp_dict["id"] = stripe_id
                    cur_pp_dict["email"] = stripe_email
                    cur_pp_dict["metadata"] = stripe_metadata
                    cur_pp_dict["name"] = stripe_name
                    cur_pp_dict["currency"] = stripe_currency
                    customer.integrations[PAYMENT_PROVIDERS.STRIPE] = cur_pp_dict
                    customer.save()
                else:
                    customer_kwargs = {
                        "organization": organization,
                        "name": stripe_name,
                        "email": stripe_email,
                        "integrations": {
                            PAYMENT_PROVIDERS.STRIPE: {
                                "id": stripe_id,
                                "email": stripe_email,
                                "metadata": stripe_metadata,
                                "name": stripe_name,
                                "currency": stripe_currency,
                            }
                        },
                    }
                    customer = Customer.objects.create(**customer_kwargs)
                    num_cust_added += 1
        except Exception as e:
            print(e)

        return num_cust_added

    def import_payment_objects(self, organization):
        imported_invoices = {}
        for customer in organization.org_customers.all():
            if PAYMENT_PROVIDERS.STRIPE in customer.integrations:
                invoices = self._import_payment_objects_for_customer(customer)
                imported_invoices[customer.customer_id] = invoices
        return imported_invoices

    def _import_payment_objects_for_customer(self, customer):
        from metering_billing.models import Invoice
        from metering_billing.serializers.internal_serializers import (
            InvoiceCustomerSerializer,
            InvoiceOrganizationSerializer,
        )

        stripe.api_key = self.secret_key
        invoices = stripe.PaymentIntent.list(
            customer=customer.integrations[PAYMENT_PROVIDERS.STRIPE]["id"]
        )
        lotus_invoices = []
        for stripe_invoice in invoices.auto_paging_iter():
            if Invoice.objects.filter(
                external_payment_obj_id=stripe_invoice.id
            ).exists():
                continue
            cost_due = Money(
                Decimal(stripe_invoice.amount) / 100, stripe_invoice.currency
            )
            invoice_kwargs = {
                "customer": InvoiceCustomerSerializer(customer).data,
                "cost_due": cost_due,
                "issue_date": datetime.datetime.fromtimestamp(
                    stripe_invoice.created, pytz.utc
                ),
                "org_connected_to_cust_payment_provider": True,
                "cust_connected_to_payment_provider": True,
                "external_payment_obj_id": stripe_invoice.id,
                "external_payment_obj_type": PAYMENT_PROVIDERS.STRIPE,
                "organization": InvoiceOrganizationSerializer(
                    customer.organization
                ).data,
                "subscription": {},
                "line_items": {},
            }
            lotus_invoice = Invoice.objects.create(**invoice_kwargs)
            lotus_invoices.append(lotus_invoice)
        return lotus_invoices

    def create_pp_customer(
        self, customer
    ) -> Union[INVOICE_STATUS.PAID, INVOICE_STATUS.UNPAID]:
        stripe.api_key = self.secret_key
        assert customer.integrations.get(PAYMENT_PROVIDERS.STRIPE, {}).get("id") is None
        customer_kwargs = {
            "name": customer.customer_name,
            "email": customer.email,
        }
        if not self.self_hosted:
            org_stripe_acct = customer.organization.payment_provider_ids.get(
                PAYMENT_PROVIDERS.STRIPE, ""
            )
            assert org_stripe_acct != ""
            customer_kwargs["stripe_account"] = org_stripe_acct
        stripe_customer = stripe.Customer.create(**customer_kwargs)
        customer.integrations[PAYMENT_PROVIDERS.STRIPE] = {
            "id": stripe_customer.id,
            "email": customer.email,
            "metadata": {},
            "name": customer.customer_name,
        }
        customer.save()

    def generate_payment_object(self, invoice) -> str:
        from metering_billing.models import Customer, Organization

        stripe.api_key = self.secret_key
        # check everything works as expected + build invoice item
        assert invoice.external_payment_obj_id is None
        organization = Organization.objects.get(
            company_name=invoice.organization["company_name"]
        )
        customer = Customer.objects.get(
            organization=organization, customer_id=invoice.customer["customer_id"]
        )
        stripe_customer_id = customer.integrations.get(
            PAYMENT_PROVIDERS.STRIPE, {}
        ).get("id")
        assert stripe_customer_id is not None
        invoice_kwargs = {
            "customer": stripe_customer_id,
            "currency": invoice.cost_due.currency,
            "payment_method_types": ["card"],
            "amount": decimal_to_cents(invoice.cost_due.amount),
            "metadata": invoice.line_items,
        }
        if not self.self_hosted:
            org_stripe_acct = customer.organization.payment_provider_ids.get(
                PAYMENT_PROVIDERS.STRIPE, ""
            )
            assert org_stripe_acct != ""
            invoice_kwargs["stripe_account"] = org_stripe_acct

        stripe_invoice = stripe.PaymentIntent.create(**invoice_kwargs)
        return stripe_invoice.id

    def get_post_data_serializer(self) -> serializers.Serializer:
        class StripePostRequestDataSerializer(serializers.Serializer):
            authorization_code = serializers.CharField()

        return StripePostRequestDataSerializer

    def handle_post(self, data, organization) -> PaymentProviderPostResponseSerializer:
        stripe.api_key = self.secret_key
        response = stripe.OAuth.token(
            grant_type="authorization_code",
            code=data["authorization_code"],
        )

        if response.json().get("error"):
            return Response(
                {
                    "payment_processor": PAYMENT_PROVIDERS.STRIPE,
                    "success": False,
                    "details": response.json().get("error_description"),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        org_pp_ids = organization.payment_provider_ids
        org_pp_ids[PAYMENT_PROVIDERS.STRIPE] = response.json()["stripe_user_id"]
        organization.payment_provider_ids = org_pp_ids
        organization.save()
        self.import_customers(organization)

        response = {
            "payment_processor": PAYMENT_PROVIDERS.STRIPE,
            "success": True,
            "details": "Successfully connected to Stripe",
        }
        serializer = PaymentProviderPostResponseSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        return Response(validated_data, status=status.HTTP_200_OK)

    def get_redirect_url(self) -> str:
        return self.redirect_url


PAYMENT_PROVIDER_MAP = {
    PAYMENT_PROVIDERS.STRIPE: StripeConnector(),
}
