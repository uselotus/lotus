import datetime
import itertools
import os
import random
import time
import uuid
from datetime import timezone

from dateutil.relativedelta import relativedelta
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
        username = os.getenv("ADMIN_USERNAME")
        admin = User.objects.get(username=username)
        organization = admin.organization
        customer_set = baker.make(
            Customer,
            _quantity=10,
            organization=organization,
            name=(fake.unique.company() for _ in range(10)),
            customer_id=(fake.unique.ean() for _ in range(10)),
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
            free_metric_units=500,
            cost_per_batch=0.25,
            metric_units_per_batch=5,
        )
        pc2 = PlanComponent.objects.create(
            billable_metric=bm_e1_2,
            free_metric_units=80_000,
            cost_per_batch=0.08,
            metric_units_per_batch=200,
        )
        pc3 = PlanComponent.objects.create(
            billable_metric=bm_e2_1,
            free_metric_units=100,
            cost_per_batch=1.25,
            metric_units_per_batch=1,
        )
        pc4 = PlanComponent.objects.create(
            billable_metric=bm_e2_2,
            free_metric_units=200,
            cost_per_batch=50,
            metric_units_per_batch=100,
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
        old_sub_start_date = (
            datetime.date.today() - relativedelta(months=1) - relativedelta(days=15)
        )
        old_sub_end_date = old_sub_start_date + relativedelta(months=1)
        new_sub_start_date = old_sub_end_date + relativedelta(days=1)
        new_sub_end_date = new_sub_start_date + relativedelta(months=1)
        old_sub_start_time = datetime.datetime.combine(
            old_sub_start_date, datetime.time.min, tzinfo=timezone.utc
        )
        old_sub_end_time = datetime.datetime.combine(
            old_sub_end_date, datetime.time.max, tzinfo=timezone.utc
        )
        new_sub_start_time = datetime.datetime.combine(
            new_sub_start_date, datetime.time.min, tzinfo=timezone.utc
        )
        new_sub_end_time = datetime.datetime.combine(
            new_sub_end_date, datetime.time.max, tzinfo=timezone.utc
        )
        for customer in customer_set:
            Subscription.objects.create(
                organization=organization,
                customer=customer,
                billing_plan=bp,
                start_date=old_sub_start_date,
                end_date=old_sub_end_date,
                status="ended",
            )
            Subscription.objects.create(
                organization=organization,
                customer=customer,
                billing_plan=bp,
                start_date=new_sub_start_date,
                end_date=new_sub_end_date,
                status="active",
            )

        for customer in customer_set:
            for start, end in [
                (old_sub_start_time, old_sub_end_time),
                (new_sub_start_time, new_sub_end_time),
            ]:
                n = int(random.gauss(5_000, 500) // 1)
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
            + relativedelta(
                # Get a random amount of seconds between `start` and `end`
                seconds=random.randint(0, int((end - start).total_seconds())),
            )
        ).replace(tzinfo=timezone.utc)


def gaussian_stacktrace_len(n):
    "Generate `n` stacktrace lengths with a gaussian distribution"
    for _ in range(n):
        yield {"stacktrace_len": round(random.gauss(300, 15), 0)}


def gaussian_latency(n):
    "Generate `n` latencies with a gaussian distribution"
    for _ in range(n):
        yield {"latency": round(max(random.gauss(350, 50), 0), 2)}
