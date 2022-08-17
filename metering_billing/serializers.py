from rest_framework import serializers

from metering_billing.models import Event, Customer, Subscription, Invoice, BillingPlan


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = "__all__"


class EventSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Event
        fields = (
            "organization",
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
            "organization",
            "name",
            "customer_id",
            "billing_id",
            "balance",
        )


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = (
            "organization",
            "customer",
            "billing_plan",
            "start_date",
            "end_date",
            "status",
        )


class BillingPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingPlan
        fields = "__all__"
