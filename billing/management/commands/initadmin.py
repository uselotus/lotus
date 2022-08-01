from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError
from ...models import User
from dotenv import load_dotenv
import os

load_dotenv()


class Command(BaseCommand):
    def handle(self, *args, **options):
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
