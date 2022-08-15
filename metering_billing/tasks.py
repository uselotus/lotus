from __future__ import absolute_import, unicode_literals
from lotus.celery import app
from datetime import datetime
from metering_billing.models import Subscription
from .generate_invoice import generate_invoice


@app.task
def calculate_invoice():
    ending_subscriptions = Subscription.objects.filter(
        status="active", end_date__lte=datetime.now()
    )
    for subscription in ending_subscriptions:
        # Generate the invoice
        try:
            generate_invoice(subscription)
        except Exception as e:
            print(e)
            print("Error generating invoice for subscription {}".format(subscription))
            continue
        # Renew the subscription
        subscription.start_date = datetime.now()
        subscription.end_date = subscription.billing_plan.subscription_end_date(
            subscription.start_date
        )
        subscription.save()
