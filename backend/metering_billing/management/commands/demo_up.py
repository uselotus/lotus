from django.core.management.base import BaseCommand

from metering_billing.demos import setup_database_demo


class Command(BaseCommand):
    "Django command to pause execution until the database is available"

    def handle(self, *args, **options):
        from metering_billing.models import Organization

        # setup_demo4(
        #     organization_name="demo4",
        #     username="demo4",
        #     email="demo4@demo4.com",
        #     password="demo4",
        #     org_type=Organization.OrganizationType.INTERNAL_DEMO,
        # )
        setup_database_demo(
            organization_name="demo5",
            username="lotus-demo",
            email="demo5@demo5.com",
            password="lotus-demo-password",
            org_type=Organization.OrganizationType.INTERNAL_DEMO,
            size="small",
        )
