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
    POSTHOG_PERSON,
    STRIPE_SECRET_KEY,
)

from metering_billing.invoice import generate_invoice
from metering_billing.models import Event, Invoice, Organization, Subscription
from metering_billing.utils import INVOICE_STATUS_TYPES, SUB_STATUS_TYPES

stripe.api_key = STRIPE_SECRET_KEY


@shared_task
def calculate_invoice():
    # get ending subs
    now = datetime.date.today()
    ending_subscriptions = list(
        Subscription.objects.filter(status=SUB_STATUS_TYPES.ACTIVE, end_date__lt=now)
    )
    invoice_sub_ids_seen = Invoice.objects.filter(
        ~Q(payment_status=INVOICE_STATUS_TYPES.DRAFT)
    ).values_list("subscription__subscription_id", flat=True)

    if len(invoice_sub_ids_seen) > 0:
        ended_subs_no_invoice = Subscription.objects.filter(
            status=SUB_STATUS_TYPES.ENDED, end_date__lt=now
        ).exclude(subscription_id__in=list(invoice_sub_ids_seen))
        ending_subscriptions.extend(ended_subs_no_invoice)

    # prefetch organization customer stripe keys
    # orgs_seen = set()
    # for sub in ending_subscriptions:
    #     org_pk = sub.organization.pk
    #     if org_pk not in orgs_seen:
    #         orgs_seen.add(org_pk)
    #         import_stripe_customers(sub.organization)
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
        already_ended = old_subscription.status == SUB_STATUS_TYPES.ENDED
        old_subscription.status = SUB_STATUS_TYPES.ENDED
        old_subscription.save()
        now = datetime.datetime.now(timezone.utc).date()
        Invoice.objects.filter(
            issue_date__lt=now, payment_status=INVOICE_STATUS_TYPES.DRAFT
        ).delete()
        # Renew the subscription
        if old_subscription.auto_renew and not already_ended:
            if old_subscription.auto_renew_billing_plan:
                new_bp = old_subscription.auto_renew_billing_plan
            else:
                new_bp = old_subscription.billing_plan
            # if we'e scheduled this plan for deletion, check if its still active in subs
            # otherwise just renew with the new plan
            if new_bp.scheduled_for_deletion:
                replacement_bp = new_bp.replacement_billing_plan
                num_with_bp = Subscription.objects.filter(
                    status=SUB_STATUS_TYPES.ACTIVE, billing_plan=new_bp
                ).count()
                if num_with_bp == 0:
                    new_bp.delete()
                new_bp = replacement_bp
            subscription_kwargs = {
                "organization": old_subscription.organization,
                "customer": old_subscription.customer,
                "billing_plan": new_bp,
                "start_date": old_subscription.end_date + relativedelta(days=+1),
                "auto_renew": True,
                "is_new": False,
            }
            sub = Subscription.objects.create(**subscription_kwargs)
            if new_bp.pay_in_advance:
                sub.flat_fee_already_billed = new_bp.flat_rate
            if sub.start_date <= now <= sub.end_date:
                sub.status = SUB_STATUS_TYPES.ACTIVE
            else:
                sub.status = SUB_STATUS_TYPES.ENDED
            sub.save()


@shared_task
def start_subscriptions():
    now = datetime.date.today()
    starting_subscriptions = Subscription.objects.filter(
        status=SUB_STATUS_TYPES.NOT_STARTED, start_date__lte=now
    )
    for new_subscription in starting_subscriptions:
        new_subscription.status = SUB_STATUS_TYPES.ACTIVE
        new_subscription.save()


@shared_task
def update_invoice_status():
    incomplete_invoices = Invoice.objects.filter(
        Q(payment_status=INVOICE_STATUS_TYPES.UNPAID)
    )
    for incomplete_invoice in incomplete_invoices:
        pi_id = incomplete_invoice.external_payment_obj_id
        if pi_id is not None:
            try:
                pi = stripe.PaymentIntent.retrieve(pi_id)
            except Exception as e:
                print(e)
                print("Error retrieving payment intent {}".format(pi_id))
                continue
            if pi.status == "succeeded":
                incomplete_invoice.payment_status = INVOICE_STATUS_TYPES.PAID
                incomplete_invoice.save()
                posthog.capture(
                    POSTHOG_PERSON
                    if POSTHOG_PERSON
                    else incomplete_invoice.organization["company_name"],
                    "invoice_status_succeeded",
                )


@shared_task
def write_batch_events_to_db(events_list):
    event_obj_list = [Event(**dict(event)) for event in events_list]
    Event.objects.bulk_create(event_obj_list)


@shared_task
def posthog_capture_track(organization_pk, len_sent_events, len_ingested_events):
    org = Organization.objects.get(pk=organization_pk)
    posthog.capture(
        POSTHOG_PERSON if POSTHOG_PERSON else org.company_name,
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
