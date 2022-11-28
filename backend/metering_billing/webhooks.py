import json

import requests
from django.conf import settings
from metering_billing.utils import now_utc
from svix.api import MessageIn, Svix

SVIX_API_KEY = settings.SVIX_API_KEY


def invoice_created_webhook(invoice_data, organization):
    from metering_billing.serializers.model_serializers import InvoiceSerializer
    if SVIX_API_KEY != "":
        now = str(now_utc())
        svix = Svix(SVIX_API_KEY)
        svix.message.create(
            organization.organization_id,
            MessageIn(
                event_type="invoice.created",
                event_id=invoice_data["invoice_id"],
                payload={
                    "attempt": 2,
                    "created_at": now,
                    "properties": invoice_data,
                },
            ),
        )
