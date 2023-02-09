from django.core.management.base import BaseCommand

from metering_billing.demos import setup_demo3
from metering_billing.models import Organization, Plan


class Command(BaseCommand):
    "Django command to execute calculate invoice"

    def handle(self, *args, **options):
        setup_demo3(
            organization_name="demo3",
            username="demo3",
            email="demo3@demo3.com",
            password="demo3",
            org_type=Organization.OrganizationType.INTERNAL_DEMO,
        )

        plan = Plan.objects.all().first()
        print(plan.plan_id)
