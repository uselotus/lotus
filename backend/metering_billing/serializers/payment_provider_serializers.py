from metering_billing.utils.enums import PAYMENT_PROVIDERS
from rest_framework import serializers


class SinglePaymentProviderSerializer(serializers.Serializer):
    payment_provider_name = serializers.CharField()
    connected = serializers.BooleanField()
    redirect_url = serializers.URLField(allow_blank=True)
    self_hosted = serializers.BooleanField()
    connection_id = serializers.CharField(allow_null=True)


class PaymentProviderGetResponseSerializer(serializers.Serializer):
    payment_providers = serializers.ListField(child=SinglePaymentProviderSerializer())


class PaymentProviderPostResponseSerializer(serializers.Serializer):
    payment_processor = serializers.ChoiceField(choices=PAYMENT_PROVIDERS.choices)
    success = serializers.BooleanField()
    details = serializers.CharField()


class PaymentProviderPostDataSerializer(serializers.Serializer):
    payment_processor = serializers.ChoiceField(choices=PAYMENT_PROVIDERS.choices)
    data = serializers.JSONField()


class PaymentProviderPostRequestSerializer(serializers.Serializer):
    pp_info = PaymentProviderPostDataSerializer()
