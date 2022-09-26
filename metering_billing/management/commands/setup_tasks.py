import os

from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, IntervalSchedule, PeriodicTask
from dotenv import load_dotenv
from metering_billing.models import APIToken, Organization, User

load_dotenv()


class Command(BaseCommand):
    def handle(self, *args, **options):

        # Create schedules
        every_day_at_6_am, _ = CrontabSchedule.objects.get_or_create(
            minute="0", hour="6", day_of_week="*", day_of_month="*", month_of_year="*"
        )
        every_hour, _ = IntervalSchedule.objects.get_or_create(
            every=1,
            period=IntervalSchedule.HOURS,
        )
        every_3_minutes, _ = IntervalSchedule.objects.get_or_create(
            every=3,
            period=IntervalSchedule.MINUTES,
        )

        # create tasks
        PeriodicTask.objects.update_or_create(
            name="Check end of subscriptions",
            task="metering_billing.tasks.calculate_invoice",
            defaults={"crontab": every_day_at_6_am},
        )

        PeriodicTask.objects.update_or_create(
            name="Check start of subscriptions",
            task="metering_billing.tasks.start_subscriptions",
            defaults={"interval": every_hour, "crontab": None},
        )

        PeriodicTask.objects.update_or_create(
            name="Check Payment Intent status and update invoice",
            task="metering_billing.tasks.update_invoice_status",
            defaults={"interval": every_hour, "crontab": None},
        )

        PeriodicTask.objects.update_or_create(
            name="Check cached events and flush",
            task="metering_billing.tasks.check_event_cache_flushed",
            defaults={"interval": every_3_minutes, "crontab": None},
        )
