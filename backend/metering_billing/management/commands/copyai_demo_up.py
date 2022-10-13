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
from metering_billing.serializers.model_serializers import BillableMetricSerializer
from model_bakery import baker


class Command(BaseCommand):
    "Django command to pause execution until the database is available"

    def handle(self, *args, **options):
        fake = Faker()
        user, created = User.objects.get_or_create(
            username="copyai", email="copyai@copyai.com"
        )
        if created:
            user.set_password("password")
            user.save()
        if user.organization is None:
            organization, _ = Organization.objects.get_or_create(company_name="copy.ai")
            user.organization = organization
            user.save()
        organization = user.organization
        customer_set = baker.make(
            Customer,
            _quantity=9,
            organization=organization,
            name=[
                "Big Company 1",
                "Bug Company 2",
                "Big Company 3",
                "Medium Company 1",
                "Medium Company 2",
                "Medium Company 3",
                "Small Company 1",
                "Small Company 2",
                "Small Company 3",
            ],
            customer_id=(fake.unique.ean() for _ in range(9)),
        )
        bm_e1_1, bm_e1_2, bm_e1_3, bm_e1_4 = baker.make(
            BillableMetric,
            organization=organization,
            event_name="generate_text",
            property_name=itertools.cycle(
                ["", "words", "compute_time", "language", "subsections"]
            ),
            aggregation_type=itertools.cycle(["count", "sum", "sum", "unique", "sum"]),
            metric_type="aggregation",
            _quantity=4,
        )
        (bm_e2_1,) = baker.make(
            BillableMetric,
            organization=organization,
            event_name="log_num_seats",
            property_name=itertools.cycle(
                [
                    "qty",
                ]
            ),
            aggregation_type=itertools.cycle(["max"]),
            metric_type="stateful",
            _quantity=1,
        )
        for bm in [bm_e1_1, bm_e1_2, bm_e1_3, bm_e1_4, bm_e2_1]:
            serializer = BillableMetricSerializer(bm)
            dict_repr = serializer.data
            dict_repr.pop("billable_metric_name")
            new_name = serializer.custom_name(dict_repr)
            bm.billable_metric_name = new_name
            bm.save()
        # LETS DEFINE PCs!!!
        pc1 = PlanComponent.objects.create(
            billable_metric=bm_e1_1,
            free_metric_units=500,
            cost_per_batch=0.75,
            metric_units_per_batch=10,
        )
        pc2 = PlanComponent.objects.create(
            billable_metric=bm_e1_2,
            free_metric_units=250_000,
            cost_per_batch=0.60,
            metric_units_per_batch=10000,
        )
        pc3 = PlanComponent.objects.create(
            billable_metric=bm_e1_3,
            free_metric_units=200,
            cost_per_batch=22.50,
            metric_units_per_batch=50,
        )
        pc4 = PlanComponent.objects.create(
            billable_metric=bm_e1_4,
            free_metric_units=1,
            cost_per_batch=15,
            metric_units_per_batch=1,
        )
        pc5 = PlanComponent.objects.create(
            billable_metric=bm_e2_1,
            free_metric_units=3,
            cost_per_batch=100,
            metric_units_per_batch=1,
        )
        bp = BillingPlan.objects.create(
            organization=organization,
            interval="month",
            name="Sentry Basic Plan",
            description="Sentry Basic Plan for event ingestion and alerting",
            flat_rate=200,
            pay_in_advance=True,
            billing_plan_id="sentry-basic-plan",
        )
        bp.components.add(pc1, pc2, pc3, pc4, pc5)
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
                is_new=True,
            )
            Subscription.objects.create(
                organization=organization,
                customer=customer,
                billing_plan=bp,
                start_date=new_sub_start_date,
                end_date=new_sub_end_date,
                status="active",
                is_new=False,
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
                    properties=gaussian_raise_issue(n),
                    time_created=random_date(start, end, n),
                    idempotency_id=uuid.uuid4,
                    _quantity=n,
                )
                n = int(random.gauss(6, 1.5) // 1)
                baker.make(
                    Event,
                    organization=organization,
                    customer=customer,
                    event_name="log_num_users",
                    properties=gaussian_users(n),
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


def gaussian_raise_issue(n):
    "Generate `n` stacktrace lengths with a gaussian distribution"
    for _ in range(n):
        yield {
            "stacktrace_len": round(random.gauss(300, 15), 0),
            "latency": round(max(random.gauss(350, 50), 0), 2),
            "project": random.choice(["project1", "project2", "project3"]),
        }


def gaussian_users(n):
    "Generate `n` latencies with a gaussian distribution"
    for _ in range(n):
        yield {
            "qty": round(random.gauss(3, 1), 0),
        }
