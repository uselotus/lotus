from __future__ import absolute_import, unicode_literals

from datetime import datetime

import stripe
from celery import shared_task
from django.db.models import Q
from lotus.settings import STRIPE_SECRET_KEY

from metering_billing.invoice import generate_invoice
from metering_billing.models import Invoice, Subscription

stripe.api_key = STRIPE_SECRET_KEY



@shared_task
def calculate_invoice():
    ending_subscriptions = Subscription.objects.filter(
        status="active", end_date__lte=datetime.now().date()
    )
    for old_subscription in ending_subscriptions:
        # Generate the invoice
        try:
            generate_invoice(old_subscription)
        except Exception as e:
            print(e)
            print(
                "Error generating invoice for subscription {}".format(old_subscription)
            )
            continue
        # End the old subscription
        old_subscription.status = "ended"
        old_subscription.save()
        # Renew the subscription
        if old_subscription.auto_renew:
            subscription_kwargs = {
                "organization": old_subscription.organization,
                "customer": old_subscription.customer,
                "billing_plan": old_subscription.next_plan,
                "start_date": old_subscription.end_date,
                "auto_renew": True,
                "is_new": False,
            }
            subscription_kwargs["end_date"] = subscription_kwargs[
                "billing_plan"
            ].subscription_end_date(subscription_kwargs["start_date"])
            if (
                subscription_kwargs["end_date"] >= datetime.now().date()
                and subscription_kwargs["start_date"] <= datetime.now().date()
            ):
                subscription_kwargs["status"] = "active"
            else:
                subscription_kwargs["status"] = "ended"
            Subscription.objects.create(**subscription_kwargs)


@shared_task
def start_subscriptions():
    starting_subscriptions = Subscription.objects.filter(
        status="not_started", start_date__lte=datetime.now().astimezone()
    )
    for new_subscription in starting_subscriptions:
        new_subscription.status = "active"
        new_subscription.save()


@shared_task
def update_invoice_status():
    incomplete_invoices = Invoice.objects.filter(~Q(status="succeeded"))
    for incomplete_invoice in incomplete_invoices:
        p_intent = stripe.PaymentIntent.retrieve(
            "pi_1DsTgI2eZvKYlo2CAd7R4A03",
        )
        if p_intent.status != incomplete_invoice.status:
            incomplete_invoice.status = p_intent.status
            incomplete_invoice.save()
