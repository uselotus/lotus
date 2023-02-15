from django.conf import settings
from lotus.backend.metering_billing.utils import (
    make_all_dates_times_strings,
    make_all_decimals_floats,
    now_utc,
)
from lotus.backend.metering_billing.utils.enums import WEBHOOK_TRIGGER_EVENTS
from svix.api import MessageIn

SVIX_CONNECTOR = settings.SVIX_CONNECTOR


def invoice_created_webhook(invoice, organization):
    from api.serializers.model_serializers import InvoiceSerializer
    from lotus.backend.metering_billing.models import WebhookEndpoint

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
            response = {
                "event_type": WEBHOOK_TRIGGER_EVENTS.INVOICE_CREATED,
                "payload": invoice_data,
            }
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
                        "properties": response,
                    },
                ),
            )


def invoice_paid_webhook(invoice, organization):
    from api.serializers.model_serializers import InvoiceSerializer
    from lotus.backend.metering_billing.models import WebhookEndpoint

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
            response = {
                "event_type": WEBHOOK_TRIGGER_EVENTS.INVOICE_PAID,
                "payload": invoice_data,
            }
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
                        "properties": response,
                    },
                ),
            )


def usage_alert_webhook(usage_alert, alert_result, subscription_record, organization):
    from api.serializers.model_serializers import (
        LightweightSubscriptionRecordSerializer,
        UsageAlertSerializer,
    )
    from api.serializers.webhook_serializers import UsageAlertPayload
    from lotus.backend.metering_billing.models import WebhookEndpoint

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
            alert_data = {
                "subscription": LightweightSubscriptionRecordSerializer(
                    subscription_record
                ).data,
                "usage_alert": UsageAlertSerializer(usage_alert).data,
                "usage": alert_result.usage,
                "time_triggered": alert_result.last_run_timestamp,
            }
            response = {
                "event_type": WEBHOOK_TRIGGER_EVENTS.USAGE_ALERT_TRIGGERED,
                "payload": UsageAlertPayload(alert_data).data,
            }
            event_id = (
                str(organization.organization_id.hex)[:50]
                + "_"
                + str(usage_alert.usage_alert_id.hex)[:50]
                + "_"
                + str(subscription_record.subscription_record_id.hex)[:50]
                + "_"
                + str(alert_result.last_run_timestamp.timestamp())
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
                        "properties": response,
                    },
                ),
            )
