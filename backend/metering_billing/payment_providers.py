import abc
import datetime
import logging
from decimal import Decimal
from urllib.parse import urlencode

import pytz
import stripe
from django.conf import settings
from django.db.models import F, Prefetch, Q
from metering_billing.exceptions.exceptions import ExternalConnectionInvalid
from metering_billing.serializers.payment_provider_serializers import (
    PaymentProviderPostResponseSerializer,
)
from metering_billing.utils import now_utc
from metering_billing.utils.enums import (
    ORGANIZATION_SETTING_GROUPS,
    ORGANIZATION_SETTING_NAMES,
    PAYMENT_PROVIDERS,
    PLAN_STATUS,
)
from rest_framework import serializers, status
from rest_framework.response import Response

logger = logging.getLogger("django.server")

SELF_HOSTED = settings.SELF_HOSTED
STRIPE_LIVE_SECRET_KEY = settings.STRIPE_LIVE_SECRET_KEY
STRIPE_TEST_SECRET_KEY = settings.STRIPE_TEST_SECRET_KEY
STRIPE_TEST_CLIENT = settings.STRIPE_TEST_CLIENT
STRIPE_LIVE_CLIENT = settings.STRIPE_LIVE_CLIENT
VITE_API_URL = settings.VITE_API_URL


class PaymentProvider(abc.ABC):
    @abc.abstractmethod
    def __init__(self):
        """This method will be called from settings.py when checking to see if the payment processor is allowed. You should implement this to capture the necessary credentials from the environment variables and store them in the class instance."""
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
    def working(self) -> bool:
        """In order to prevent errors on object creation, this method will be called to decide whether this payment processor is connected to this instance of Lotus."""
        pass

    @abc.abstractmethod
    def update_payment_object_status(self, organization, payment_object_id: str):
        """This method will be called periodically when the status of a payment object needs to be updated. It should return the status of the payment object, which should be either paid or unpaid."""
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

    # EXPORT METHODS
    @abc.abstractmethod
    def create_customer(self, customer) -> str:
        """Depending on global settings and the way you want to use Lotus, this method will be called when a customer is created in Lotus in order to create the same customer in the payment provider. It should return the id of the customer in the payment processor."""
        pass

    @abc.abstractmethod
    def create_payment_object(self, invoice) -> str:
        """This method will be called when an external payment object needs to be generated (this can vary greatly depending on the payment processor). It should return the id of this object as a string so that the status of the payment can later be updated."""
        pass

    # FRONTEND REQUEST METHODS
    @abc.abstractmethod
    def get_post_data_serializer(self) -> serializers.Serializer:
        """This method will be called when a POST request is made to the payment provider endpoint. It should return a serializer that can be used to validate the data that is sent in the POST request. The data sent in the request will naturally be dependent on the payment processor, so we use this method to dynamically use the serializer."""
        pass

    @abc.abstractmethod
    def handle_post(self, data, organization) -> PaymentProviderPostResponseSerializer:
        """This method will be called when a POST request is made to the payment provider endpoint. It should return a response that will be sent back to the user."""
        pass

    @abc.abstractmethod
    def get_redirect_url(self, organization) -> str:
        """The link returned by this method will be called when a user clicks on the connect button for a payment processor. It should return a link that the user will be redirected to in order to connect their account to the payment processor."""
        pass

    @abc.abstractmethod
    def initialize_settings(self, organization) -> None:
        """This method will be called when a user clicks on the connect button for a payment processor. It should initialize the settings for the payment processor for the organization."""
        pass


class StripeConnector(PaymentProvider):
    def __init__(self):
        self.live_secret_key = STRIPE_LIVE_SECRET_KEY
        self.test_secret_key = STRIPE_TEST_SECRET_KEY
        self.self_hosted = SELF_HOSTED
        live_redirect_dict = {
            "response_type": "code",
            "scope": "read_write",
            "client_id": STRIPE_LIVE_CLIENT,
            "redirect_uri": VITE_API_URL + "redirectstripe",
        }
        live_qstr = urlencode(live_redirect_dict)
        test_redirect_dict = {
            "response_type": "code",
            "scope": "read_write",
            "client_id": STRIPE_TEST_CLIENT,
            "redirect_uri": VITE_API_URL + "redirectstripe",
        }
        test_qstr = urlencode(test_redirect_dict)
        self.live_redirect_url = (
            "https://connect.stripe.com/oauth/authorize?" + live_qstr
        )
        self.test_redirect_url = (
            "https://connect.stripe.com/oauth/authorize?" + test_qstr
        )

    def working(self) -> bool:
        return self.live_secret_key is not None or self.test_secret_key is not None

    def customer_connected(self, customer) -> bool:
        pp_ids = customer.integrations
        stripe_dict = pp_ids.get(PAYMENT_PROVIDERS.STRIPE, {})
        stripe_id = stripe_dict.get("id", None)
        return stripe_id is not None

    def organization_connected(self, organization) -> bool:
        if self.self_hosted:
            return self.live_secret_key is not None or self.test_secret_key is not None
        else:
            return (
                organization.payment_provider_ids.get(PAYMENT_PROVIDERS.STRIPE, None)
                is not None
            )

    def update_payment_object_status(self, organization, payment_object_id):
        from metering_billing.models import Invoice, Organization

        invoice_payload = {}
        if not self.self_hosted:
            invoice_payload["stripe_account"] = organization.payment_provider_ids.get(
                PAYMENT_PROVIDERS.STRIPE
            )
        if organization.organization_type == Organization.OrganizationType.PRODUCTION:
            stripe.api_key = self.live_secret_key
        else:
            stripe.api_key = self.test_secret_key
        invoice = stripe.Invoice.retrieve(payment_object_id, **invoice_payload)
        if invoice.status == "paid":
            return Invoice.PaymentStatus.PAID
        else:
            return Invoice.PaymentStatus.UNPAID

    def import_customers(self, organization):
        """
        Imports customers from Stripe. If they already exist (by checking that either they already have their Stripe ID in our system, or seeing that they have the same email address), then we update the Stripe section of payment_providers dict to reflect new information. If they don't exist, we create them (not as a Lotus customer yet, just as a Stripe customer).
        """
        from metering_billing.models import Customer, Organization

        if organization.organization_type == Organization.OrganizationType.PRODUCTION:
            stripe.api_key = self.live_secret_key
        else:
            stripe.api_key = self.test_secret_key

        num_cust_added = 0
        org_ppis = organization.payment_provider_ids

        stripe_cust_kwargs = {}
        if not self.self_hosted:
            # this is to get "on behalf" of someone
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
                stripe_payment_methods = []
                payment_methods = stripe.Customer.list_payment_methods(stripe_id)
                for payment_method in payment_methods.auto_paging_iter():
                    pm_dict = {
                        "id": payment_method.id,
                        "type": payment_method.type,
                        "details": {},
                    }
                    if payment_method.type == "card":
                        pm_dict["details"]["brand"] = payment_method.card.brand
                        pm_dict["details"]["exp_month"] = payment_method.card.exp_month
                        pm_dict["details"]["exp_year"] = payment_method.card.exp_year
                        pm_dict["details"]["last4"] = payment_method.card.last4
                    stripe_payment_methods.append(pm_dict)
                customer = Customer.objects.filter(
                    Q(integrations__stripe__id=stripe_id)
                    | (Q(email=stripe_email) & Q(email__isnull=False)),
                    organization=organization,
                ).first()
                if customer:  # customer exists in system already
                    integrations_dict = customer.integrations
                    cur_pp_dict = integrations_dict.get(PAYMENT_PROVIDERS.STRIPE, {})
                    cur_pp_dict["id"] = stripe_id
                    cur_pp_dict["email"] = stripe_email
                    cur_pp_dict["metadata"] = stripe_metadata
                    cur_pp_dict["name"] = stripe_name
                    cur_pp_dict["currency"] = stripe_currency
                    cur_pp_dict["payment_methods"] = stripe_payment_methods
                    integrations_dict[PAYMENT_PROVIDERS.STRIPE] = cur_pp_dict
                    customer.integrations = integrations_dict
                    customer.payment_provider = PAYMENT_PROVIDERS.STRIPE
                    customer.save()
                else:
                    customer_kwargs = {
                        "organization": organization,
                        "customer_name": stripe_name,
                        "email": stripe_email,
                        "integrations": {
                            PAYMENT_PROVIDERS.STRIPE: {
                                "id": stripe_id,
                                "email": stripe_email,
                                "metadata": stripe_metadata,
                                "name": stripe_name,
                                "currency": stripe_currency,
                                "payment_methods": stripe_payment_methods,
                            }
                        },
                        "payment_provider": PAYMENT_PROVIDERS.STRIPE,
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
            if PAYMENT_PROVIDERS.STRIPE in customer.integrations:
                invoices = self._import_payment_objects_for_customer(customer)
                imported_invoices[customer.customer_id] = invoices
        return imported_invoices

    def _import_payment_objects_for_customer(self, customer):
        from metering_billing.models import Invoice

        payload = {}
        if not self.self_hosted:
            payload["stripe_account"] = customer.organization.payment_provider_ids.get(
                PAYMENT_PROVIDERS.STRIPE
            )
        invoices = stripe.Invoice.list(
            customer=customer.integrations[PAYMENT_PROVIDERS.STRIPE]["id"], **payload
        )
        lotus_invoices = []
        for stripe_invoice in invoices.auto_paging_iter():
            if Invoice.objects.filter(
                organization=customer.organization,
                external_payment_obj_id=stripe_invoice.id,
            ).exists():
                continue
            cost_due = Decimal(stripe_invoice.amount_due) / 100
            invoice_kwargs = {
                "customer": customer,
                "cost_due": cost_due,
                "issue_date": datetime.datetime.fromtimestamp(
                    stripe_invoice.created, pytz.utc
                ),
                "org_connected_to_cust_payment_provider": True,
                "cust_connected_to_payment_provider": True,
                "external_payment_obj_id": stripe_invoice.id,
                "external_payment_obj_type": PAYMENT_PROVIDERS.STRIPE,
                "organization": customer.organization,
            }
            lotus_invoice = Invoice.objects.create(**invoice_kwargs)
            lotus_invoices.append(lotus_invoice)
        return lotus_invoices

    def create_customer(self, customer):
        from metering_billing.models import Organization, OrganizationSetting

        if (
            customer.organization.organization_type
            == Organization.OrganizationType.PRODUCTION
        ):
            stripe.api_key = self.live_secret_key
        else:
            stripe.api_key = self.test_secret_key

        setting = OrganizationSetting.objects.get(
            setting_name=ORGANIZATION_SETTING_NAMES.GENERATE_CUSTOMER_IN_STRIPE_AFTER_LOTUS,
            organization=customer.organization,
            setting_group=ORGANIZATION_SETTING_GROUPS.STRIPE,
        )
        setting_value = setting.setting_values.get("value", False)
        if setting_value is True:
            assert (
                customer.integrations.get(PAYMENT_PROVIDERS.STRIPE, {}).get("id")
                is None
            ), "Customer already has a Stripe ID"
            customer_kwargs = {
                "name": customer.customer_name,
                "email": customer.email,
            }
            if not self.self_hosted:
                org_stripe_acct = customer.organization.payment_provider_ids.get(
                    PAYMENT_PROVIDERS.STRIPE, None
                )
                assert (
                    org_stripe_acct is not None
                ), "Organization does not have a Stripe account ID"
                customer_kwargs["stripe_account"] = org_stripe_acct
            try:
                stripe_customer = stripe.Customer.create(**customer_kwargs)
                customer.integrations[PAYMENT_PROVIDERS.STRIPE] = {
                    "id": stripe_customer.id,
                    "email": customer.email,
                    "metadata": {},
                    "name": customer.customer_name,
                }
                customer.save()
            except Exception:
                pass
        elif setting_value is False:
            pass
        else:
            raise Exception(
                "Invalid value for generate_customer_after_creating_in_lotus setting"
            )

    def create_payment_object(self, invoice) -> str:
        from metering_billing.models import Organization

        if (
            invoice.organization.organization_type
            == Organization.OrganizationType.PRODUCTION
        ):
            stripe.api_key = self.live_secret_key
        else:
            stripe.api_key = self.test_secret_key
        # check everything works as expected + build invoice item
        assert invoice.external_payment_obj_id is None
        customer = invoice.customer
        stripe_customer_id = customer.integrations.get(
            PAYMENT_PROVIDERS.STRIPE, {}
        ).get("id")
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
            org_stripe_acct = customer.organization.payment_provider_ids.get(
                PAYMENT_PROVIDERS.STRIPE, None
            )
            assert (
                org_stripe_acct is not None
            ), "Organization does not have a Stripe account ID"
            invoice_kwargs["stripe_account"] = org_stripe_acct

        for line_item in invoice.line_items.all().order_by(
            F("associated_subscription_record").desc(nulls_last=True)
        ):
            name = line_item.name
            amount = line_item.subtotal
            customer = stripe_customer_id
            period = {
                "start": int(line_item.start_date.timestamp()),
                "end": int(line_item.end_date.timestamp()),
            }
            tax_behavior = "inclusive"
            sr = line_item.associated_subscription_record
            metadata = {
                "plan_name": sr.billing_plan.plan.plan_name,
            }
            filters = sr.filters.all()
            for f in filters:
                metadata[f.property_name] = f.comparison_value[0]
                name += f" - ({f.property_name} : {f.comparison_value[0]})"
            inv_dict = {
                "description": name,
                "amount": int(amount * 100),
                "customer": customer,
                "period": period,
                "currency": invoice.currency.code.lower(),
                "tax_behavior": tax_behavior,
                "metadata": metadata,
            }
            if not self.self_hosted:
                inv_dict["stripe_account"] = org_stripe_acct
            stripe.InvoiceItem.create(**inv_dict)
        stripe_invoice = stripe.Invoice.create(**invoice_kwargs)
        return stripe_invoice.id

    def get_post_data_serializer(self) -> serializers.Serializer:
        class StripePostRequestDataSerializer(serializers.Serializer):
            authorization_code = serializers.CharField()

        return StripePostRequestDataSerializer

    def handle_post(self, data, organization) -> PaymentProviderPostResponseSerializer:
        from metering_billing.models import Organization

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
                    "payment_processor": PAYMENT_PROVIDERS.STRIPE,
                    "success": False,
                    "details": response.get("error_description"),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        org_pp_ids = organization.payment_provider_ids
        org_pp_ids[PAYMENT_PROVIDERS.STRIPE] = response["stripe_user_id"]
        organization.payment_provider_ids = org_pp_ids
        organization.save()
        self.initialize_settings(organization)

        response = {
            "payment_processor": PAYMENT_PROVIDERS.STRIPE,
            "success": True,
            "details": "Successfully connected to Stripe",
        }
        serializer = PaymentProviderPostResponseSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        return Response(validated_data, status=status.HTTP_200_OK)

    def get_redirect_url(self, organization) -> str:
        from metering_billing.models import Organization

        if organization.organization_type == Organization.OrganizationType.PRODUCTION:
            return self.live_redirect_url
        else:
            return self.test_redirect_url

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

        org_ppis = organization.payment_provider_ids
        stripe_cust_kwargs = {}
        if org_ppis.get(PAYMENT_PROVIDERS.STRIPE) not in [None, ""]:
            stripe_cust_kwargs["stripe_account"] = org_ppis.get(
                PAYMENT_PROVIDERS.STRIPE
            )
        else:
            if not self.self_hosted:
                raise ExternalConnectionInvalid(
                    "Organization does not have a Stripe ID. Cannot transfer subscriptions."
                )

        stripe_subscriptions = stripe.Subscription.search(
            query="status:'active'", **stripe_cust_kwargs
        )
        plans_with_links = (
            Plan.objects.filter(organization=organization, status=PLAN_STATUS.ACTIVE)
            .prefetch_related(
                Prefetch(
                    "external_links",
                    queryset=ExternalPlanLink.objects.filter(
                        organization=organization, source=PAYMENT_PROVIDERS.STRIPE
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
                    integrations__stripe__id=subscription.customer,
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
                billing_plan = Plan.objects.get(id=matching_plans[0][0])
                # check to see if subscription exists
                validated_data = {
                    "organization": organization,
                    "customer": customer,
                    "billing_plan": billing_plan.display_version,
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
                SubscriptionRecord.objects.create(**validated_data)
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
        OrganizationSetting.objects.create(
            organization=organization,
            setting_name=ORGANIZATION_SETTING_NAMES.GENERATE_CUSTOMER_IN_STRIPE_AFTER_LOTUS,
            setting_values={"value": generate_stripe_after_lotus_value},
            setting_group=PAYMENT_PROVIDERS.STRIPE,
        )


PAYMENT_PROVIDER_MAP = {
    PAYMENT_PROVIDERS.STRIPE: StripeConnector(),
}
