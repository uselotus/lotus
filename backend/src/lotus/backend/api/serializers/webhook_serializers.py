from rest_framework import serializers

from api.serializers.model_serializers import (
    InvoiceSerializer,
    LightweightSubscriptionRecordSerializer,
    UsageAlertSerializer,
)
from lotus.backend.metering_billing.utils.enums import WEBHOOK_TRIGGER_EVENTS


class InvoiceCreatedSerializer(serializers.Serializer):
    payload = InvoiceSerializer()
    event_type = serializers.CharField(
        default=WEBHOOK_TRIGGER_EVENTS.INVOICE_CREATED, read_only=True
    )


class InvoicePaidSerializer(serializers.Serializer):
    payload = InvoiceSerializer()
    event_type = serializers.CharField(
        default=WEBHOOK_TRIGGER_EVENTS.INVOICE_PAID, read_only=True
    )


class UsageAlertPayload(serializers.Serializer):
    subscription = LightweightSubscriptionRecordSerializer()
    usage_alert = UsageAlertSerializer()
    usage = serializers.DecimalField(max_digits=20, decimal_places=10)
    time_triggered = serializers.DateTimeField()


class UsageAlertTriggeredSerializer(serializers.Serializer):
    event_type = serializers.CharField(
        default=WEBHOOK_TRIGGER_EVENTS.USAGE_ALERT_TRIGGERED, read_only=True
    )
    payload = UsageAlertPayload()
