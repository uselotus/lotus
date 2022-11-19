"""
A basic example of a Redpanda consumer
"""
import os
from dataclasses import dataclass

from django.conf import settings
from django.core.management.base import BaseCommand
from metering_billing.demos import setup_demo_3
from metering_billing.models import Customer, Event
import posthog
from django.core.cache import cache


KAFKA_HOST = os.environ.get("KAFKA_HOST", "localhost")
EVENTS_TOPIC = os.environ.get("EVENTS_TOPIC", "events_topic")
POSTHOG_PERSON = settings.POSTHOG_PERSON


CONSUMER = settings.CONSUMER


@dataclass
class ConsumerConfig:
    bootstrap_servers = [KAFKA_HOST]
    topic = EVENTS_TOPIC
    auto_offset_reset = "earliest"


def write_batch_events_to_db(events_list):

    event_obj_list = [Event(**dict(event)) for event in events_list]
    customer_id_mappings = {}
    ### Match Customer pk with customer_id
    customer_pk = Customer.objects.filter(
        organization=event.organization, customer_id=event.cust_id
    ).first()

    for event in event_obj_list:
        event.customer = customer_id_mappings[event.cust_id]

    events = Event.objects.bulk_create(event_obj_list)
    event_org_map = {}
    customer_event_name_map = {}
    for event in events:
        if event.organization not in event_org_map:
            event_org_map[event.organization] = 0
        if event.customer.customer_id not in customer_event_name_map:
            customer_event_name_map[event.customer] = set()
        event_org_map[event.organization] += 1
        customer_event_name_map[event.customer].add(event.event_name)
    for customer_id, to_invalidate in customer_event_name_map.items():
        cache_keys_to_invalidate = []
        for event_name in to_invalidate:
            cache_keys_to_invalidate.append(
                f"customer_id:{customer_id}__event_name:{event_name}"
            )
        cache.delete_many(cache_keys_to_invalidate)
    for org, num_events in event_org_map.items():
        posthog.capture(
            POSTHOG_PERSON if POSTHOG_PERSON else org.company_name + " (API Key)",
            event="track_event",
            properties={
                "ingested_events": num_events,
                "organization": org.company_name,
            },
        )


class Consumer:
    def __init__(self, config: ConsumerConfig):
        self.client = CONSUMER
        self.topic = config.topic

    def consume(self):
        """Consume messages from a Redpanda topic"""
        try:
            for msg in self.client:
                print(f"Consumed record. key={msg.key}, value={msg.value}")
                write_batch_events_to_db(msg.value["events"])
        except:
            print(f"Could not consume from topic: {self.topic}")
            raise


class Command(BaseCommand):
    "Django command to pause execution until the database is available"

    def handle(self, *args, **options):
        config = ConsumerConfig()
        redpanda_consumer = Consumer(config)
        while True:
            redpanda_consumer.consume()
