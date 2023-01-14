import json

import requests
from django.conf import settings
from metering_billing.utils import (
    make_all_dates_times_strings,
    make_all_decimals_floats,
    now_utc,
)
from metering_billing.utils.enums import WEBHOOK_TRIGGER_EVENTS
from svix.api import MessageIn, Svix

SVIX_CONNECTOR = settings.SVIX_CONNECTOR


def invoice_created_webhook(invoice, organization):
    from metering_billing.models import WebhookEndpoint
    from metering_billing.serializers.model_serializers import InvoiceSerializer

    if SVIX_CONNECTOR is not None:
        endpoints = (
            WebhookEndpoint.objects.filter(organization=organization)
            .prefetch_related("triggers")
            .filter(triggers__trigger_name=WEBHOOK_TRIGGER_EVENTS.INVOICE_CREATED)
            .distinct()
        )
        if endpoints.count() > 0:
            svix = SVIX_CONNECTOR
            now = str(now_utc())
            invoice_data = InvoiceSerializer(invoice).data
            invoice_data = make_all_decimals_floats(invoice_data)
            invoice_data = make_all_dates_times_strings(invoice_data)
            svix.message.create(
                organization.organization_id.hex,
                MessageIn(
                    event_type=WEBHOOK_TRIGGER_EVENTS.INVOICE_CREATED,
                    event_id=str(organization.organization_id.hex)
                    + "_"
                    + str(invoice_data["invoice_number"])
                    + "_"
                    + "created",
                    payload={
                        "attempt": 5,
                        "created_at": now,
                        "properties": invoice_data,
                    },
                ),
            )


def invoice_paid_webhook(invoice, organization):
    from metering_billing.models import WebhookEndpoint
    from metering_billing.serializers.model_serializers import InvoiceSerializer

    if SVIX_CONNECTOR is not None:
        endpoints = (
            WebhookEndpoint.objects.filter(organization=organization)
            .prefetch_related("triggers")
            .filter(triggers__trigger_name=WEBHOOK_TRIGGER_EVENTS.INVOICE_PAID)
            .distinct()
        )
        if endpoints.count() > 0:
            svix = SVIX_CONNECTOR
            now = str(now_utc())
            invoice_data = InvoiceSerializer(invoice).data
            invoice_data = make_all_decimals_floats(invoice_data)
            invoice_data = make_all_dates_times_strings(invoice_data)
            svix.message.create(
                organization.organization_id.hex,
                MessageIn(
                    event_type=WEBHOOK_TRIGGER_EVENTS.INVOICE_PAID,
                    event_id=str(organization.organization_id.hex)
                    + "_"
                    + str(invoice_data["invoice_number"])
                    + "_"
                    + "paid",
                    payload={
                        "attempt": 5,
                        "created_at": now,
                        "properties": invoice_data,
                    },
                ),
            )


def usage_alert_webhook(usage_alert, alert_result, subscription_record, organization):
    from metering_billing.models import WebhookEndpoint
    from metering_billing.serializers.model_serializers import (
        LightweightSubscriptionRecordSerializer,
        UsageAlertSerializer,
    )
    from metering_billing.serializers.response_serializers import (
        UsageAlertTriggeredSerializer,
    )

    if SVIX_CONNECTOR is not None:
        endpoints = (
            WebhookEndpoint.objects.filter(organization=organization)
            .prefetch_related("triggers")
            .filter(triggers__trigger_name=WEBHOOK_TRIGGER_EVENTS.USAGE_ALERT_TRIGGERED)
            .distinct()
        )
        if endpoints.count() > 0:
            svix = SVIX_CONNECTOR
            now = str(now_utc())
            data = {
                "subscription": LightweightSubscriptionRecordSerializer(
                    subscription_record
                ).data,
                "usage_alert": UsageAlertSerializer(usage_alert).data,
                "usage": alert_result.usage,
                "time_triggered": alert_result.last_run_timestamp,
            }
            serialized_data = UsageAlertTriggeredSerializer(data).data
            event_id = (
                str(organization.organization_id)[:50]
                + "_"
                + str(usage_alert.usage_alert_id)[:50]
                + "_"
                + str(subscription_record.subscription_record_id)[:50]
                + "_"
                + str(alert_result.last_run_timestamp)
                + "_"
                + "triggered"
            )
            svix.message.create(
                organization.organization_id,
                MessageIn(
                    event_type=WEBHOOK_TRIGGER_EVENTS.USAGE_ALERT_TRIGGERED,
                    event_id=event_id,
                    payload={
                        "attempt": 5,
                        "created_at": now,
                        "properties": serialized_data,
                    },
                ),
            )
