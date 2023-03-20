from django.core.management.base import BaseCommand
from django_celery_beat.models import IntervalSchedule, PeriodicTask
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
        every_5_mins, _ = IntervalSchedule.objects.get_or_create(
            every=5,
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

        PeriodicTask.objects.update_or_create(
            name="Run Zero Out Expired Balances",
            task="metering_billing.tasks.zero_out_expired_balance_adjustments",
            defaults={"interval": every_5_mins, "crontab": None},
        )

        PeriodicTask.objects.update_or_create(
            name="Prune Guard Table",
            task="metering_billing.tasks.prune_guard_table",
            defaults={"interval": every_15_mins, "crontab": None},
        )

        PeriodicTask.objects.update_or_create(
            name="Invoices past due",
            task="metering_billing.tasks.check_past_due_invoices",
            defaults={"interval": every_15_mins, "crontab": None},
        )

        PeriodicTask.objects.update_or_create(
            name="Sync with CRM",
            task="metering_billing.tasks.sync_all_crm_integrations",
            defaults={"interval": every_hour, "crontab": None},
        )
