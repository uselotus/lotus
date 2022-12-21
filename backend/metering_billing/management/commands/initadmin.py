import os

from django.core.management.base import BaseCommand
from dotenv import load_dotenv
from metering_billing.models import Organization, PricingUnit, User
from metering_billing.utils.enums.enums import SUPPORTED_CURRENCIES

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

            org = Organization.objects.create(company_name="Lotus Default")
            admin.organization = org
            admin.save()

        else:
            logger.info("Admin account has already been initialized.")

        for org in Organization.objects.all():
            org.provision_currencies()
