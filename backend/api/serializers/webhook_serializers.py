from api.serializers.model_serializers import (
    CustomerSerializer,
    InvoiceSerializer,
    LightweightSubscriptionRecordSerializer,
    UsageAlertSerializer,
    SubscriptionRecordSerializer,
)
from metering_billing.utils.enums import WEBHOOK_TRIGGER_EVENTS
from rest_framework import serializers


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


class InvoicePastDueSerializer(serializers.Serializer):
    payload = InvoiceSerializer()
    event_type = serializers.CharField(
        default=WEBHOOK_TRIGGER_EVENTS.INVOICE_PAST_DUE, read_only=True
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


class CustomerCreatedSerializer(serializers.Serializer):
    payload = CustomerSerializer()
    eventType = serializers.CharField(
        default=WEBHOOK_TRIGGER_EVENTS.CUSTOMER_CREATED, read_only=True
    )


class SubscriptionCreatedSerializer(serializers.Serializer):
    payload = SubscriptionRecordSerializer()
    eventType = serializers.CharField(
        default=WEBHOOK_TRIGGER_EVENTS.SUBSCRIPTION_CREATED, read_only=True
    )
