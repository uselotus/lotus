from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from metering_billing.payment_providers import PAYMENT_PROVIDER_MAP
from metering_billing.permissions import ValidOrganization
from metering_billing.serializers.payment_provider_serializers import (
    PaymentProviderPostRequestSerializer,
    PaymentProviderPostResponseSerializer,
    SinglePaymentProviderSerializer,
)

SELF_HOSTED = settings.SELF_HOSTED


class PaymentProviderView(APIView):
    permission_classes = [IsAuthenticated & ValidOrganization]

    @extend_schema(
        request=None,
        responses={200: SinglePaymentProviderSerializer(many=True)},
    )
    def get(self, request, format=None):
        organization = request.organization
        response = []
        for payment_processor_name, pp_obj in PAYMENT_PROVIDER_MAP.items():
            pp_response = {
                "payment_provider_name": payment_processor_name,
                "connected": pp_obj.organization_connected(organization),
                "redirect_url": pp_obj.get_redirect_url(organization),
                "self_hosted": SELF_HOSTED,
                "connection_id": pp_obj.get_connection_id(organization),
            }
            response.append(pp_response)
        serializer = SinglePaymentProviderSerializer(data=response, many=True)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)

    @extend_schema(
        request=PaymentProviderPostRequestSerializer,
        responses={200: PaymentProviderPostResponseSerializer},
    )
    def post(self, request, format=None):
        organization = request.organization
        # parse outer level request
        serializer = PaymentProviderPostRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment_processor_name = serializer.validated_data["pp_info"][
            "payment_processor"
        ]
        data = serializer.validated_data["pp_info"]["data"]

        # validate payment processor specific data
        data_serializer = PAYMENT_PROVIDER_MAP[
            payment_processor_name
        ].get_post_data_serializer()
        data_serializer = data_serializer(data=data)
        data_serializer.is_valid(raise_exception=True)
        data = data_serializer.validated_data

        # call payment processor specific post method
        response = PAYMENT_PROVIDER_MAP[payment_processor_name].handle_post(
            data, organization
        )

        return response
