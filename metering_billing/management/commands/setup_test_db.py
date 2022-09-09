import datetime
import itertools
import os
import random
import uuid
from datetime import datetime, timedelta, timezone

from django.core.management.base import BaseCommand
from faker import Faker
from metering_billing.models import (
    BillableMetric,
    BillingPlan,
    Customer,
    Event,
    Organization,
    PlanComponent,
    Subscription,
    User,
)
from model_bakery import baker


class Command(BaseCommand):
    "Django command to pause execution until the database is available"

    def handle(self, *args, **options):
        fake = Faker()
        username = os.getenv("DJANGO_SUPERUSER_USERNAME")

        admin = User.objects.get(username=username)
        organization = admin.organization

        customer_set = baker.make(
            Customer,
            _quantity=10,
            organization=organization,
            name=lambda _: fake.unique.company(),
            customer_id=lambda _: fake.unique.ean(),
        )
        bm_e1_1, bm_e1_2 = baker.make(
            BillableMetric,
            organization=organization,
            event_name="raise_issue",
            property_name=itertools.cycle(["", "stacktrace_len"]),
            aggregation_type=itertools.cycle(["count", "sum"]),
            _quantity=2,
        )
        bm_e2_1, bm_e2_2 = baker.make(
            BillableMetric,
            organization=organization,
            event_name="send_alert",
            property_name=itertools.cycle(["", "latency"]),
            aggregation_type=itertools.cycle(["count", "max"]),
            _quantity=2,
        )
        pc1 = PlanComponent.objects.create(
            billable_metric=bm_e1_1,
            free_metric_quantity=1000,
            cost_per_metric=0.01,
            metric_amount_per_cost=5,
        )
        pc2 = PlanComponent.objects.create(
            billable_metric=bm_e1_2,
            free_metric_quantity=20_000,
            cost_per_metric=0.005,
            metric_amount_per_cost=250,
        )
        pc3 = PlanComponent.objects.create(
            billable_metric=bm_e2_1,
            free_metric_quantity=100,
            cost_per_metric=0.50,
            metric_amount_per_cost=1,
        )
        pc4 = PlanComponent.objects.create(
            billable_metric=bm_e2_2,
            free_metric_quantity=200,
            cost_per_metric=75,
            metric_amount_per_cost=100,
        )
        bp = BillingPlan.objects.create(
            organization=organization,
            interval="month",
            name="Sentry Basic Plan",
            description="Sentry Basic Plan for event ingestion and alerting",
            currency="USD",
            flat_rate=30,
            pay_in_advance=True,
            billing_plan_id="sentry-basic-plan",
        )
        bp.components.add(pc1, pc2, pc3, pc4)
        bp.save()
        old_sub_start = datetime.now() - timedelta(days=45)
        old_sub_end = datetime.now() - timedelta(days=16)
        new_sub_start = datetime.now() - timedelta(days=15)
        new_sub_end = datetime.now() + timedelta(days=14)
        for customer in customer_set:
            Subscription.objects.create(
                organization=organization,
                customer=customer,
                billing_plan=bp,
                start_date=old_sub_start.date(),
                end_date=old_sub_end.date(),
                status="ended",
            )
            Subscription.objects.create(
                organization=organization,
                customer=customer,
                billing_plan=bp,
                start_date=new_sub_start.date(),
                end_date=new_sub_end.date(),
                status="active",
            )

        for customer in customer_set:
            for start, end in [
                (old_sub_start, old_sub_end),
                (new_sub_start, new_sub_end),
            ]:
                n = int(random.gauss(10_000, 500) // 1)
                baker.make(
                    Event,
                    organization=organization,
                    customer=customer,
                    event_name="raise_issue",
                    properties=gaussian_stacktrace_len(n),
                    time_created=random_date(start, end, n),
                    idempotency_id=uuid.uuid4,
                    _quantity=n,
                )
                n = int(random.gauss(1_000, 100) // 1)
                baker.make(
                    Event,
                    organization=organization,
                    customer=customer,
                    event_name="send_alert",
                    properties=gaussian_latency(n),
                    time_created=random_date(start, end, n),
                    idempotency_id=uuid.uuid4,
                    _quantity=n,
                )


def random_date(start, end, n):
    """Generate a random datetime between `start` and `end`"""
    for _ in range(n):
        yield (
            start
            + timedelta(
                # Get a random amount of seconds between `start` and `end`
                seconds=random.randint(0, int((end - start).total_seconds())),
            )
        ).replace(tzinfo=timezone.utc)


def gaussian_stacktrace_len(n):
    "Generate `n` stacktrace lengths with a gaussian distribution"
    for _ in range(n):
        yield {"stacktrace_len": round(random.gauss(205, 15), 0)}


def gaussian_latency(n):
    "Generate `n` latencies with a gaussian distribution"
    for _ in range(n):
        yield {"latency": round(max(random.gauss(350, 50), 0), 2)}
