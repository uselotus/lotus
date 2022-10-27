from metering_billing.utils.enums import PAYMENT_PROVIDERS
from rest_framework import serializers


class SinglePaymentProviderSerializer(serializers.Serializer):
    payment_provider_name = serializers.CharField()
    connected = serializers.BooleanField()
    redirect_link = serializers.URLField()


class PaymentProviderGetResponseSerializer(serializers.Serializer):
    payment_providers = serializers.ListField(child=SinglePaymentProviderSerializer())


class PaymentProviderPostResponseSerializer(serializers.Serializer):
    payment_processor = serializers.ChoiceField(choices=PAYMENT_PROVIDERS.choices)
    success = serializers.BooleanField()
    details = serializers.CharField()


class PaymentProviderPostRequestSerializer(serializers.Serializer):
    payment_processor = serializers.ChoiceField(choices=PAYMENT_PROVIDERS.choices)
    data = serializers.JSONField()
