import logging
import threading
from dataclasses import dataclass

import posthog
from django.conf import settings
from django.core.cache import cache
from lotus.backend.metering_billing.models import Customer, Event, Organization
from lotus.backend.metering_billing.utils import now_utc

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
    buffer = {}
    buffer_size = 0

    def __init__(self):
        self.__connection = CONSUMER
        self.config = ConsumerConfig()
        self.topic = self.config.topic
        self.buffer = {}
        self.buffer_size = 0

    def consume(self):
        """Consume messages from a Redpanda topic"""
        try:
            for msg in self.__connection:
                if msg is None or msg.value is None or msg.key is None:
                    continue

                logger.info(f"Consumed record. key={msg.key}, value={msg.value}")
                try:
                    event = msg.value["events"][0]
                    organization_pk = msg.value["organization_id"]
                    self.buffer[organization_pk] = self.buffer.get(
                        organization_pk, []
                    ).append(event)
                    self.buffer_size += 1
                    if self.buffer_size >= 100:
                        self.write_events_to_db()
                    elif self.timer is None:
                        self.timer = threading.Timer(0.250, self.write_events_to_db)
                        self.timer.start()
                except Exception:
                    continue
        except Exception:
            logger.info(f"Could not consume from topic: {self.topic}")
            raise

    def write_events_to_db(self):
        self.timer.cancel()

        if self.buffer:
            write_batch_events_to_db(self.buffer)
            self.buffer = {}
            self.buffer_size = 0

        self.timer = threading.Timer(0.250, self.write_events_to_db)


def write_batch_events_to_db(buffer):
    now = now_utc()
    for org_pk, events_list in buffer.items():
        ### Match Customer pk with customer_id amd fill in customer pk
        events_to_insert = []
        for event in events_list:
            customer_pk = cache.get(f"customer_pk_{org_pk}_{event['cust_id']}")
            if not customer_pk:
                try:
                    customer_pk = Customer.objects.get(
                        organization_id=org_pk, customer_id=event["cust_id"]
                    ).pk
                    cache.set(
                        f"customer_pk_{org_pk}_{event['cust_id']}",
                        customer_pk,
                        60 * 60 * 24,
                    )
                except Customer.DoesNotExist:
                    pass
            events_to_insert.append(
                Event(**{**event, "customer_id": customer_pk, "inserted_at": now})
            )
        ## now insert events
        events = Event.objects.bulk_create(events_to_insert, ignore_conflicts=True)
        organization_name = cache.get(f"organization_name_{org_pk}")
        if not organization_name:
            organization_name = Organization.objects.get(pk=org_pk).organization_name
            cache.set(f"organization_name_{org_pk}", organization_name, 60 * 60 * 24)
        try:
            posthog.capture(
                POSTHOG_PERSON if POSTHOG_PERSON else organization_name + " (API Key)",
                event="track_event",
                properties={
                    "ingested_events": len(events),
                    "organization": organization_name,
                },
            )
        except Exception:
            pass
