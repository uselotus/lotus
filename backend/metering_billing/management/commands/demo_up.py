from django.core.management.base import BaseCommand

from metering_billing.demos import setup_database_demo


class Command(BaseCommand):
    "Django command to pause execution until the database is available"

    def add_arguments(self, parser):
        # Named (optional) arguments
        parser.add_argument(
            "--size",
            help="whether to use the expanded version or not",
        )
        parser.add_argument(
            "--name",
            help="name of the demo organization",
        )

    def handle(self, *args, **options):
        from metering_billing.models import Organization

        size = options.get("size")
        if size is None:
            size = "small"
        elif size not in ("small", "large"):
            raise ValueError("Invalid size: %s" % size)
        name = options.get("name") or "demo"
        setup_database_demo(
            organization_name=name,
            username=name,
            email=name + "@demo.com",
            password=name,
            size=size,
            org_type=Organization.OrganizationType.INTERNAL_DEMO,
        )
