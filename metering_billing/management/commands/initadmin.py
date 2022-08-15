from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError
from metering_billing.models import User, Organization, APIToken
from django.core.management import call_command
from dotenv import load_dotenv
from django.db import connection
import os

load_dotenv()


class Command(BaseCommand):
    def handle(self, *args, **options):

        # try:
        #     organization = Organization.objects.get_or_create(
        #         company_name="Lotus",
        #         stripe_id="",
        #     )
        # except OperationalError:
        #     pass

        username = os.getenv("DJANGO_SUPERUSER_USERNAME")
        email = os.getenv("DJANGO_SUPERUSER_EMAIL")
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD")

        if not User.objects.filter(username=username).exists():
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
