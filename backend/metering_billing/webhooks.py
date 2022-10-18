import json

import requests

from .models import Alert


def invoice_created_webhook(data, organization):

    alert_list = Alert.objects.filter(organization=organization, type="webhook").values(
        "webhook_url"
    )
    data["webhook_name"] = "invoice.created"

    for alert in alert_list:
        webhook_url = alert["webhook_url"]
        requests.post(
            webhook_url,
            data=json.dumps(data),
            headers={"Content-Type": "application/json"},
        )
