from django.core.management.base import BaseCommand

from metering_billing.demos import setup_database_demo


class Command(BaseCommand):
    "Django command to pause execution until the database is available"

    def add_arguments(self, parser):
        # Named (optional) arguments
        parser.add_argument(
            "--large",
            help="whether to use the expanded version or not",
        )
        parser.add_argument(
            "--name",
            help="name of the demo organization",
        )

    def handle(self, *args, **options):
        setup_database_demo(
            organization_name=options.get("name", "demo"),
            username=options.get("name", "demo"),
            email=options.get("name", "demo") + "@demo.com",
            password=options.get("name", "demo"),
            size=options.get("large", "small"),
        )
