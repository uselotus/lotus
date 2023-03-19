import json

import pycountry
import requests
import sentry_sdk
from django.conf import settings
from drf_spectacular.utils import extend_schema, inline_serializer
from metering_billing.exceptions import (
    CRMIntegrationNotAllowed,
    CRMNotSupported,
    EnvironmentNotConnected,
)
from metering_billing.models import (
    Address,
    Customer,
    Invoice,
    OrganizationSetting,
    UnifiedCRMCustomerIntegration,
    UnifiedCRMInvoiceIntegration,
    UnifiedCRMOrganizationIntegration,
)
from metering_billing.permissions import ValidOrganization
from metering_billing.utils.enums import ORGANIZATION_SETTING_NAMES
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from scourgify import normalize_address_record

SELF_HOSTED = settings.SELF_HOSTED
VESSEL_API_KEY = settings.VESSEL_API_KEY
VITE_API_URL = settings.VITE_API_URL


class SingleCRMProviderSerializer(serializers.Serializer):
    crm_provider_name = serializers.ChoiceField(
        choices=UnifiedCRMOrganizationIntegration.CRMProvider.labels
    )
    connected = serializers.BooleanField()
    self_hosted = serializers.BooleanField()
    working = serializers.BooleanField()
    connection_id = serializers.CharField(allow_null=True)
    account_id = serializers.CharField(allow_null=True)
    native_org_url = serializers.URLField(allow_null=True)


class UpdateCRMSourceOfTruthSerializer(serializers.Serializer):
    crm_provider_name = serializers.ChoiceField(
        choices=UnifiedCRMOrganizationIntegration.CRMProvider.labels
    )
    lotus_is_source = serializers.BooleanField()


class CRMUnifiedAPIView(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    permission_classes = [IsAuthenticated & ValidOrganization]

    @extend_schema(
        request=UpdateCRMSourceOfTruthSerializer,
        responses={
            200: inline_serializer(
                "SuccessResponse", {"success": serializers.BooleanField()}
            )
        },
    )
    def update_crm_customer_source_of_truth(self, request, format=None):
        organization = request.organization
        serializer = UpdateCRMSourceOfTruthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        crm_provider_name = serializer.validated_data["crm_provider_name"]
        lotus_is_source = serializer.validated_data["lotus_is_source"]
        if not organization.crm_settings_provisioned:
            organization.provision_crm_settings()
        org_setting = OrganizationSetting.objects.get(
            organization=organization,
            setting_name=ORGANIZATION_SETTING_NAMES.CRM_CUSTOMER_SOURCE,
        )
        setting_values = org_setting.setting_values
        setting_values[crm_provider_name] = lotus_is_source
        org_setting.setting_values = setting_values
        org_setting.save()
        return Response({"success": True})

    @extend_schema(
        request=None,
        responses={200: SingleCRMProviderSerializer(many=True)},
    )
    def get_crms(self, request, format=None):
        organization = request.organization
        response = []
        for (
            crm_value,
            crm_provider_name,
        ) in UnifiedCRMOrganizationIntegration.CRMProvider.choices:
            integration = UnifiedCRMOrganizationIntegration.objects.filter(
                organization=organization, crm_provider=crm_value
            ).first()
            data_dict = {
                "crm_provider_name": crm_provider_name,
                "working": True,  # always "working" for now
                "connected": False,
                "self_hosted": SELF_HOSTED,
                "connection_id": None,
                "account_id": None,
                "native_org_url": None,
            }
            if integration:
                data_dict["connected"] = True
                data_dict["connection_id"] = integration.connection_id
                data_dict["account_id"] = integration.native_org_id
                data_dict["native_org_url"] = integration.native_org_url
            response.append(data_dict)

        serializer = SingleCRMProviderSerializer(data=response, many=True)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)

    def check_vessel_token_and_crm_integration(self, request):
        if VESSEL_API_KEY is None:
            raise EnvironmentNotConnected()
        if not request.organization.team.crm_integration_allowed:
            raise CRMIntegrationNotAllowed()
        return None

    @extend_schema(
        request=None,
        responses={
            200: inline_serializer(
                "LinkTokenResponse",
                fields={
                    "link_token": serializers.CharField(
                        help_text="The token used to link Vessel and the CRM"
                    )
                },
            )
        },
    )
    def link_token(self, request, format=None):
        self.check_vessel_token_and_crm_integration(request)

        response = requests.post(
            "https://api.vessel.land/link/token",
            headers={"vessel-api-token": VESSEL_API_KEY},
        )
        body = response.json()
        return Response({"link_token": body["linkToken"]}, status=status.HTTP_200_OK)

    @extend_schema(
        request=inline_serializer(
            "StoreTokenRequest",
            fields={
                "publicToken": serializers.CharField(
                    help_text="The public token obtained from the Vessel API"
                )
            },
        ),
        responses={
            200: inline_serializer(
                "StoreTokenResponse",
                fields={
                    "success": serializers.BooleanField(
                        help_text="Whether the token was successfully stored"
                    )
                },
            )
        },
    )
    def store_token(self, request, format=None):
        self.check_vessel_token_and_crm_integration(request)

        public_token = request.data["public_token"]
        response = requests.post(
            "https://api.vessel.land/link/exchange",
            headers={
                "vessel-api-token": VESSEL_API_KEY,
                "Content-Type": "application/json",
            },
            json={"publicToken": public_token},
        )
        response = response.json()
        connection_id = response["connectionId"]
        access_token = response["accessToken"]
        native_org_url = response["nativeOrgURL"]
        native_org_id = response["nativeOrgId"]
        integration_id = response["integrationId"]
        crm_provider_value = (
            UnifiedCRMOrganizationIntegration.get_crm_provider_from_label(
                integration_id
            )
        )
        if crm_provider_value is None:
            raise CRMNotSupported(f"CRM type {integration_id} is not supported")
        conn, _ = UnifiedCRMOrganizationIntegration.objects.update_or_create(
            organization=request.organization,
            crm_provider=crm_provider_value,
            defaults={
                "access_token": access_token,
                "native_org_url": native_org_url,
                "native_org_id": native_org_id,
                "connection_id": connection_id,
            },
        )
        conn.save()
        return Response({"success": True}, status=status.HTTP_200_OK)


def send_invoice_to_salesforce(invoice, customer, accountId, access_token):
    headers = {
        "vessel-api-token": VESSEL_API_KEY,
    }
    url = "https://api.vessel.land/crm/note"
    body = {
        "lotus_url": VITE_API_URL + f"customers/{customer.customer_id}",
        "invoice_pdf": invoice.invoice_pdf,
    }
    note = {
        "accountId": accountId,
        "content": json.dumps(body),
        "isPrivate": False,
        "additional": {
            "Title": f"[LOTUS] Invoice on {invoice.issue_date.strftime('%Y-%m-%d')}",
        },
    }
    payload = {
        "accessToken": access_token,
        "note": note,
    }
    response = requests.post(url, headers=headers, json=payload)
    try:
        response.raise_for_status()  # raises exception when not a 2xx response
    except requests.exceptions.HTTPError as e:
        sentry_sdk.capture_exception(e)
        print(e)
        print(response.text)
        return
    unified_id = response.json()["id"]
    get_url = url + f"?accessToken={access_token}&id={unified_id}"
    response = requests.get(
        get_url,
        headers=headers,
    )
    response_json = response.json()
    integration = UnifiedCRMInvoiceIntegration.objects.create(
        organization=invoice.organization,
        crm_provider=UnifiedCRMOrganizationIntegration.CRMProvider.SALESFORCE,
        unified_note_id=unified_id,
        native_invoice_id=response_json["note"]["nativeId"],
    )
    invoice.salesforce_integration = integration
    invoice.save()


def sync_invoices_with_salesforce(organization):
    connection = organization.unified_crm_organization_links.get(
        crm_provider=UnifiedCRMOrganizationIntegration.CRMProvider.SALESFORCE
    )
    access_token = connection.access_token

    customers_with_integration = organization.customers.filter(
        salesforce_integration__isnull=False
    )
    invoices_from_customers = Invoice.objects.filter(
        customer__in=customers_with_integration
    )
    for customer in customers_with_integration:
        invoices = invoices_from_customers.filter(
            customer=customer, salesforce_integration__isnull=True
        )
        accountId = customer.salesforce_integration.unified_account_id
        if not accountId:
            continue
        for invoice in invoices:
            send_invoice_to_salesforce(invoice, customer, accountId, access_token)


def sync_customers_with_salesforce(organization):
    org_setting = OrganizationSetting.objects.get(
        organization=organization,
        setting_name=ORGANIZATION_SETTING_NAMES.CRM_CUSTOMER_SOURCE,
    )
    setting_values = org_setting.setting_values
    lotus_is_source = setting_values["salesforce"]
    connection = organization.unified_crm_organization_links.get(
        crm_provider=UnifiedCRMOrganizationIntegration.CRMProvider.SALESFORCE
    )
    access_token = connection.access_token

    headers = {
        "vessel-api-token": VESSEL_API_KEY,
    }
    url = f"https://api.vessel.land/crm/accounts?accessToken={access_token}&allFields=true"
    response = requests.get(url, headers=headers)
    response.raise_for_status()  # raises exception when not a 2xx response
    accounts = response.json()["accounts"]

    customer_ids_set = {x["additional"].get("AccountNumber") for x in accounts}
    native_ids_set = {x["nativeId"] for x in accounts}
    if lotus_is_source:
        url = "https://api.vessel.land/crm/account"
        headers = {
            "Content-Type": "application/json",
            "vessel-api-token": VESSEL_API_KEY,
        }
        for customer in organization.customers.all():
            payload = {
                "accessToken": access_token,
                "account": {
                    "name": customer.customer_name,
                    "email": customer.email,
                },
            }
            if customer.shipping_address:
                payload["additional"] = {}
                payload["additional"]["ShippingAddress"] = {
                    "street": customer.shipping_address.line1,
                    "city": customer.shipping_address.city,
                    "state": customer.shipping_address.state,
                    "country": customer.shipping_address.country,
                    "postalCode": customer.shipping_address.postal_code,
                }
            if customer.billing_address:
                if not payload.get("additional"):
                    payload["additional"] = {}
                payload["additional"]["BillingAddress"] = {
                    "street": customer.billing_address.line1,
                    "city": customer.billing_address.city,
                    "state": customer.billing_address.state,
                    "country": customer.billing_address.country,
                    "postalCode": customer.billing_address.postal_code,
                }
            if customer.salesforce_integration:
                response = requests.patch(
                    url, headers=headers, data=json.dumps(payload)
                )
            else:
                # not in salesforce! We create
                response = requests.post(url, headers=headers, data=json.dumps(payload))
                unified_id = response.json()["id"]
                get_url = url + f"?accessToken={access_token}&id={unified_id}"
                response = requests.get(
                    get_url,
                    headers=headers,
                )
                response_json = response.json()
                integration = UnifiedCRMCustomerIntegration.objects.create(
                    organization=organization,
                    crm_provider=UnifiedCRMOrganizationIntegration.CRMProvider.SALESFORCE,
                    unified_account_id=unified_id,
                    native_customer_id=response_json["account"]["nativeId"],
                )
                customer.salesforce_integration = integration
                customer.save()
    else:
        lotus_customers = organization.customers.filter(
            customer_id__in=customer_ids_set
        )
        lotus_customer_integrations = organization.unified_crm_customer_links.filter(
            native_customer_id__in=native_ids_set
        )
        for account in accounts:
            name = account["name"]
            internal_id = (
                account["additional"].get("AccountNumber") or account["nativeId"]
            )
            native_id = account["nativeId"]
            unified_id = account["id"]
            billing_address = account["additional"]["BillingAddress"]
            shipping_address = account["additional"]["ShippingAddress"]
            if billing_address:
                try:
                    fuzzy_country = pycountry.countries.search_fuzzy(
                        billing_address["country"]
                    )
                except Exception:
                    fuzzy_country = None

                try:
                    billing_address = Address.objects.get_or_create(
                        line1=billing_address["street"],
                        city=billing_address["city"],
                        state=billing_address["state"],
                        country=fuzzy_country[0].alpha_2,
                        postal_code=billing_address["postalCode"],
                    )
                except Exception:
                    try:
                        normalized = normalize_address_record(billing_address["street"])
                        billing_address = Address.objects.get_or_create(
                            line1=normalized["address_line_1"],
                            line2=normalized["address_line_2"],
                            city=normalized["city"],
                            state=normalized["state"],
                            country="US",
                            postal_code=normalized["postal_code"],
                        )
                    except Exception:
                        billing_address = None
            if shipping_address:
                try:
                    fuzzy_country = pycountry.countries.search_fuzzy(
                        shipping_address["country"]
                    )
                except Exception:
                    fuzzy_country = None

                try:
                    shipping_address = Address.objects.get_or_create(
                        line1=shipping_address["street"],
                        city=shipping_address["city"],
                        state=shipping_address["state"],
                        country=fuzzy_country[0].alpha_2,
                        postal_code=shipping_address["postalCode"],
                    )
                except Exception:
                    try:
                        normalized = normalize_address_record(
                            shipping_address["street"]
                        )
                        shipping_address = Address.objects.get_or_create(
                            line1=normalized["address_line_1"],
                            line2=normalized["address_line_2"],
                            city=normalized["city"],
                            state=normalized["state"],
                            country="US",
                            postal_code=normalized["postal_code"],
                        )
                    except Exception:
                        shipping_address = None
            integration = lotus_customer_integrations.filter(
                native_customer_id=native_id
            ).first()
            matching_customer = lotus_customers.filter(customer_id=internal_id).first()
            if integration:
                customer = integration.customer
            elif matching_customer:
                customer = matching_customer
            else:
                customer = None

            if customer is None:
                customer = Customer.objects.create(
                    organization=organization,
                    customer_id=internal_id,
                    customer_name=name,
                    billing_address=billing_address,
                    shipping_address=shipping_address,
                )
            else:
                customer.customer_name = name
                customer.billing_address = billing_address
                customer.shipping_address = shipping_address
                customer.save()
            customer_integration = customer.salesforce_integration
            if not customer_integration:
                customer_integration = UnifiedCRMCustomerIntegration.objects.create(
                    organization=organization,
                    crm_provider=UnifiedCRMOrganizationIntegration.CRMProvider.SALESFORCE,
                    native_customer_id=native_id,
                    unified_account_id=unified_id,
                )
                customer.salesforce_integration = customer_integration
                customer.save()
