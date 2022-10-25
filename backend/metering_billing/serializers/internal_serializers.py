from django.conf import settings
from metering_billing.models import Customer, Organization, PlanVersion, Subscription
from rest_framework import serializers

from .model_serializers import EventSerializer

POSTHOG_PERSON = settings.POSTHOG_PERSON

## CUSTOM SERIALIZERS


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


# Invoice Serializers
class InvoiceOrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ("company_name",)


class InvoiceCustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = (
            "customer_name",
            "customer_id",
        )

    customer_name = serializers.CharField(source="name")


class InvoicePlanVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanVersion
        fields = (
            "name",
            "description",
            "version",
            "interval",
            "flat_rate",
            "flat_fee_billing_type",
            "usage_billing_type",
        )

    flat_rate = serializers.SerializerMethodField()
    name = serializers.CharField(source="plan.plan_name")
    interval = serializers.CharField(source="plan.plan_duration")

    def get_flat_rate(self, obj):
        return float(obj.flat_rate.amount)


class InvoiceSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ("start_date", "end_date", "billing_plan", "subscription_id")

    billing_plan = InvoicePlanVersionSerializer()
