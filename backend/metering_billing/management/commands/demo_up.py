from django.core.management.base import BaseCommand
from metering_billing.demos import setup_demo3, setup_demo4, setup_paas_demo


class Command(BaseCommand):
    "Django command to pause execution until the database is available"

    def handle(self, *args, **options):
        from metering_billing.models import Organization

        setup_demo3(
            organization_name="demo3",
            username="demo3",
            email="demo3@demo3.com",
            password="demo3",
            org_type=Organization.OrganizationType.INTERNAL_DEMO,
        )
        setup_demo4(
            organization_name="demo4",
            username="demo4",
            email="demo4@demo4.com",
            password="demo4",
            org_type=Organization.OrganizationType.INTERNAL_DEMO,
        )
        setup_paas_demo(
            org_type=Organization.OrganizationType.INTERNAL_DEMO,
        )
