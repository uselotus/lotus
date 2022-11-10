from django.conf import settings
from metering_billing.models import Customer, Organization, PlanVersion, Subscription
from rest_framework import serializers

from .model_serializers import EventSerializer

## CUSTOM SERIALIZERS


class EventPreviewSerializer(serializers.Serializer):
    events = EventSerializer(many=True)
    total_pages = serializers.IntegerField(required=True)


class CustomerNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ("customer_name",)


class CustomerIDSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ("customer_id",)


class PlanVersionNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanVersion
        fields = ("name",)
