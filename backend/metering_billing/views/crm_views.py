import requests
from django.conf import settings
from drf_spectacular.utils import extend_schema, inline_serializer
from metering_billing.exceptions import (
    CRMIntegrationNotAllowed,
    CRMNotSupported,
    EnvironmentNotConnected,
)
from metering_billing.models import UnifiedCRMOrganizationIntegration
from metering_billing.permissions import ValidOrganization
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

SELF_HOSTED = settings.SELF_HOSTED
VESSEL_API_KEY = settings.VESSEL_API_KEY


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


class CRMUnifiedAPIView(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    permission_classes = [IsAuthenticated & ValidOrganization]

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
                organization=organization, crm_type=crm_value
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
        crm_type_value = UnifiedCRMOrganizationIntegration.get_crm_provider_from_label(
            integration_id
        )
        if crm_type_value is None:
            raise CRMNotSupported(f"CRM type {integration_id} is not supported")
        conn, _ = UnifiedCRMOrganizationIntegration.objects.update_or_create(
            organization=request.organization,
            crm_type=crm_type_value,
            defaults={
                "access_token": access_token,
                "native_org_url": native_org_url,
                "native_org_id": native_org_id,
                "connection_id": connection_id,
            },
        )
        conn.save()
        return Response({"success": True}, status=status.HTTP_200_OK)
        return Response({"success": True}, status=status.HTTP_200_OK)
