from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, IntervalSchedule, PeriodicTask
from dotenv import load_dotenv
from metering_billing.models import Customer, SubscriptionManager

load_dotenv()


class Command(BaseCommand):
    def handle(self, *args, **options):

        customers = Customer.objects.filter(subscription_manager=None)
        for customer in customers:
            customer.subscription_manager = SubscriptionManager.objects.create(
                customer=customer,
                organization=customer.organization,
            )
            customer.save()
