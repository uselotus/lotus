from metering_billing.auth import parse_organization
from metering_billing.models import Customer, PlanVersion
from metering_billing.utils.enums import PLAN_STATUS
from rest_framework import serializers

from .model_serializers import EventSerializer, PlanVersionSerializer
from .serializer_utils import SlugRelatedFieldWithOrganization

## CUSTOM SERIALIZERS


class UpdatePlanVersionRequestSerializer(serializers.Serializer):
    old_version_id = serializers.CharField()
    updated_billing_plan = PlanVersionSerializer()
    update_behavior = serializers.ChoiceField(
        choices=["replace_immediately", "replace_on_renewal"]
    )

    def create(self, validated_data):
        request = self.context.get("request", None)
        org = parse_organization(request)
        validated_data["updated_billing_plan"]["organization"] = org
        for component in validated_data["updated_billing_plan"]["components"]:
            bm = component.pop("billable_metric")
            component["billable_metric_name"] = bm.billable_metric_name
        serializer = PlanVersionSerializer(
            data=validated_data["updated_billing_plan"], context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.validated_data["organization"] = org
        billing_plan = serializer.save()
        return billing_plan


class EventPreviewSerializer(serializers.Serializer):
    events = EventSerializer(many=True)
    total_pages = serializers.IntegerField(required=True)


class CustomerNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ("name",)


class CustomerIDSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ("customer_id",)


class PlanVersionNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanVersion
        fields = ("name",)
