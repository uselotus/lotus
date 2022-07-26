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
                organization.organization_id,
                MessageIn(
                    event_type=WEBHOOK_TRIGGER_EVENTS.INVOICE_CREATED,
                    event_id=str(organization.organization_id)
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
                organization.organization_id,
                MessageIn(
                    event_type=WEBHOOK_TRIGGER_EVENTS.INVOICE_PAID,
                    event_id=str(organization.organization_id)
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
