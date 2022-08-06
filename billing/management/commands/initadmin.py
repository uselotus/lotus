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
            tenant = Tenant(
                schema_name="public",
                company_name="Lotus Public",
            )
            tenant.save()

        else:
            tenant = Tenant.objects.filter(schema_name="public").first()
        # Add one or more domains for the tenant
        domain = Domain()
        domain.domain = "www.uselotus.app"
        domain.tenant = tenant
        domain.is_primary = True
        domain.save()

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
