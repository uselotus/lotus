import os

from django.core.management.base import BaseCommand
from dotenv import load_dotenv

from metering_billing.models import Metric, Organization, User
from metering_billing.utils.enums import METRIC_STATUS

load_dotenv()


class Command(BaseCommand):
    def handle(self, *args, **options):
        import logging

        logger = logging.getLogger("django.server")

        username = os.getenv("ADMIN_USERNAME")
        email = os.getenv("ADMIN_EMAIL")
        password = os.getenv("ADMIN_PASSWORD")

        if not User.objects.filter(username=username).exists():
            admin = User.objects.create_superuser(
                email=email, username=username, password=password
            )

            org = Organization.objects.create(organization_name="Lotus Default")
            admin.organization = org
            admin.save()

        else:
            logger.info("Admin account has already been initialized.")

        for org in Organization.objects.all():
            org.provision_currencies()
            org.provision_subscription_filter_settings()

        for metric in Metric.objects.filter(
            status=METRIC_STATUS.ACTIVE, mat_views_provisioned=False
        ):
            metric.provision_materialized_views()

        for metric in Metric.objects.filter(
            status=METRIC_STATUS.ARCHIVED, mat_views_provisioned=True
        ):
            metric.delete_materialized_views()
