from __future__ import absolute_import, unicode_literals
from webbrowser import get
from celery import shared_task
from datetime import datetime
from .models import Subscription
from .generate_invoice import generate_invoice


@shared_task
def calculate_invoice(subscription):
    ending_subscriptions = Subscription.objects.filter(
        status="active", end_date__lte=datetime.now()
    )
    for subscription in ending_subscriptions:
        # Generate the invoice
        generate_invoice(subscription)
        # Renew the subscription
        subscription.start_date = datetime.now()
        subscription.end_date = subscription.billing_plan.subscription_end_date(
            subscription.start_date
        )
        subscription.save()
