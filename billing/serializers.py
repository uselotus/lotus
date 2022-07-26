from rest_framework import serializers

from .models import Event, Customer


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
            "external_id",
            "billing_id",
        )
