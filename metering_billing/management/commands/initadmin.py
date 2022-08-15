from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError
from organization.models import User, Domain, APIToken
from django.core.management import call_command
from dotenv import load_dotenv
from django.db import connection
import os

load_dotenv()


def create_local_tenant():
    if not Tenant.objects.filter(schema_name="local").exists():

        tenant = Tenant.objects.create(
            company_name="Local",
            schema_name="local",
        )
        tenant.save()
        domain = Domain.objects.create(
            tenant=tenant,
            domain="local.localhost",
            is_primary=True,
        )
        domain.save()
    else:
        tenant = Tenant.objects.get(schema_name="local")
    return tenant


class Command(BaseCommand):
    def handle(self, *args, **options):

        if not Tenant.objects.filter(schema_name="public"):
            tenant = Tenant.objects.create(
                schema_name="public",
                company_name="Lotus Public",
            )
            tenant.save()
            domain = Domain()
            domain.domain = "localhost"
            domain.tenant = tenant
            domain.is_primary = True
            domain.save()

        else:
            tenant = Tenant.objects.filter(schema_name="public").first()
            print("Public Tenant found")

        local_tenant = create_local_tenant()
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
            connection.set_tenant(local_tenant)
            print("Creating account for %s (%s)" % (username, email))
            admin = User.objects.create_superuser(
                email=email, username=username, password=password
            )
            api_token = APIToken.objects.create(
                user=admin,
                name="local_token",
            )
            api_token.save()
        else:
            print("Admin account has already been initialized.")
