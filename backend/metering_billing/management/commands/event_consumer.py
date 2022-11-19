from django.conf import settings
from django.core.management.base import BaseCommand
from metering_billing.kafka.consumer import Consumer

POSTHOG_PERSON = settings.POSTHOG_PERSON
KAFKA_HOST = settings.KAFKA_HOST
KAFKA_EVENTS_TOPIC = settings.KAFKA_EVENTS_TOPIC
CONSUMER = settings.CONSUMER


class Command(BaseCommand):
    "Django command to pause execution until the database is available"

    def handle(self, *args, **options):
        consumer = Consumer()
        while True:
            consumer.consume()
