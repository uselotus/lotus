import logging
import os
from dataclasses import dataclass

import posthog
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from metering_billing.models import Customer, Event
from metering_billing.utils import now_utc

from .singleton import Singleton

POSTHOG_PERSON = settings.POSTHOG_PERSON
KAFKA_HOST = settings.KAFKA_HOST
KAFKA_EVENTS_TOPIC = settings.KAFKA_EVENTS_TOPIC
CONSUMER = settings.CONSUMER

logger = logging.getLogger("django.server")


@dataclass
class ConsumerConfig:
    bootstrap_servers = [KAFKA_HOST]
    topic = KAFKA_EVENTS_TOPIC
    auto_offset_reset = "earliest"


class Consumer(metaclass=Singleton):
    __connection = None

    def __init__(self):
        self.__connection = CONSUMER
        self.config = ConsumerConfig()
        self.topic = self.config.topic

    def consume(self):
        """Consume messages from a Redpanda topic"""
        try:
            for msg in self.__connection:
                if msg is None or msg.value is None or msg.key is None:
                    continue
                logger.info(f"Consumed record. key={msg.key}, value={msg.value}")
                try:
                    write_batch_events_to_db(
                        msg.value["events"], msg.value["organization_id"]
                    )
                except:
                    continue
        except:
            logger.info(f"Could not consume from topic: {self.topic}")
            raise


def write_batch_events_to_db(events_list, org_pk):
    ### Match Customer pk with customer_id amd fill in customer pk
    organization = org_pk
    customer_id = events_list[0]["cust_id"]
    customer_pk = Customer.objects.filter(
        organization=organization, customer_id=customer_id
    ).first()
    ##put events in correct object format
    now = now_utc()
    event_obj_list = [
        Event(**{**event, "customer": customer_pk, "inserted_at": now})
        for event in events_list
    ]
    ## check idempotency
    now_minus_45_days = now - relativedelta(days=45)
    now_minus_7_days = now - relativedelta(days=7)
    idem_ids = [x.idempotency_id for x in event_obj_list]
    repeat_idem = Event.objects.filter(
        Q(time_created__gte=now_minus_45_days) | Q(inserted_at__gte=now_minus_7_days),
        organization=organization,
        idempotency_id__in=idem_ids,
    ).exists()
    events_to_insert = []
    if repeat_idem:
        # if we have a repeat idempotency, filter thru the events and remove repeats
        for event in event_obj_list:
            event_idem_exists = Event.objects.filter(
                Q(time_created__gte=now_minus_45_days)
                | Q(inserted_at__gte=now_minus_7_days),
                organization=organization,
                idempotency_id__in=idem_ids,
            ).exists()
            if not event_idem_exists:
                events_to_insert.append(event)
    else:
        events_to_insert = event_obj_list
    ## now insert events
    events = Event.objects.bulk_create(events_to_insert)
    ## posthog + cache invalidation
    event_org_map = {}
    customer_event_name_map = {}
    for event in events:
        if event.organization not in event_org_map:
            event_org_map[event.organization] = 0
        if event.cust_id not in customer_event_name_map:
            customer_event_name_map[event.cust_id] = set()
        event_org_map[event.organization] += 1
        customer_event_name_map[event.cust_id].add(event.event_name)
    for customer_id, to_invalidate in customer_event_name_map.items():
        cache_keys_to_invalidate = []
        for event_name in to_invalidate:
            cache_keys_to_invalidate.append(
                f"customer_id:{customer_id}__event_name:{event_name}"
            )
        cache.delete_many(cache_keys_to_invalidate)
    for org, num_events in event_org_map.items():
        posthog.capture(
            POSTHOG_PERSON if POSTHOG_PERSON else org.organization_name + " (API Key)",
            event="track_event",
            properties={
                "ingested_events": num_events,
                "organization": org.organization_name,
            },
        )
