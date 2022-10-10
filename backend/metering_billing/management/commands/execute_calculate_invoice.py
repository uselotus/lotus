import time

from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError
from metering_billing.tasks import calculate_invoice


class Command(BaseCommand):
    "Django command to execute calculate invoice"

    def handle(self, *args, **options):
        calculate_invoice()
