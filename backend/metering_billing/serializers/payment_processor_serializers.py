from metering_billing.utils.enums import PAYMENT_PROCESSORS
from rest_framework import serializers


class SinglePaymentProcesorSerializer(serializers.Serializer):
    payment_provider_name = serializers.CharField()
    connected = serializers.BooleanField()
    redirect_url = serializers.URLField(allow_blank=True)
    self_hosted = serializers.BooleanField()
    connection_id = serializers.CharField(allow_null=True)
    working = serializers.BooleanField()


class PaymentProcesorGetResponseSerializer(serializers.Serializer):
    payment_providers = serializers.ListField(child=SinglePaymentProcesorSerializer())


class PaymentProcesorPostResponseSerializer(serializers.Serializer):
    payment_processor = serializers.ChoiceField(choices=PAYMENT_PROCESSORS.choices)
    success = serializers.BooleanField()
    details = serializers.CharField()


class PaymentProcesorPostDataSerializer(serializers.Serializer):
    payment_processor = serializers.ChoiceField(choices=PAYMENT_PROCESSORS.choices)
    data = serializers.JSONField()


class PaymentProcesorPostRequestSerializer(serializers.Serializer):
    pp_info = PaymentProcesorPostDataSerializer()
