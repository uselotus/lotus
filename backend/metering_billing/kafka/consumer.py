import logging
from dataclasses import dataclass

import posthog
import sentry_sdk
from django.conf import settings
from django.core.cache import cache
from metering_billing.models import Event, Organization
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
    buffer = {}
    buffer_size = 0

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
                    event = msg.value["events"][0]
                    organization_pk = msg.value["organization_id"]
                    write_batch_events_to_db({organization_pk: [event]})
                except Exception as e:
                    sentry_sdk.capture_exception(e)
                    logger.info(
                        f"Could not consume from topic: {self.topic}. Excpetionmessage: {e}"
                    )
                    continue
        except Exception:
            logger.info(f"Could not consume from topic: {self.topic}")
            raise


def write_batch_events_to_db(buffer):
    now = now_utc()
    for org_pk, events_list in buffer.items():
        ### Match Customer pk with customer_id amd fill in customer pk
        events_to_insert = []
        for event in events_list:
            events_to_insert.append(Event(**{**event, "inserted_at": now}))
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
