import os

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, IntervalSchedule, PeriodicTask
from dotenv import load_dotenv
from metering_billing.models import APIToken, Organization, User

load_dotenv()


class Command(BaseCommand):
    def handle(self, *args, **options):

        #Create schedules
        every_hour, _ = CrontabSchedule.objects.get_or_create(
            minute="0", hour="*", day_of_week="*", day_of_month="*", month_of_year="*"
        )
        every_2_minutes, _ = IntervalSchedule.objects.get_or_create(
            every=2,
            period=IntervalSchedule.MINUTES,
        )

        #create tasks
        task, created = PeriodicTask.objects.get_or_create(
            name="Check end of subscriptions",
            task="metering_billing.tasks.calculate_invoice",
            crontab=every_hour,
        )
        if not created:
            print(f"task {task.name} already exists")
        task, created = PeriodicTask.objects.get_or_create(
            name="Check start of subscriptions",
            task="metering_billing.tasks.start_subscriptions",
            interval=every_2_minutes,
        )
        if not created:
            print(f"task {task.name} already exists")
