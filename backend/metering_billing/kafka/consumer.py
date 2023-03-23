import logging
from dataclasses import dataclass

import sentry_sdk
from django.conf import settings

from metering_billing.models import Event
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
                    event = msg.value["event"]
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
            event["cust_id"] = event.pop("customer_id")
            events_to_insert.append(Event(**{**event, "inserted_at": now}))
        ## now insert events
        Event.objects.bulk_create(events_to_insert, ignore_conflicts=True)
