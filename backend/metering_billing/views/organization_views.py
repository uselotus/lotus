import datetime
from decimal import Decimal

from django.conf import settings
from metering_billing.serializers.internal_serializers import *
from metering_billing.serializers.model_serializers import *
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import JsonResponse
from metering_billing.services.organization import organization_service
from django.core import serializers

POSTHOG_PERSON = settings.POSTHOG_PERSON


class OrganizationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        """
        Get the current settings for the organization.
        """
        organization_id = request.query_params.get("id", None)
        organization = organization_service.get(
            user_id=request.user.id, organization_id=organization_id
        )
        return JsonResponse({"organization": list(organization.values())})


class InviteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        email = request.data.get("email", None)
        invite = organization_service.invite(user_id=request.user.id, email=email)

        return JsonResponse({"email": email})
