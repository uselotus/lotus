from __future__ import absolute_import, unicode_literals

import datetime
from datetime import timezone

import stripe
from celery import shared_task
from django.core.cache import cache
from django.db.models import Q
from lotus.settings import (
    EVENT_CACHE_FLUSH_COUNT,
    EVENT_CACHE_FLUSH_SECONDS,
    STRIPE_SECRET_KEY,
)

from metering_billing.invoice import generate_invoice
from metering_billing.models import Event, Invoice, Subscription

stripe.api_key = STRIPE_SECRET_KEY


@shared_task
def calculate_invoice():
    now = datetime.date.today()
    ending_subscriptions = Subscription.objects.filter(
        status="active", end_date__lte=now
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
                "billing_plan": old_subscription.billing_plan,
                "start_date": old_subscription.end_date,
                "auto_renew": True,
                "is_new": False,
            }
            subscription_kwargs["end_date"] = subscription_kwargs[
                "billing_plan"
            ].subscription_end_date(subscription_kwargs["start_date"])
            if (
                subscription_kwargs["end_date"] >= now
                and subscription_kwargs["start_date"] <= now
            ):
                subscription_kwargs["status"] = "active"
            else:
                subscription_kwargs["status"] = "ended"
            Subscription.objects.create(**subscription_kwargs)


@shared_task
def start_subscriptions():
    now = datetime.datetime.now(timezone.utc).astimezone()
    starting_subscriptions = Subscription.objects.filter(
        status="not_started", start_date__lte=now
    )
    for new_subscription in starting_subscriptions:
        new_subscription.status = "active"
        new_subscription.save()


@shared_task
def update_invoice_status():
    incomplete_invoices = Invoice.objects.filter(~Q(status="succeeded"))
    for incomplete_invoice in incomplete_invoices:
        p_intent = stripe.PaymentIntent.retrieve(incomplete_invoice.payment_intent_id)
        if p_intent.status != incomplete_invoice.status:
            incomplete_invoice.status = p_intent.status
            incomplete_invoice.save()


@shared_task
def write_batch_events_to_db(events_list):
    event_obj_list = [Event(**dict(event)) for event in events_list]
    Event.objects.bulk_create(event_obj_list)


@shared_task
def check_event_cache_flushed():
    cache_tup = cache.get("events_to_insert")
    now = datetime.datetime.now(timezone.utc).astimezone()
    cached_events, last_flush_dt = cache_tup if cache_tup else (set(), now)
    time_since_last_flush = (now - last_flush_dt).total_seconds()
    if (
        len(cached_events) >= EVENT_CACHE_FLUSH_COUNT
        or time_since_last_flush >= EVENT_CACHE_FLUSH_SECONDS
    ):
        write_batch_events_to_db.delay(cached_events)
        cached_events = []
        cache.set("events_to_insert", (cached_events, now), None)
