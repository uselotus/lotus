from django.core.management.base import BaseCommand
from metering_billing.demos import setup_demo_3


class Command(BaseCommand):
    "Django command to pause execution until the database is available"

    def handle(self, *args, **options):
        setup_demo_3(
            company_name="demo3",
            username="demo3",
            email="demo3@demo3.com",
            password="demo3",
        )
