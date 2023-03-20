import abc
import base64
import datetime
import logging
from decimal import Decimal
from typing import Literal, Optional, Tuple
from urllib.parse import urlencode

import braintree
import pytz
import requests
import sentry_sdk
import stripe
from django.conf import settings
from django.core.cache import cache
from django.db.models import F, Prefetch, Q
from metering_billing.serializers.payment_processor_serializers import (
    PaymentProcesorPostResponseSerializer,
)
from metering_billing.utils import (
    convert_to_two_decimal_places,
    now_utc,
    parse_nested_response,
)
from metering_billing.utils.enums import (
    ORGANIZATION_SETTING_GROUPS,
    ORGANIZATION_SETTING_NAMES,
    PAYMENT_PROCESSORS,
)
from rest_framework import serializers, status
from rest_framework.response import Response

logger = logging.getLogger("django.server")

SELF_HOSTED = settings.SELF_HOSTED

NANGO_SECRET = settings.NANGO_SECRET

STRIPE_LIVE_SECRET_KEY = settings.STRIPE_LIVE_SECRET_KEY
STRIPE_TEST_SECRET_KEY = settings.STRIPE_TEST_SECRET_KEY
STRIPE_TEST_CLIENT = settings.STRIPE_TEST_CLIENT
STRIPE_LIVE_CLIENT = settings.STRIPE_LIVE_CLIENT

BRAINTREE_LIVE_MERCHANT_ID = settings.BRAINTREE_LIVE_MERCHANT_ID
BRAINTREE_LIVE_PUBLIC_KEY = settings.BRAINTREE_LIVE_PUBLIC_KEY
BRAINTREE_LIVE_SECRET_KEY = settings.BRAINTREE_LIVE_SECRET_KEY
BRAINTREE_TEST_MERCHANT_ID = settings.BRAINTREE_TEST_MERCHANT_ID
BRAINTREE_TEST_PUBLIC_KEY = settings.BRAINTREE_TEST_PUBLIC_KEY
BRAINTREE_TEST_SECRET_KEY = settings.BRAINTREE_TEST_SECRET_KEY

VITE_API_URL = settings.VITE_API_URL


def base64_encode(data: str) -> str:
    string_bytes = data.encode("ascii")
    base64_bytes = base64.b64encode(string_bytes)
    base64_string = base64_bytes.decode("ascii")
    return base64_string


class PaymentProcesor(abc.ABC):
    # MANAGEMENT METHODS
    @abc.abstractmethod
    def __init__(self):
        """This method will be called from settings.py when checking to see if the payment processor is allowed. You should implement this to capture the necessary credentials from the environment variables and store them in the class instance."""
        pass

    @abc.abstractmethod
    def working(self) -> bool:
        """In order to prevent errors on object creation, this method will be called to decide whether this payment processor is connected to this instance of Lotus."""
        pass

    @abc.abstractmethod
    def customer_connected(self, customer) -> bool:
        """This method will be called in order to gate calls to create_payment_object."""
        pass

    @abc.abstractmethod
    def organization_connected(self, organization) -> bool:
        """This method will be called in order to gate calls to create_payment_object. If the organization is not connected, then won't generate a payment object for the organization."""
        pass

    @abc.abstractmethod
    def initialize_settings(self, organization) -> None:
        """This method will be called when a user clicks on the connect button for a payment processor. It should initialize the settings for the payment processor for the organization."""
        pass

    @abc.abstractmethod
    def get_connection_id(self, organization) -> str:
        """
        This method is used for Nango for determining which unique key to use for the connection. Usually a good strategy is to use the organization's organization_idid.
        """
        pass

    @abc.abstractmethod
    def get_account_id(self, organization) -> str:
        """This method is used to see the id of the connected account."""
        pass

    ## IMPORT METHODS
    @abc.abstractmethod
    def import_customers(self, organization) -> int:
        """This method will be called periodically to match customers from the payment processor with customers in Lotus. Keep in mind that Customers have a payment_provider field that can be used to determine which payment processor the customer should be connected to, and that the payment_provider_id field can be used to store the id of the customer in the associated payment processor. Return the number of customers that were imported."""
        pass

    @abc.abstractmethod
    def import_payment_objects(self, organization) -> dict[str, list[str]]:
        """Similar to the import_customers method, this method will be called periodically to match invoices from the payment processor with invoices in Lotus. Keep in mind that Invoices have a payment_provider field that can be used to determine which payment processor the invoice should be connected to, and that the payment_provider_id field can be used to store the id of the invoice in the associated payment processor. Return a dictionary mapping customer ids to lists of Lotus Invoice objects that were created from the imports."""
        pass

    @abc.abstractmethod
    def transfer_subscriptions(self, organization, end_now=False) -> int:
        """This method will be used when transferring data from a payment provider's billing solution into Lotus. This method works by taking currently active subscriptions from the payment provider, and checking two things. First, there has to be a customer in Lotus with a linked customer_id (or equivalent) the same as in the subscription. Second, there has to be a Plan with a linked product_id/price_id (or equivalent) the same as in the subscription. If both of these conditions are met, then a Subscription object will be created in Lotus. If the end_now parameter is True, then the subscription in the payment provider will be cancelled and the subscription in Lotus will be set to start immediately. Otherwise, the renew parameter in the payment_provider's subscription will be turned off, and a Subscription object will be created in Lotus with the same start as the end date as the subscription in the payment provider. Return the number of subscriptions that were transferred."""
        pass

    @abc.abstractmethod
    def update_payment_object_status(self, organization, payment_object_id: str):
        """This method will be called periodically when the status of a payment object needs to be updated. It should return the status of the payment object, which should be either paid or unpaid."""
        pass

    @abc.abstractmethod
    def retrieve_customer_by_external_id(self, organization, external_id: str):
        """This method will be called when a customer is created in Lotus and the payment provider is connected. It should return the customer object from the payment provider."""
        pass

    @abc.abstractmethod
    def has_payment_method(self, customer) -> bool:
        """This method will be caleld to check if the customer has a payment method attached to their account."""
        pass

    @abc.abstractmethod
    def connect_customer(self, customer, external_id) -> bool:
        """This method will be caleld to check if the customer has a payment method attached to their account."""
        pass

    @abc.abstractmethod
    def get_customer_address(self, customer, type: Literal["shipping", "billing"]):
        """This method will be called to get the address of a customer."""
        pass

    @abc.abstractmethod
    def get_organization_address(
        self,
        organization,
    ):
        """This method will be called to get the address of a customer."""
        pass

    # EXPORT METHODS
    @abc.abstractmethod
    def create_customer_flow(self, customer) -> None:
        """Depending on global settings and the way you want to use Lotus, this method will be called when a customer is created in Lotus in order to create the same customer in the payment provider. After creating it, it should insert the payment provider customer id into the customer object in Lotus."""
        pass

    @abc.abstractmethod
    def create_payment_object(self, invoice) -> Tuple[Optional[str], Optional[str]]:
        """This method will be called when an external payment object needs to be generated (this can vary greatly depending on the payment processor). It should return the id of this object and its status as a tuple of strings."""
        pass

    # FRONTEND REQUEST METHODS
    @abc.abstractmethod
    def handle_post(
        self, data, organization
    ) -> Optional[PaymentProcesorPostResponseSerializer]:
        """This method will be called when a POST request is made to the payment provider endpoint. It should return a response that will be sent back to the user. In the case of Stripe, it needs to do the Oauth flow itself, but in the case of Braitnree, Nango took care of the connection on the frontend so we can just use that information direclty to create the integration."""
        pass

    @abc.abstractmethod
    def get_post_data_serializer(self) -> serializers.Serializer:
        """This method will be called when a POST request is made to the payment provider endpoint. It should return a serializer that will be used to validate the data sent in the POST request."""
        pass

    @abc.abstractmethod
    def get_redirect_url(self, organization) -> str:
        """The link returned by this method will be called when a user clicks on the connect button for a payment processor. It should return a link that the user will be redirected to in order to connect their account to the payment processor.

        NOTE: After using Nango, this is pretty much only necessary for Stripe. No one else has a redirect url that needs to be handled manually.
        """
        pass


class BraintreeConnector(PaymentProcesor):
    # MANAGEMENT METHODS
    def __init__(self):
        self.self_hosted = SELF_HOSTED
        self.live_merchant_id = BRAINTREE_LIVE_MERCHANT_ID
        self.live_public_key = BRAINTREE_LIVE_PUBLIC_KEY
        self.live_private_key = BRAINTREE_LIVE_SECRET_KEY
        self.test_merchant_id = BRAINTREE_TEST_MERCHANT_ID
        self.test_public_key = BRAINTREE_TEST_PUBLIC_KEY
        self.test_private_key = BRAINTREE_TEST_SECRET_KEY
        self.config_key = "braintree-sandbox"
        self.scopes = "address:create, address:update, address:find, customer:create, customer:update, customer:find, customer:search, payment_method:find, transaction:sale, transaction:find, transaction:search, view_facilitated_transaction_metrics, read_facilitated_transactions, merchant_account:all,merchant_account:find, payment_method_nonce:find"

    def working(self) -> bool:
        if self.self_hosted:
            return (
                self.live_merchant_id is not None
                and self.live_public_key is not None
                and self.live_private_key is not None
            ) or (
                self.test_merchant_id is not None
                and self.test_public_key is not None
                and self.test_private_key is not None
            )
        else:
            return True

    def customer_connected(self, customer) -> bool:
        return customer.braintree_integration is not None

    def organization_connected(self, organization) -> bool:
        from metering_billing.models import Organization

        id_in = organization.braintree_integration is not None
        if self.self_hosted:
            if (
                organization.organization_type
                == Organization.OrganizationType.PRODUCTION
            ):
                return (
                    self.live_merchant_id is not None
                    and self.live_public_key is not None
                    and self.live_private_key is not None
                )
            else:
                return (
                    self.test_merchant_id is not None
                    and self.test_public_key is not None
                    and self.test_private_key is not None
                )
        else:
            return id_in

    def initialize_settings(self, organization, **kwargs):
        from metering_billing.models import OrganizationSetting

        generate_braintree_after_lotus_value = kwargs.get(
            "generate_braintree_after_lotus", False
        )
        setting, created = OrganizationSetting.objects.get_or_create(
            organization=organization,
            setting_name=ORGANIZATION_SETTING_NAMES.GENERATE_CUSTOMER_IN_BRAINTREE_AFTER_LOTUS,
            setting_group=PAYMENT_PROCESSORS.BRAINTREE,
        )
        if created:
            setting.setting_values = {"value": generate_braintree_after_lotus_value}
            setting.save()

    def get_connection_id(self, organization) -> str:
        return organization.organization_id.hex

    def get_account_id(self, organization) -> str:
        from metering_billing.models import (
            BraintreeOrganizationIntegration,
            Organization,
        )

        integration = organization.braintree_integration
        if integration is None:
            stored_id = None
        else:
            stored_id = organization.braintree_integration.braintree_merchant_id

        if self.self_hosted:
            if (
                organization.organization_type
                == Organization.OrganizationType.PRODUCTION
            ):
                if (
                    stored_id != self.live_merchant_id
                    and self.live_merchant_id is not None
                ):
                    if stored_id is None:
                        organization.braintree_integration = (
                            BraintreeOrganizationIntegration.objects.create(
                                organization=organization,
                                braintree_merchant_id=self.live_merchant_id,
                            )
                        )
                        organization.save()
                    else:
                        organization.braintree_integration.braintree_merchant_id = (
                            self.live_merchant_id
                        )
                        organization.braintree_integration.save()
                    self.initialize_settings(organization)
                return self.live_merchant_id
            else:
                if (
                    stored_id != self.test_merchant_id
                    and self.test_merchant_id is not None
                ):
                    if stored_id is None:
                        organization.braintree_integration = (
                            BraintreeOrganizationIntegration.objects.create(
                                organization=organization,
                                braintree_merchant_id=self.test_merchant_id,
                            )
                        )
                        organization.save()
                    else:
                        organization.braintree_integration.braintree_merchant_id = (
                            self.test_merchant_id
                        )
                        organization.braintree_integration.save()
                    self.initialize_settings(organization)
                return self.test_merchant_id
        else:
            return stored_id

    def _get_config_key(self, organization):
        from metering_billing.models import Organization

        if organization.organization_type == Organization.OrganizationType.PRODUCTION:
            return "braintree"
        else:
            return "braintree-sandbox"

    def _get_access_token(self, organization) -> str:
        connection_id = self.get_connection_id(organization)

        headers = {"Authorization": f"Bearer {NANGO_SECRET}"}

        url = f"https://api.nango.dev/connection/{connection_id}?provider_config_key={self._get_config_key(organization)}"

        resp = requests.get(url, headers=headers).json()
        access_token = resp["credentials"]["access_token"]
        return access_token

    def _get_merchant_id(self, organization) -> str:
        connection_id = self.get_connection_id(organization)

        headers = {"Authorization": f"Bearer {NANGO_SECRET}"}

        url = f"https://api.nango.dev/connection/{connection_id}?provider_config_key={self._get_config_key(organization)}"

        resp = requests.get(url, headers=headers).json()
        access_token = resp["metadata"]["merchantId"]
        return access_token

    def _get_gateway(self, organization) -> braintree.BraintreeGateway:
        from metering_billing.models import Organization

        if self.self_hosted:
            if (
                organization.organization_type
                == Organization.OrganizationType.PRODUCTION
            ):
                config = braintree.Configuration(
                    braintree.Environment.Production,
                    merchant_id=self.live_merchant_id,
                    public_key=self.live_public_key,
                    private_key=self.live_private_key,
                )
                gateway = braintree.BraintreeGateway(config)

            else:
                config = braintree.Configuration(
                    braintree.Environment.Sandbox,
                    merchant_id=self.test_merchant_id,
                    public_key=self.test_public_key,
                    private_key=self.test_private_key,
                )
                gateway = braintree.BraintreeGateway(config)
        else:
            gateway = braintree.BraintreeGateway(
                access_token=self._get_access_token(organization)
            )
        return gateway

    # IMPORT METHODS

    def import_customers(self, organization):
        """
        Imports customers from Braintree. If they already exist (by checking that either they already have their Stripe ID in our system, or seeing that they have the same email address), then we update the Braintree section of payment_providers dict to reflect new information. If they don't exist, we create them (not as a Lotus customer yet, just as a Braintree customer).
        """
        from metering_billing.models import BraintreeCustomerIntegration, Customer

        gateway = self._get_gateway(organization)

        num_cust_added = 0

        try:
            all_braintree_customers = gateway.customer.all()
            for braintree_customer in all_braintree_customers.items:
                braintree_id = braintree_customer.id
                braintree_email = braintree_customer.email
                braintree_first_name = braintree_customer.first_name
                braintree_last_name = braintree_customer.last_name
                customer = Customer.objects.filter(
                    Q(braintree_integration__braintree_customer_id=braintree_id)
                    | (Q(email=braintree_email) & Q(email__isnull=False)),
                    organization=organization,
                ).first()
                if customer:  # customer exists in system already
                    customer.payment_provider = PAYMENT_PROCESSORS.BRAINTREE
                    customer.save()
                else:
                    try:
                        integration = BraintreeCustomerIntegration.objects.create(
                            braintree_customer_id=braintree_id,
                            organization=organization,
                        )
                        customer_kwargs = {
                            "organization": organization,
                            "customer_name": f"{braintree_first_name} {braintree_last_name}",
                            "email": braintree_email,
                            "payment_provider": PAYMENT_PROCESSORS.BRAINTREE,
                            "braintree_integration": integration,
                        }
                        customer = Customer.objects.create(**customer_kwargs)
                        num_cust_added += 1
                    except Exception as e:
                        logger.error("Ran into exception:", e)
                        continue
        except Exception as e:
            logger.error("Ran into exception:", e)

        return num_cust_added

    def transfer_subscriptions(self, organization):
        """
        NOT READY YET
        """
        pass

    def import_payment_objects(self, organization):
        """
        NOT READY YET
        """
        pass

    # EXPORT METHODS
    def create_customer_flow(self, customer) -> None:
        from metering_billing.models import (
            BraintreeCustomerIntegration,
            OrganizationSetting,
        )

        gateway = self._get_gateway(customer.organization)

        setting, _ = OrganizationSetting.objects.get_or_create(
            setting_name=ORGANIZATION_SETTING_NAMES.GENERATE_CUSTOMER_IN_BRAINTREE_AFTER_LOTUS,
            organization=customer.organization,
            setting_group=ORGANIZATION_SETTING_GROUPS.BRAINTREE,
        )
        setting_value = setting.setting_values.get("value", False)
        if setting_value is True:
            assert (
                customer.braintree_integration is None
            ), "Customer already has a Braintree ID"
            customer_kwargs = {
                "first_name": customer.customer_name,
                "last_name": customer.customer_name,
                "company": customer.customer_name,
                "email": customer.email,
            }
            if not self.self_hosted:
                assert (
                    customer.organization.braintree_integration is not None
                ), "Organization does not have a Braintree account connected"
            result = gateway.customer.create(customer_kwargs)

            if result.is_success:
                braintree_integration = BraintreeCustomerIntegration.objects.create(
                    braintree_customer_id=result.customer.id,
                    organization=customer.organization,
                )
                customer.braintree_integration = braintree_integration
                customer.save()
        elif setting_value is False:
            pass
        else:
            raise Exception(
                "Invalid value for generate_customer_after_creating_in_lotus setting"
            )

    def create_payment_object(self, invoice) -> Tuple[Optional[str], Optional[str]]:
        gateway = self._get_gateway(invoice.organization)
        # check everything works as expected + build invoice item
        assert (
            invoice.external_payment_obj_id is None
        ), "Invoice already has an external ID"
        customer = invoice.customer
        braintree_customer_id = customer.braintree_integration.braintree_customer_id
        assert (
            braintree_customer_id is not None
        ), "Customer does not have a Braintree ID"
        invoice_kwargs = {
            "amount": convert_to_two_decimal_places(invoice.amount),
            "customer_id": braintree_customer_id,
            "line_items": [],
            "options": {"submit_for_settlement": True},
        }
        for line_item in invoice.line_items.all().order_by(
            F("associated_subscription_record").desc(nulls_last=True)
        ):
            name = line_item.name[:35]
            kind = "debit" if line_item.base > 0 else "credit"
            quantity = convert_to_two_decimal_places(line_item.quantity or 1)
            total_amount = convert_to_two_decimal_places(abs(line_item.base))
            unit_amount = convert_to_two_decimal_places(total_amount / quantity)

            invoice_kwargs["line_items"].append(
                {
                    "name": name,
                    "quantity": quantity,
                    "unit_amount": unit_amount,
                    "total_amount": total_amount,
                    "description": name,
                    "kind": kind,
                }
            )
        result = gateway.transaction.sale(invoice_kwargs)
        if result.is_success:
            invoice.external_payment_obj_id = result.transaction.id
            invoice.external_payment_obj_status = result.transaction.status
            invoice.save()
            return result.transaction.id, result.transaction.status
        else:
            logger.error("Ran into error:", result.message)
            return None, None

    def update_payment_object_status(self, organization, payment_object_id):
        from metering_billing.models import Invoice

        gateway = self._get_gateway(organization)
        invoice = gateway.transaction.find(payment_object_id)
        if invoice.status == braintree.Transaction.Status.Settled:
            return Invoice.PaymentStatus.PAID
        else:
            return Invoice.PaymentStatus.UNPAID

    def retrieve_customer_by_external_id(self, organization, external_id: str):
        gateway = self._get_gateway(organization)
        customer = gateway.customer.find(external_id)
        return customer

    def has_payment_method(self, customer) -> bool:
        braintree_customer_id = customer.braintree_integration.braintree_customer_id
        cust_dict = cache.get(f"braintree_customer_{braintree_customer_id}")
        if cust_dict is None:
            customer_obj = self.retrieve_customer_by_external_id(
                customer.organization, braintree_customer_id
            )
            cust_dict = parse_nested_response(customer_obj)
            cache.set(
                f"braintree_customer_{braintree_customer_id}",
                cust_dict,
                60 * 60 * 24,
            )
        return len(cust_dict.get("invoice_settings", {}).get("payment_methods", [])) > 0

    def connect_customer(self, customer, external_id) -> bool:
        from metering_billing.models import BraintreeCustomerIntegration

        gateway = self._get_gateway(customer.organization)
        try:
            gateway.customer.find(external_id)
            integration = BraintreeCustomerIntegration.objects.create(
                organization=customer.organization,
                braintree_customer_id=external_id,
            )
            customer.braintree_integration = integration
            customer.save()
        except Exception as e:
            logger.error(e)
            return False

    def get_customer_address(self, customer, type: Literal["shipping", "billing"]):
        from metering_billing.models import Address

        # ignore type for now
        cust_dict = cache.get(
            f"braintree_customer_{customer.braintree_integration.braintree_customer_id}"
        )
        if cust_dict is None:
            customer_obj = self.retrieve_customer_by_external_id(
                customer.organization, customer.stripe_integration.stripe_customer_id
            )
            cust_dict = parse_nested_response(customer_obj)
            cache.set(
                f"braintree_customer_{customer.braintree_integration.braintree_customer_id}",
                cust_dict,
                60 * 60 * 24,
            )
        address = next(iter(cust_dict.get("addresses", [])), {})
        addy = Address(
            city=address.get("locality"),
            country=address.get("country_code_alpha2"),
            line1=address.get("street_address"),
            line2=address.get("extended_address"),
            postal_code=address.get("postal_code"),
            state=address.get("region"),
        )
        return addy

    def get_organization_address(
        self,
        organization,
    ):
        from metering_billing.models import Address

        braintree_id = organization.braintree_integration.braintree_merchant_id
        acct_dict = cache.get(f"braintree_account_{braintree_id}")
        if acct_dict is None:
            acct_obj = self.retrieve_account(organization)
            acct_dict = parse_nested_response(acct_obj)
            cache.set(
                f"braintree_account_{braintree_id}",
                acct_dict,
                60 * 60 * 24,
            )
        address = acct_dict.get("business_details", {}).get("address_details", {})
        addy = Address(
            city=address.get("locality"),
            country=address.get("country_code_alpha2"),
            line1=address.get("street_address"),
            line2=address.get("extended_address"),
            postal_code=address.get("postal_code"),
            state=address.get("region"),
        )
        return addy

    def retrieve_account(self, organization):
        gateway = self._get_gateway(organization)
        result = gateway.merchant_account.all()
        return result[0] if result else None

    # FRONTEND REQUEST METHODS
    def get_post_data_serializer(self) -> serializers.Serializer:
        class BraintreePostRequestDataSerializer(serializers.Serializer):
            nango_connected = serializers.BooleanField()

        return BraintreePostRequestDataSerializer

    def handle_post(self, data, organization) -> None:
        from metering_billing.models import BraintreeOrganizationIntegration

        nango_connected = data.get("nango_connected", False)
        if not nango_connected:
            return Response(
                {
                    "payment_processor": PAYMENT_PROCESSORS.BRAINTREE,
                    "success": False,
                    "details": "Failed to connect to Braintree",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            stored_id = data.get("merchant_id") or self._get_merchant_id(organization)
        except Exception as e:
            logger.error(e)
            return Response(
                {
                    "payment_processor": PAYMENT_PROCESSORS.BRAINTREE,
                    "success": False,
                    "details": "Failed to connect to Braintree",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        integration = BraintreeOrganizationIntegration.objects.create(
            organization=organization,
            braintree_merchant_id=stored_id,
        )
        organization.braintree_integration = integration
        organization.save()
        self.initialize_settings(organization)

        response = {
            "payment_processor": PAYMENT_PROCESSORS.BRAINTREE,
            "success": True,
            "details": "Successfully connected to Braintree",
        }
        serializer = PaymentProcesorPostResponseSerializer(data=response)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        return Response(validated_data, status=status.HTTP_200_OK)

    def get_redirect_url(self, organization) -> str:
        return ""


class StripeConnector(PaymentProcesor):
    def __init__(self):
        self.stripe_account_id = None
        self.live_secret_key = STRIPE_LIVE_SECRET_KEY
        self.test_secret_key = STRIPE_TEST_SECRET_KEY
        self.self_hosted = SELF_HOSTED
        redirect_dict = {
            "response_type": "code",
            "scope": "read_write",
            "redirect_uri": VITE_API_URL + "redirectstripe",
        }
        live_qstr = urlencode(
            {
                **redirect_dict,
                "client_id": STRIPE_LIVE_CLIENT,
            }
        )
        test_qstr = urlencode(
            {
                **redirect_dict,
                "client_id": STRIPE_TEST_CLIENT,
            }
        )
        if not self.self_hosted:
            self.live_redirect_url = (
                "https://connect.stripe.com/oauth/authorize?" + live_qstr
            )
            self.test_redirect_url = (
                "https://connect.stripe.com/oauth/authorize?" + test_qstr
            )
        else:
            self.live_redirect_url = None
            self.test_redirect_url = None
            stripe.api_key = self.live_secret_key or self.test_secret_key
            try:
                res = stripe.Account.retrieve()
                self.stripe_account_id = res.id
            except Exception as e:
                logger.error(e)

    def working(self) -> bool:
        return self.live_secret_key is not None or self.test_secret_key is not None

    def customer_connected(self, customer) -> bool:
        return customer.stripe_integration is not None

    def organization_connected(self, organization) -> bool:
        from metering_billing.models import Organization

        id_in = organization.stripe_integration is not None
        if self.self_hosted:
            if (
                organization.organization_type
                == Organization.OrganizationType.PRODUCTION
            ):
                return (
                    self.live_secret_key is not None
                    and self.stripe_account_id is not None
                )
            else:
                return (
                    self.test_secret_key is not None
                    and self.stripe_account_id is not None
                )
        else:
            return id_in

    def get_connection_id(self, organization) -> str:
        # Since stripe doesn't use Nango, this doesn't truly matter, but we pass back anyway
        return organization.organization_id.hex

    def get_account_id(self, organization):
        from metering_billing.models import StripeOrganizationIntegration

        integration = organization.stripe_integration
        if integration is not None:
            stored_id = organization.stripe_integration.stripe_account_id
        else:
            stored_id = None

        if self.self_hosted:
            if (
                stored_id != self.stripe_account_id
                and self.stripe_account_id is not None
            ):
                if stored_id is None:
                    organization.stripe_integration = (
                        StripeOrganizationIntegration.objects.create(
                            organization=organization,
                            stripe_account_id=self.stripe_account_id,
                        )
                    )
                    organization.save()
                else:
                    organization.stripe_integration.stripe_account_id = (
                        self.stripe_account_id
                    )
                    organization.stripe_integration.save()
                self.initialize_settings(organization)
            return self.stripe_account_id
        else:
            return stored_id

    def update_payment_object_status(self, organization, payment_object_id):
        from metering_billing.models import Invoice, Organization

        invoice_payload = {}
        if not self.self_hosted:
            invoice_payload[
                "stripe_account"
            ] = organization.stripe_integration.stripe_account_id
        if organization.organization_type == Organization.OrganizationType.PRODUCTION:
            stripe.api_key = self.live_secret_key
        else:
            stripe.api_key = self.test_secret_key
        invoice = stripe.Invoice.retrieve(payment_object_id, **invoice_payload)
        if invoice.status == "paid":
            return Invoice.PaymentStatus.PAID
        else:
            return Invoice.PaymentStatus.UNPAID

    def retrieve_customer_by_external_id(self, organization, external_id: str):
        from metering_billing.models import Organization

        customer_payload = {}
        if not self.self_hosted:
            customer_payload[
                "stripe_account"
            ] = organization.stripe_integration.stripe_account_id
        if organization.organization_type == Organization.OrganizationType.PRODUCTION:
            stripe.api_key = self.live_secret_key
        else:
            stripe.api_key = self.test_secret_key
        customer = stripe.Customer.retrieve(external_id, **customer_payload)

        return customer

    def has_payment_method(self, customer) -> bool:
        stripe_id = customer.stripe_integration.stripe_customer_id
        cust_dict = cache.get(f"stripe_customer_{stripe_id}")
        if cust_dict is None:
            customer_obj = self.retrieve_customer_by_external_id(
                customer.organization, stripe_id
            )
            cust_dict = parse_nested_response(customer_obj)
            cache.set(
                f"stripe_customer_{stripe_id}",
                cust_dict,
                60 * 60 * 24,
            )
        return (
            cust_dict.get("invoice_settings", {}).get("default_payment_method")
            is not None
        )

    def connect_customer(self, customer, external_id) -> bool:
        from metering_billing.models import Organization, StripeCustomerIntegration

        organization = customer.organization
        if organization.organization_type == Organization.OrganizationType.PRODUCTION:
            stripe.api_key = self.live_secret_key
        else:
            stripe.api_key = self.test_secret_key
        customer_payload = {}
        if not self.self_hosted:
            customer_payload[
                "stripe_account"
            ] = organization.stripe_integration.stripe_account_id

        try:
            cust = stripe.Customer.retrieve(external_id, **customer_payload)
            if getattr(cust, "deleted", False):
                raise Exception("Customer deleted")
            integration = StripeCustomerIntegration.objects.create(
                organization=customer.organization,
                stripe_customer_id=external_id,
            )
            customer.stripe_integration = integration
            customer.save()
        except Exception as e:
            logger.error(e)
            return False

    def get_customer_address(self, customer, type: Literal["shipping", "billing"]):
        from metering_billing.models import Address

        stripe_id = customer.stripe_integration.stripe_customer_id
        key = "address" if type == "billing" else "shipping"
        cust_dict = cache.get(f"stripe_customer_{stripe_id}")
        if cust_dict is None:
            customer_obj = self.retrieve_customer_by_external_id(
                customer.organization, stripe_id
            )
            cust_dict = parse_nested_response(customer_obj)
            cache.set(
                f"stripe_customer_{stripe_id}",
                cust_dict,
                60 * 60 * 24,
            )
        address = cust_dict.get(key, {}) or {}
        addy = Address(
            city=address.get("city"),
            country=address.get("country"),
            line1=address.get("line1"),
            line2=address.get("line2"),
            postal_code=address.get("postal_code"),
            state=address.get("state"),
        )
        return addy

    def get_organization_address(
        self,
        organization,
    ):
        from metering_billing.models import Address

        stripe_id = organization.stripe_integration.stripe_account_id
        acct_dict = cache.get(f"stripe_account_{stripe_id}")
        if acct_dict is None:
            customer_obj = self.retrieve_account(organization)
            acct_dict = parse_nested_response(customer_obj)
            cache.set(
                f"stripe_account_{stripe_id}",
                acct_dict,
                60 * 60 * 24,
            )
        address = acct_dict.get("company", {}).get("address")
        addy = Address(
            city=address.get("city"),
            country=address.get("country"),
            line1=address.get("line1"),
            line2=address.get("line2"),
            postal_code=address.get("postal_code"),
            state=address.get("state"),
        )
        return addy

    def retrieve_account(self, organization):
        from metering_billing.models import Organization

        account_payload = {}
        if not self.self_hosted:
            account_payload[
                "stripe_account"
            ] = organization.stripe_integration.stripe_account_id
        if organization.organization_type == Organization.OrganizationType.PRODUCTION:
            stripe.api_key = self.live_secret_key
        else:
            stripe.api_key = self.test_secret_key
        customer = stripe.Account.retrieve(**account_payload)

        return customer

    def import_customers(self, organization):
        """
        Imports customers from Stripe. If they already exist (by checking that either they already have their Stripe ID in our system, or seeing that they have the same email address), then we update the Stripe section of payment_providers dict to reflect new information. If they don't exist, we create them (not as a Lotus customer yet, just as a Stripe customer).
        """
        from metering_billing.models import (
            Customer,
            Organization,
            StripeCustomerIntegration,
        )

        if organization.organization_type == Organization.OrganizationType.PRODUCTION:
            stripe.api_key = self.live_secret_key
        else:
            stripe.api_key = self.test_secret_key

        num_cust_added = 0

        stripe_cust_kwargs = {}
        if not self.self_hosted:
            # this is to get "on behalf" of someone
            stripe_cust_kwargs[
                "stripe_account"
            ] = organization.stripe_integration.stripe_account_id
        try:
            stripe_customers_response = stripe.Customer.list(**stripe_cust_kwargs)
            for stripe_customer in stripe_customers_response.auto_paging_iter():
                stripe_id = stripe_customer.id
                stripe_email = stripe_customer.email
                stripe_name = stripe_customer.name
                stripe_name = stripe_name if stripe_name else "no_stripe_name"
                customer = Customer.objects.filter(
                    Q(stripe_integration__stripe_customer_id=stripe_id)
                    | (Q(email=stripe_email) & Q(email__isnull=False)),
                    organization=organization,
                ).first()
                if customer:  # customer exists in system already
                    customer.payment_provider = PAYMENT_PROCESSORS.STRIPE
                    customer.save()
                else:
                    stripe_integration = StripeCustomerIntegration.objects.create(
                        organization=organization,
                        stripe_customer_id=stripe_id,
                    )
                    customer_kwargs = {
                        "organization": organization,
                        "customer_name": stripe_name,
                        "email": stripe_email,
                        "payment_provider": PAYMENT_PROCESSORS.STRIPE,
                        "stripe_integration": stripe_integration,
                    }
                    customer = Customer.objects.create(**customer_kwargs)
                    num_cust_added += 1
        except Exception as e:
            logger.error("Ran into exception:", e)

        return num_cust_added

    def import_payment_objects(self, organization):
        from metering_billing.models import Organization

        if organization.organization_type == Organization.OrganizationType.PRODUCTION:
            stripe.api_key = self.live_secret_key
        else:
            stripe.api_key = self.test_secret_key
        imported_invoices = {}
        for customer in organization.customers.all():
            if customer.stripe_integration:
                invoices = self._import_payment_objects_for_customer(customer)
                imported_invoices[customer.customer_id] = invoices
        return imported_invoices

    def _import_payment_objects_for_customer(self, customer):
        from metering_billing.models import Invoice

        payload = {}
        if not self.self_hosted:
            payload[
                "stripe_account"
            ] = customer.organization.stripe_integration.stripe_account_id
        invoices = stripe.Invoice.list(
            customer=customer.stripe_integration.stripe_customer_id, **payload
        )
        lotus_invoices = []
        for stripe_invoice in invoices.auto_paging_iter():
            if Invoice.objects.filter(
                organization=customer.organization,
                external_payment_obj_id=stripe_invoice.id,
            ).exists():
                continue
            amount = Decimal(stripe_invoice.amount_due) / 100
            invoice_kwargs = {
                "customer": customer,
                "amount": amount,
                "issue_date": datetime.datetime.fromtimestamp(
                    stripe_invoice.created, pytz.utc
                ),
                "org_connected_to_cust_payment_provider": True,
                "cust_connected_to_payment_provider": True,
                "external_payment_obj_id": stripe_invoice.id,
                "external_payment_obj_type": PAYMENT_PROCESSORS.STRIPE,
                "external_payment_obj_status": stripe_invoice.status,
                "organization": customer.organization,
            }
            lotus_invoice = Invoice.objects.create(**invoice_kwargs)
            lotus_invoices.append(lotus_invoice)
        return lotus_invoices

    def create_customer_flow(self, customer) -> None:
        from metering_billing.models import (
            Organization,
            OrganizationSetting,
            StripeCustomerIntegration,
        )

        organization = customer.organization
        if organization.organization_type == Organization.OrganizationType.PRODUCTION:
            stripe.api_key = self.live_secret_key
        else:
            stripe.api_key = self.test_secret_key

        setting, _ = OrganizationSetting.objects.get_or_create(
            setting_name=ORGANIZATION_SETTING_NAMES.GENERATE_CUSTOMER_IN_STRIPE_AFTER_LOTUS,
            organization=organization,
            setting_group=ORGANIZATION_SETTING_GROUPS.STRIPE,
        )
        setting_value = setting.setting_values.get("value", False)
        if setting_value is True and customer.stripe_integration is None:
            customer_kwargs = {
                "name": customer.customer_name,
                "email": customer.email,
            }
            if not self.self_hosted:
                org_stripe_acct = organization.stripe_integration.stripe_account_id
                customer_kwargs["stripe_account"] = org_stripe_acct
            try:
                stripe_customer = stripe.Customer.create(**customer_kwargs)
                integration = StripeCustomerIntegration.objects.create(
                    organization=organization,
                    stripe_customer_id=stripe_customer.id,
                )
                customer.stripe_integration = integration
                customer.save()
            except Exception as e:
                logger.error("Ran into exception:", e)
                pass
        elif setting_value is False:
            pass
        else:
            raise Exception(
                "Invalid value for generate_customer_after_creating_in_lotus setting"
            )

    def create_payment_object(self, invoice) -> Tuple[Optional[str], Optional[str]]:
        from metering_billing.models import Organization

        organization = invoice.organization
        customer = invoice.customer

        if organization.organization_type == Organization.OrganizationType.PRODUCTION:
            stripe.api_key = self.live_secret_key
        else:
            stripe.api_key = self.test_secret_key
        # check everything works as expected + build invoice item
        assert invoice.external_payment_obj_id is None
        stripe_customer_id = customer.stripe_integration.stripe_customer_id
        assert stripe_customer_id is not None, "Customer does not have a Stripe ID"
        invoice_kwargs = {
            "auto_advance": True,
            "customer": stripe_customer_id,
            "description": "Invoice from {}".format(
                customer.organization.organization_name
            ),
            "currency": invoice.currency.code.lower(),
        }
        if not self.self_hosted:
            org_stripe_acct = organization.stripe_integration.stripe_account_id
            assert (
                org_stripe_acct is not None
            ), "Organization does not have a Stripe account ID"
            invoice_kwargs["stripe_account"] = org_stripe_acct

        stripe_invoice = stripe.Invoice.create(**invoice_kwargs)
        for line_item in invoice.line_items.all().order_by(
            F("associated_subscription_record").desc(nulls_last=True)
        ):
            name = line_item.name
            amount = line_item.base
            customer = stripe_customer_id
            period = {
                "start": int(line_item.start_date.timestamp()),
                "end": int(line_item.end_date.timestamp()),
            }
            tax_behavior = "inclusive"
            sr = line_item.associated_subscription_record
            metadata = {}
            if sr is not None:
                metadata["plan_name"] = sr.billing_plan.plan.plan_name
                filters = sr.subscription_filters
                for f in filters:
                    metadata[f[0]] = f[1]
                    name += f" - ({f[0]} : {f[1]})"
            inv_dict = {
                "description": name,
                "amount": int(amount * 100),
                "customer": customer,
                "period": period,
                "currency": invoice.currency.code.lower(),
                "tax_behavior": tax_behavior,
                "metadata": metadata,
                "invoice": stripe_invoice.id,
            }
            if not self.self_hosted:
                inv_dict["stripe_account"] = org_stripe_acct
            stripe.InvoiceItem.create(**inv_dict)

        return stripe_invoice.id, stripe_invoice.status

    def get_post_data_serializer(self) -> serializers.Serializer:
        class StripePostRequestDataSerializer(serializers.Serializer):
            authorization_code = serializers.CharField()

        return StripePostRequestDataSerializer

    def handle_post(self, data, organization) -> PaymentProcesorPostResponseSerializer:
        from metering_billing.models import Organization, StripeOrganizationIntegration

        if organization.organization_type == Organization.OrganizationType.PRODUCTION:
            stripe.api_key = self.live_secret_key
        else:
            stripe.api_key = self.test_secret_key
        response = stripe.OAuth.token(
            grant_type="authorization_code",
            code=data["authorization_code"],
        )

        if response.get("error"):
            return Response(
                {
                    "payment_processor": PAYMENT_PROCESSORS.STRIPE,
                    "success": False,
                    "details": response.get("error_description"),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        integration = StripeOrganizationIntegration.objects.create(
            organization=organization,
            stripe_account_id=response["stripe_user_id"],
        )
        organization.stripe_integration = integration
        organization.save()
        self.initialize_settings(organization)

        response = {
            "payment_processor": PAYMENT_PROCESSORS.STRIPE,
            "success": True,
            "details": "Successfully connected to Stripe",
        }
        serializer = PaymentProcesorPostResponseSerializer(data=response)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        return Response(validated_data, status=status.HTTP_200_OK)

    def get_redirect_url(self, organization) -> str:
        from metering_billing.models import Organization

        if organization.organization_type == Organization.OrganizationType.PRODUCTION:
            return self.live_redirect_url or ""
        else:
            return self.test_redirect_url or ""

    def transfer_subscriptions(
        self, organization, end_now=False
    ) -> list[stripe.Subscription]:
        from metering_billing.models import (
            Customer,
            ExternalPlanLink,
            Organization,
            Plan,
            SubscriptionRecord,
        )

        if organization.organization_type == Organization.OrganizationType.PRODUCTION:
            stripe.api_key = self.live_secret_key
        else:
            stripe.api_key = self.test_secret_key

        stripe_cust_kwargs = {}
        if not self.self_hosted:
            stripe_cust_kwargs[
                "stripe_account"
            ] = organization.stripe_integration.stripe_account_id

        stripe_subscriptions = stripe.Subscription.search(
            query="status:'active'", **stripe_cust_kwargs
        )
        plans_with_links = (
            Plan.objects.filter(organization=organization)
            .prefetch_related(
                Prefetch(
                    "external_links",
                    queryset=ExternalPlanLink.objects.filter(
                        organization=organization, source=PAYMENT_PROCESSORS.STRIPE
                    ),
                )
            )
            .values("id", external_id=F("external_links__external_plan_id"))
        )
        plan_dict = {}
        for plan_obj in plans_with_links:
            if plan_obj["id"] not in plan_dict:
                plan_dict[plan_obj["id"]] = set()
            plan_dict[plan_obj["id"]].add(plan_obj["external_id"])

        lotus_plans = [
            (plan_id, external_plan_ids)
            for plan_id, external_plan_ids in plan_dict.items()
        ]
        ret_subs = []
        for i, subscription in enumerate(stripe_subscriptions.auto_paging_iter()):
            if (
                subscription.cancel_at_period_end
            ):  # don't transfer subscriptions that are ending
                continue
            try:  # if no customer matches, don't transfer
                customer = Customer.objects.get(
                    organization=organization,
                    stripe_integration__stripe_customer_id=subscription.customer,
                )
            except Customer.DoesNotExist:
                continue
            sub_items = subscription["items"]
            item_ids = {x["price"]["id"] for x in sub_items["data"]} | {
                x["price"]["product"] for x in sub_items["data"]
            }
            matching_plans = list(filter(lambda x: x[1] & item_ids, lotus_plans))
            # if no plans match any of the items, don't transfer
            if len(matching_plans) == 0:
                continue
            # great, in this case we transfer the subscription
            elif len(matching_plans) == 1:
                billing_plan = Plan.objects.get(
                    id=matching_plans[0][0]
                ).versions.first()
                # check to see if subscription exists
                validated_data = {
                    "organization": organization,
                    "customer": customer,
                    "billing_plan": billing_plan,
                    "auto_renew": True,
                    "is_new": False,
                }
                if end_now:
                    validated_data["start_date"] = now_utc()
                    sub = stripe.Subscription.delete(
                        subscription.id,
                        prorate=True,
                        invoice_now=True,
                        **stripe_cust_kwargs,
                    )
                else:
                    validated_data["start_date"] = datetime.datetime.utcfromtimestamp(
                        subscription.current_period_end
                    ).replace(tzinfo=pytz.utc)
                    sub = stripe.Subscription.modify(
                        subscription.id,
                        cancel_at_period_end=True,
                        **stripe_cust_kwargs,
                    )
                ret_subs.append(sub)
                SubscriptionRecord.create_subscription_record(
                    start_date=validated_data["start_date"],
                    end_date=validated_data.get("start_date"),
                    billing_plan=billing_plan,
                    customer=customer,
                    organization=organization,
                    subscription_filters=[],
                    is_new=False,
                    quantity=1,
                )
            else:  # error if multiple plans match
                err_msg = "Multiple Lotus plans match Stripe subscription {}.".format(
                    subscription
                )
                for plan_id, linked_ids in matching_plans:
                    err_msg += "Plan {} matches items {}".format(
                        plan_id, item_ids.intersection(linked_ids)
                    )
                raise ValueError(err_msg)
        return ret_subs

    def initialize_settings(self, organization, **kwargs):
        from metering_billing.models import OrganizationSetting

        generate_stripe_after_lotus_value = kwargs.get(
            "generate_stripe_after_lotus", False
        )
        setting, created = OrganizationSetting.objects.get_or_create(
            organization=organization,
            setting_name=ORGANIZATION_SETTING_NAMES.GENERATE_CUSTOMER_IN_STRIPE_AFTER_LOTUS,
            setting_group=PAYMENT_PROCESSORS.STRIPE,
        )
        if created:
            setting.setting_values = {"value": generate_stripe_after_lotus_value}
            setting.save()


PAYMENT_PROCESSOR_MAP = {}
try:
    PAYMENT_PROCESSOR_MAP[PAYMENT_PROCESSORS.STRIPE] = StripeConnector()
except Exception as e:
    print("ERROR: ", e)
    logger.error(e)
    sentry_sdk.capture_exception(e)
    pass
try:
    PAYMENT_PROCESSOR_MAP[PAYMENT_PROCESSORS.BRAINTREE] = BraintreeConnector()
except Exception as e:
    print("ERROR: ", e)
    logger.error(e)
    sentry_sdk.capture_exception(e)
    pass
