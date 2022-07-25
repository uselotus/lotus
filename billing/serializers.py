from rest_framework import serializers

from .models import Event, Subscription


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
