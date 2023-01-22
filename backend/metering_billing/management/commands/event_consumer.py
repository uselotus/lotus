from django.core.management.base import BaseCommand

from metering_billing.kafka.consumer import Consumer


class Command(BaseCommand):
    "Django command to pause execution until the database is available"

    def handle(self, *args, **options):
        consumer = Consumer()
        while True:
            consumer.consume()
