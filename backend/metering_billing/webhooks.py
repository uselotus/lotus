import logging

from django.conf import settings
from django.utils.text import slugify
from metering_billing.utils import (
    make_all_dates_times_strings,
    make_all_decimals_floats,
    now_utc,
)
from metering_billing.utils.enums import WEBHOOK_TRIGGER_EVENTS
from svix.api import MessageIn

logger = logging.getLogger("django.server")


SVIX_CONNECTOR = settings.SVIX_CONNECTOR


def customer_created_webhook(customer, customer_data=None):
    from api.serializers.model_serializers import CustomerSerializer
    from metering_billing.models import WebhookEndpoint

    if SVIX_CONNECTOR is not None:
        endpoints = (
            WebhookEndpoint.objects.prefetch_related("triggers")
            .filter(triggers__trigger_name=WEBHOOK_TRIGGER_EVENTS.CUSTOMER_CREATED)
            .distinct()
        )
        if endpoints.count() > 0:
            svix = SVIX_CONNECTOR
            now = str(now_utc())
            payload = (
                customer_data if customer_data else CustomerSerializer(customer).data
            )
            payload = make_all_decimals_floats(payload)
            payload = make_all_dates_times_strings(payload)
            response = {
                "event_type": WEBHOOK_TRIGGER_EVENTS.CUSTOMER_CREATED,
                "payload": payload,
            }
            event_id = (
                slugify(str(customer.customer_id))
                + "_"
                + slugify(str(customer.customer_name))
                + "_"
                + "created"
            )
            try:
                response = svix.message.create(
                    customer.organization.organization_id.hex,
                    MessageIn(
                        event_type=WEBHOOK_TRIGGER_EVENTS.CUSTOMER_CREATED,
                        event_id=event_id,
                        payload={
                            "attempt": 5,
                            "created_at": now,
                            "properties": response,
                        },
                    ),
                )
            except Exception as e:
                logger.error(e)


def invoice_created_webhook(invoice, organization):
    from api.serializers.model_serializers import InvoiceSerializer
    from metering_billing.models import WebhookEndpoint

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
            try:
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
            except Exception as e:
                logger.error(e)


def invoice_paid_webhook(invoice, organization):
    from api.serializers.model_serializers import InvoiceSerializer
    from metering_billing.models import WebhookEndpoint

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
            try:
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
            except Exception as e:
                logger.error(e)


def invoice_past_due_webhook(invoice, organization):
    from api.serializers.model_serializers import InvoiceSerializer
    from metering_billing.models import WebhookEndpoint

    if SVIX_CONNECTOR is not None:
        endpoints = (
            WebhookEndpoint.objects.filter(organization=organization)
            .prefetch_related("triggers")
            .filter(triggers__trigger_name=WEBHOOK_TRIGGER_EVENTS.INVOICE_PAST_DUE)
            .distinct()
        )
        if endpoints.count() > 0:
            svix = SVIX_CONNECTOR
            now = str(now_utc())
            invoice_data = InvoiceSerializer(invoice).data
            invoice_data = make_all_decimals_floats(invoice_data)
            invoice_data = make_all_dates_times_strings(invoice_data)
            response = {
                "event_type": WEBHOOK_TRIGGER_EVENTS.INVOICE_PAST_DUE,
                "payload": invoice_data,
            }
            try:
                svix.message.create(
                    organization.organization_id.hex,
                    MessageIn(
                        event_type=WEBHOOK_TRIGGER_EVENTS.INVOICE_PAST_DUE,
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
            except Exception as e:
                logger.error(e)


def subscription_created_webhook(subscription, subscription_data=None):
    from api.serializers.model_serializers import SubscriptionRecordSerializer
    from metering_billing.models import WebhookEndpoint

    if SVIX_CONNECTOR is not None:
        endpoints = (
            WebhookEndpoint.objects.prefetch_related("triggers")
            .filter(triggers__trigger_name=WEBHOOK_TRIGGER_EVENTS.SUBSCRIPTION_CREATED)
            .distinct()
        )
        if endpoints.count() > 0:
            svix = SVIX_CONNECTOR
            now = str(now_utc())
            payload = (
                subscription_data
                if subscription_data
                else SubscriptionRecordSerializer(subscription).data
            )
            payload = make_all_decimals_floats(payload)
            payload = make_all_dates_times_strings(payload)
            response = {
                "event_type": WEBHOOK_TRIGGER_EVENTS.SUBSCRIPTION_CREATED,
                "payload": payload,
            }
            event_id = (
                slugify(str(subscription.customer))
                + "_"
                + slugify(str(subscription.billing_plan))
                + "_"
                + slugify(str(subscription.subscription_record_id.hex)[:50])
                + "_"
                + "created"
            )
            try:
                svix.message.create(
                    subscription.organization.organization_id.hex,
                    MessageIn(
                        event_type=WEBHOOK_TRIGGER_EVENTS.SUBSCRIPTION_CREATED,
                        event_id=event_id,
                        payload={
                            "attempt": 5,
                            "created_at": now,
                            "properties": response,
                        },
                    ),
                )
            except Exception as e:
                logger.error(e)


def usage_alert_webhook(usage_alert, alert_result, subscription_record, organization):
    from api.serializers.model_serializers import (
        LightweightSubscriptionRecordSerializer,
        UsageAlertSerializer,
    )
    from api.serializers.webhook_serializers import UsageAlertPayload
    from metering_billing.models import WebhookEndpoint

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
            try:
                svix.message.create(
                    organization.organization_id.hex,
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
            except Exception as e:
                logger.error(e)


def subscription_cancelled_webhook(subscription, subscription_data=None):
    from api.serializers.model_serializers import SubscriptionRecordSerializer
    from metering_billing.models import WebhookEndpoint

    if SVIX_CONNECTOR is not None:
        endpoints = (
            WebhookEndpoint.objects.prefetch_related("triggers")
            .filter(
                triggers__trigger_name=WEBHOOK_TRIGGER_EVENTS.SUBSCRIPTION_CANCELLED
            )
            .distinct()
        )

        if endpoints.count() > 0:
            svix = SVIX_CONNECTOR
            now = str(now_utc())
            payload = (
                subscription_data
                if subscription_data
                else SubscriptionRecordSerializer(subscription).data
            )
            payload = make_all_decimals_floats(payload)
            payload = make_all_dates_times_strings(payload)
            response = {
                "event_type": WEBHOOK_TRIGGER_EVENTS.SUBSCRIPTION_CANCELLED,
                "payload": payload,
            }
            event_id = (
                slugify(str(subscription.customer))
                + "_"
                + slugify(str(subscription.billing_plan))
                + "_"
                + slugify(str(subscription.subscription_record_id.hex)[:50])
                + "_"
                + "cancelled"
            )
            try:
                response = svix.message.create(
                    subscription.organization.organization_id.hex,
                    MessageIn(
                        event_type=WEBHOOK_TRIGGER_EVENTS.SUBSCRIPTION_CANCELLED,
                        event_id=event_id,
                        payload={
                            "attempt": 5,
                            "created_at": now,
                            "properties": response,
                        },
                    ),
                )
            except Exception as e:
                logger.error(e)


def subscription_renewed_webhook(subscription, subscription_data=None):
    from api.serializers.model_serializers import SubscriptionRecordSerializer
    from metering_billing.models import WebhookEndpoint

    if SVIX_CONNECTOR is not None:
        endpoints = (
            WebhookEndpoint.objects.prefetch_related("triggers")
            .filter(triggers__trigger_name=WEBHOOK_TRIGGER_EVENTS.SUBSCRIPTION_RENEWED)
            .distinct()
        )
        if endpoints.count() > 0:
            svix = SVIX_CONNECTOR
            now = str(now_utc())
            payload = (
                subscription_data
                if subscription_data
                else SubscriptionRecordSerializer(subscription).data
            )
            payload = make_all_decimals_floats(payload)
            payload = make_all_dates_times_strings(payload)
            response = {
                "event_type": WEBHOOK_TRIGGER_EVENTS.SUBSCRIPTION_RENEWED,
                "payload": payload,
            }
            event_id = (
                slugify(str(subscription.customer))
                + "_"
                + slugify(str(subscription.billing_plan))
                + "_"
                + slugify(str(subscription.subscription_record_id.hex)[:50])
                + "_"
                + "created"
            )

            try:
                response = svix.message.create(
                    subscription.organization.organization_id.hex,
                    MessageIn(
                        event_type=WEBHOOK_TRIGGER_EVENTS.SUBSCRIPTION_RENEWED,
                        event_id=event_id,
                        payload={
                            "attempt": 5,
                            "created_at": now,
                            "properties": response,
                        },
                    ),
                )
            except Exception as e:
                logger.error(e)
                logger.error(e)
