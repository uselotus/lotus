from metering_billing.auth import parse_organization
from metering_billing.models import Customer, PlanVersion
from metering_billing.utils.enums import PLAN_STATUS
from rest_framework import serializers

from .model_serializers import EventSerializer, PlanVersionSerializer
from .serializer_utils import SlugRelatedFieldWithOrganization


class RegistrationDetailSerializer(serializers.Serializer):
    company_name = serializers.CharField(allow_blank=True)
    industry = serializers.CharField(allow_blank=True)
    email = serializers.CharField()
    password = serializers.CharField()
    username = serializers.CharField()

    def validate(self, attrs):
        token = self.context.get("token", None)
        if not token:
            if attrs["company_name"] is None:
                raise serializers.ValidationError(
                    "Company name is required for registration"
                )
        return super().validate(attrs)


class RegistrationSerializer(serializers.Serializer):
    register = RegistrationDetailSerializer()
