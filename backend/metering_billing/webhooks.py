import json
import requests
from svix.api import Svix, MessageIn
from django.conf import settings
from metering_billing.utils import (
    now_utc,
)


SVIX_SECRET = settings.SVIX_SECRET


def invoice_created_webhook(invoice, organization):
    if SVIX_SECRET != "":
        now = now_utc()
        svix = Svix("AUTH_TOKEN")
        svix.message.create(
            organization.organization_id,
            MessageIn(
                event_type="invoice.created",
                event_id=invoice.invoice_id,
                payload={
                    "attempt": 2,
                    "created_at": now,
                    "properties": invoice,
                },
            ),
        )
