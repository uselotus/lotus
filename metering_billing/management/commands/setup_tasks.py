import os

from django.core.management import call_command
from django.core.management.base import BaseCommand
from dotenv import load_dotenv
from django_celery_beat.models import PeriodicTask, CrontabSchedule

from metering_billing.models import APIToken, Organization, User

load_dotenv()


class Command(BaseCommand):
    def handle(self, *args, **options):

        schedule, created = CrontabSchedule.objects.get_or_create(
            minute="0", hour="0", day_of_week="*", day_of_month="*", month_of_year="*"
        )
        if created:
            task = PeriodicTask.objects.create(
                name="Check end of subscriptions",
                task="metering_billing.tasks.calculate_invoice",
                crontab=schedule,
            )
            task.save()
