import json

import requests
from django.conf import settings
from drf_spectacular.utils import extend_schema
from metering_billing.exceptions import (
    CRMIntegrationNotAllowed,
    CRMNotSupported,
    EnvironmentNotConnected,
)
from metering_billing.models import UnifiedCRMOrganizationIntegration
from metering_billing.permissions import ValidOrganization
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

SELF_HOSTED = settings.SELF_HOSTED
VESSEL_API_TOKEN = settings.VESSEL_API_TOKEN


class CRMUnifiedAPIView(APIView):
    permission_classes = [IsAuthenticated & ValidOrganization]

    def check_vessel_token_and_crm_integration(self, request):
        if VESSEL_API_TOKEN is None:
            raise EnvironmentNotConnected()
        if not request.organization.team.crm_integration_allowed:
            raise CRMIntegrationNotAllowed()
        return None

    @extend_schema(
        request=None,
        responses={200: None},
    )
    def link_token(self, request, format=None):
        self.check_vessel_token_and_crm_integration(request)

        response = requests.post(
            "https://api.vessel.land/link/token",
            headers={"vessel-api-token": VESSEL_API_TOKEN},
        )
        body = response.json()
        return Response({"linkToken": body["linkToken"]}, status=status.HTTP_200_OK)

    @extend_schema(
        request=None,
        responses={200: None},
    )
    def store_token(self, request, format=None):
        self.check_vessel_token_and_crm_integration(request)

        public_token = request.data["publicToken"]
        response = requests.post(
            "https://api.vessel.land/link/exchange",
            headers={"vessel-api-token": VESSEL_API_TOKEN},
            data=json.dumps({"publicToken": public_token}),
        )
        response = response.json()

        connection_id = response["connectionId"]
        access_token = response["accessToken"]
        native_org_url = response["nativeOrgUrl"]
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
