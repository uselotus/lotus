from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError
from tenant.models import User, Tenant, Domain, APIToken
from dotenv import load_dotenv
import os

load_dotenv()


class Command(BaseCommand):
    def handle(self, *args, **options):

        if not Tenant.objects.filter(schema_name="public"):
            print("30")
            tenant = Tenant.objects.create(
                schema_name="public",
                company_name="Lotus Public",
            )
            tenant.save()
            domain = Domain()
            domain.domain = "www.uselotus.app"
            domain.tenant = tenant
            domain.is_primary = True
            domain.save()

        else:
            tenant = Tenant.objects.filter(schema_name="public").first()
        # Add one or more domains for the tenant

        # from django_celery_beat.models import CrontabSchedule, PeriodicTask

        # schedule, _ = CrontabSchedule.objects.get_or_create(
        #     minute="1",
        #     hour="*",
        #     day_of_week="*",
        #     day_of_month="*",
        #     month_of_year="*",
        # )

        # PeriodicTask.objects.create(
        #     crontab=schedule,
        #     name="Generate Invoices",
        #     task="billing.tasks.calculate_invoice",
        # )

        username = os.getenv("DJANGO_SUPERUSER_USERNAME")
        email = os.getenv("DJANGO_SUPERUSER_EMAIL")
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD")

        if not User.objects.filter(username=username).exists():
            print("Creating account for %s (%s)" % (username, email))
            admin = User.objects.create_superuser(
                email=email, username=username, password=password
            )
        else:
            print("Admin account has already been initialized.")
