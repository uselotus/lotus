from rest_framework import serializers

from .models import Event, Customer, Subscription


class EventSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Event
        fields = (
            "customer",
            "event_name",
            "time_created",
            "properties",
            "idempotency_id",
        )


class CustomerSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Customer
        fields = (
            "name",
            "company_name",
            "customer_id",
            "billing_id",
            "balance",
            "billing_configuration",
        )


class SubscriptionSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Subscription
        fields = (
            "customer",
            "billing_plan",
            "time_created",
            "time_ended",
            "id",
            "status",
        )
