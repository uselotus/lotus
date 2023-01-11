from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, IntervalSchedule, PeriodicTask
from dotenv import load_dotenv

load_dotenv()


class Command(BaseCommand):
    def handle(self, *args, **options):

        # Create schedules
        every_hour, _ = IntervalSchedule.objects.get_or_create(
            every=1,
            period=IntervalSchedule.HOURS,
        )
        every_15_mins, _ = IntervalSchedule.objects.get_or_create(
            every=15,
            period=IntervalSchedule.MINUTES,
        )
        every_3_minutes, _ = IntervalSchedule.objects.get_or_create(
            every=3,
            period=IntervalSchedule.MINUTES,
        )

        # create tasks
        PeriodicTask.objects.update_or_create(
            name="Check end of subscriptions",
            task="metering_billing.tasks.calculate_invoice",
            defaults={"interval": every_hour, "crontab": None},
        )

        PeriodicTask.objects.update_or_create(
            name="Check Payment Intent status and update invoice",
            task="metering_billing.tasks.update_invoice_status",
            defaults={"interval": every_15_mins, "crontab": None},
        )

        PeriodicTask.objects.update_or_create(
            name="Run Alert Refreshes",
            task="metering_billing.tasks.refresh_alerts",
            defaults={"interval": every_3_minutes, "crontab": None},
        )
