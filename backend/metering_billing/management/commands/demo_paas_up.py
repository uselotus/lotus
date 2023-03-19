from django.core.management.base import BaseCommand
from metering_billing.demos import setup_paas_demo


class Command(BaseCommand):
    "Django command to pause execution until the database is available"

    def handle(self, *args, **options):
        from metering_billing.models import Organization

        setup_paas_demo(
            org_type=Organization.OrganizationType.INTERNAL_DEMO,
        )
