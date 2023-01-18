from api.serializers.model_serializers import (
    InvoiceSerializer,
    LightweightSubscriptionRecordSerializer,
    UsageAlertSerializer,
)
from metering_billing.utils.enums import WEBHOOK_TRIGGER_EVENTS
from rest_framework import serializers


class InvoiceCreatedSerializer(serializers.Serializer):
    payload = InvoiceSerializer()
    event_type = serializers.ReadOnlyField(
        default=WEBHOOK_TRIGGER_EVENTS.INVOICE_CREATED
    )


class InvoicePaidSerializer(serializers.Serializer):
    payload = InvoiceSerializer()
    event_type = serializers.ReadOnlyField(default=WEBHOOK_TRIGGER_EVENTS.INVOICE_PAID)


class UsageAlertPayload(serializers.Serializer):
    subscription = LightweightSubscriptionRecordSerializer()
    usage_alert = UsageAlertSerializer()
    usage = serializers.DecimalField(max_digits=20, decimal_places=10)
    time_triggered = serializers.DateTimeField()


class UsageAlertTriggeredSerializer(serializers.Serializer):
    event_type = serializers.ReadOnlyField(
        default=WEBHOOK_TRIGGER_EVENTS.USAGE_ALERT_TRIGGERED
    )
    payload = UsageAlertPayload()
