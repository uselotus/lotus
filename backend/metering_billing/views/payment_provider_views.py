from drf_spectacular.utils import extend_schema
from metering_billing.auth import parse_organization
from metering_billing.payment_providers import PAYMENT_PROVIDER_MAP
from metering_billing.serializers.payment_provider_serializers import (
    PaymentProviderGetResponseSerializer,
    PaymentProviderPostRequestSerializer,
    PaymentProviderPostResponseSerializer,
)
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class PaymentProviderView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: PaymentProviderGetResponseSerializer()},
    )
    def get(self, request, format=None):
        organization = parse_organization(request)
        response = []
        for payment_processor_name, pp_obj in PAYMENT_PROVIDER_MAP.items():
            response = {
                "name": payment_processor_name,
                "connected": pp_obj.organization_connected(organization),
                "redirect_link": pp_obj.get_redirect_link(organization),
            }
        serializer = PaymentProviderGetResponseSerializer(data=response)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)

    @extend_schema(
        request=PaymentProviderPostRequestSerializer,
        responses={200: PaymentProviderPostResponseSerializer},
    )
    def post(self, request, format=None):
        organization = parse_organization(request)
        # parse outer level request
        serializer = PaymentProviderPostRequestSerializer(data=request)
        serializer.is_valid(raise_exception=True)
        payment_processor_name = serializer.validated_data["payment_processor_name"]
        data = serializer.validated_data["data"]

        # validate payment processor specific data
        data_serializer = PAYMENT_PROVIDER_MAP[
            payment_processor_name
        ].get_post_data_serializer()
        data_serializer = data_serializer(data=data)
        data_serializer.is_valid(raise_exception=True)
        data = data_serializer.validated_data

        # call payment processor specific post method
        response = PAYMENT_PROVIDER_MAP[payment_processor_name].handle_post(
            organization, data
        )

        return response
