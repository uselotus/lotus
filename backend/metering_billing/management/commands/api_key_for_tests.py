from django.core.management.base import BaseCommand
from metering_billing.models import Organization
from metering_billing.serializers.model_serializers import APITokenSerializer


class Command(BaseCommand):
    "Django command to execute calculate invoice"

    def handle(self, *args, **options):
        org = Organization.objects.all().first()

        _, key = APITokenSerializer().create(
            {
                "name": "test",
                "organization": org,
            }
        )

        print(key)
