import os

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, IntervalSchedule, PeriodicTask
from dotenv import load_dotenv
from metering_billing.models import APIToken, Organization, User

load_dotenv()


class Command(BaseCommand):
    def handle(self, *args, **options):

        # Create schedules
        every_day, _ = CrontabSchedule.objects.get_or_create(
            minute="0", hour="0", day_of_week="*", day_of_month="*", month_of_year="*"
        )
        every_hour, _ = CrontabSchedule.objects.get_or_create(
            minute="0", hour="*", day_of_week="*", day_of_month="*", month_of_year="*"
        )
        every_2_minutes, _ = IntervalSchedule.objects.get_or_create(
            every=2,
            period=IntervalSchedule.MINUTES,
        )

        # create tasks
        task_qs = PeriodicTask.objects.filter(name="Check end of subscriptions")
        if len(task_qs) == 0:
            PeriodicTask.objects.create(
                name="Check end of subscriptions",
                task="metering_billing.tasks.calculate_invoice",
                crontab=every_day,
            )

        task_qs = PeriodicTask.objects.filter(name="Check start of subscriptions")
        if len(task_qs) == 0:
            PeriodicTask.objects.create(
                name="Check start of subscriptions",
                task="metering_billing.tasks.start_subscriptions",
                interval=every_2_minutes,
            )

        task_qs = PeriodicTask.objects.filter(
            name="Check Payment Intent status and update invoice"
        )
        if len(task_qs) == 0:
            PeriodicTask.objects.create(
                name="Check Payment Intent status and update invoice",
                task="metering_billing.tasks.update_invoice_status",
                crontab=every_hour,
            )

        task_qs = PeriodicTask.objects.filter(name="Check cached events and flush")
        if len(task_qs) == 0:
            PeriodicTask.objects.create(
                name="Check cached events and flush",
                task="metering_billing.tasks.check_event_cache_flushed",
                interval=every_2_minutes,
            )
