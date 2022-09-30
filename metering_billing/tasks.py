from __future__ import absolute_import, unicode_literals

import datetime
from datetime import timezone

import posthog
import stripe
from celery import shared_task
from dateutil.relativedelta import relativedelta
from django.core.cache import cache
from django.db.models import Q
from lotus.settings import (
    EVENT_CACHE_FLUSH_COUNT,
    EVENT_CACHE_FLUSH_SECONDS,
    STRIPE_SECRET_KEY,
)

from metering_billing.invoice import generate_invoice
from metering_billing.models import Event, Invoice, Organization, Subscription
from metering_billing.views.views import import_stripe_customers

stripe.api_key = STRIPE_SECRET_KEY


@shared_task
def calculate_invoice():
    # get ending subs
    now = datetime.date.today()
    ending_subscriptions = list(
        Subscription.objects.filter(status="active", end_date__lt=now)
    )
    invoice_sub_uids_seen = Invoice.values_list("subscription__subscription_uid", flat=True)
    ended_subs_no_invoice = Subscription.objects.filter(status="ended", end_date__lt=now).exclude(subscription_uid__in=invoice_sub_uids_seen)
    ending_subscriptions.extend(ended_subs_no_invoice)

    # prefetch organization customer stripe keys
    orgs_seen = set()
    for sub in ending_subscriptions:
        org_pk = sub.organization.pk
        if org_pk not in orgs_seen:
            orgs_seen.add(org_pk)
            import_stripe_customers(sub.organization)
    # now generate invoices and new subs
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
        # End the old subscription and delete draft invoices
        old_subscription.status = "ended"
        old_subscription.save()
        now = datetime.datetime.now(timezone.utc).date()
        Invoice.objects.filter(issue_date__lt=now, status="draft").delete()
        # Renew the subscription
        if old_subscription.auto_renew:
            subscription_kwargs = {
                "organization": old_subscription.organization,
                "customer": old_subscription.customer,
                "billing_plan": old_subscription.billing_plan,
                "start_date": old_subscription.end_date + relativedelta(days=+1),
                "auto_renew": True,
                "is_new": False,
            }
            sub = Subscription.objects.create(**subscription_kwargs)
            if sub.end_date >= now and sub.start_date <= now:
                sub.status = "active"
            else:
                sub.status = "ended"
            sub.save()


@shared_task
def start_subscriptions():
    now = datetime.date.today()
    starting_subscriptions = Subscription.objects.filter(
        status="not_started", start_date__lte=now
    )
    for new_subscription in starting_subscriptions:
        new_subscription.status = "active"
        new_subscription.save()


@shared_task
def update_invoice_status():
    incomplete_invoices = Invoice.objects.filter(
        ~Q(status="succeeded") & ~Q(status="draft")
    )
    for incomplete_invoice in incomplete_invoices:
        pi_id = incomplete_invoice.payment_intent_id
        if pi_id is not None:
            try:
                pi = stripe.PaymentIntent.retrieve(pi_id)
            except Exception as e:
                print(e)
                print("Error retrieving payment intent {}".format(pi_id))
                continue
            if pi.status != incomplete_invoice.status:
                incomplete_invoice.status = pi.status
                incomplete_invoice.save()


@shared_task
def write_batch_events_to_db(events_list):
    event_obj_list = [Event(**dict(event)) for event in events_list]
    Event.objects.bulk_create(event_obj_list)


@shared_task
def posthog_capture_track(organization_pk, len_sent_events, len_ingested_events):
    org = Organization.objects.get(pk=organization_pk)
    posthog.capture(
        org.company_name,
        "track_event",
        {"sent_events": len_sent_events, "ingested_events": len_ingested_events},
    )


@shared_task
def check_event_cache_flushed():
    cache_tup = cache.get("events_to_insert")
    now = datetime.datetime.now(timezone.utc).astimezone()
    cached_events, cached_idems, last_flush_dt = (
        cache_tup if cache_tup else ([], set(), now)
    )
    time_since_last_flush = (now - last_flush_dt).total_seconds()
    if (
        len(cached_events) >= EVENT_CACHE_FLUSH_COUNT
        or time_since_last_flush >= EVENT_CACHE_FLUSH_SECONDS
    ):
        write_batch_events_to_db.delay(cached_events)
        cached_events = []
        cached_idems = set()
        cache.set("events_to_insert", (cached_events, cached_idems, now), None)
