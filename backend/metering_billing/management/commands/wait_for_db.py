import time

from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    "Django command to pause execution until the database is available"

    def handle(self, *args, **options):
        "Pause execution until the database is available"

        db_connection = None
        while not db_connection:
            try:
                db_connection = connections["default"]
            except:
                time.sleep(1)
