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
            username="cai", email="cai@cai.com"
        )
        if created:
            user.set_password("password")
            user.save()
        if user.organization is None:
            organization, _ = Organization.objects.get_or_create(company_name="c.ai")
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
        calls, sum_words, sum_compute, unique_lang, unique_subsections = baker.make(
            BillableMetric,
            organization=organization,
            event_name="generate_text",
            property_name=itertools.cycle(
                ["", "words", "compute_time", "language", "subsections"]
            ),
            aggregation_type=itertools.cycle(["count", "sum", "sum", "unique", "unique"]),
            metric_type="aggregation",
            _quantity=4,
        )
        (num_seats,) = baker.make(
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
        for bm in [calls, sum_words, sum_compute, unique_lang, unique_subsections, num_seats]:
            serializer = BillableMetricSerializer(bm)
            dict_repr = serializer.data
            dict_repr.pop("billable_metric_name")
            new_name = serializer.custom_name(dict_repr)
            bm.billable_metric_name = new_name
            bm.save()
        #SET THE BILLING PLANS
        free_bp = BillingPlan.objects.create(
            organization=organization,
            interval="month",
            name="Free Plan",
            description="The free tier",
            flat_rate=0,
            pay_in_advance=True,
            billing_plan_id="free",
        )
        pc1 = PlanComponent.objects.create(
            billable_metric=sum_words,
            max_metric_units=2_000
        )
        free_bp.components.add(pc1)
        free_bp.save()
        bp_40_og = BillingPlan.objects.create(
            organization=organization,
            interval="month",
            name="40K Words Plan",
            description="40K words per month",
            flat_rate=49,
            pay_in_advance=True,
            billing_plan_id="40_og",
        )
        pc1 = PlanComponent.objects.create(
            billable_metric=sum_words,
            max_metric_units=40_000
        )
        bp_40_og.components.add(pc1)
        bp_40_og.save()
        bp_100_og = BillingPlan.objects.create(
            organization=organization,
            interval="month",
            name="100K Words Plan",
            description="100K words per month",
            flat_rate=99,
            pay_in_advance=True,
            billing_plan_id="100_og",
        )
        pc1 = PlanComponent.objects.create(
            billable_metric=sum_words,
            max_metric_units=100_000
        )
        bp_100_og.components.add(pc1)
        bp_100_og.save()
        bp_300_og = BillingPlan.objects.create(
            organization=organization,
            interval="month",
            name="300K Words Plan",
            description="300K words per month",
            flat_rate=279,
            pay_in_advance=True,
            billing_plan_id="300_og",
        )
        pc1 = PlanComponent.objects.create(
            billable_metric=sum_words,
            max_metric_units=300_000
        )
        bp_300_og.components.add(pc1)
        bp_300_og.save()
        bp_40_language_seats = BillingPlan.objects.create(
            organization=organization,
            interval="month",
            name="40K Words Plan - UB Language + Seats",
            description="40K words per month + usage based pricing on Languages and Seats",
            flat_rate=19,
            pay_in_advance=True,
            billing_plan_id="40_language_seats",
        )
        pc1 = PlanComponent.objects.create(
            billable_metric=sum_words,
            max_metric_units=40_000
        )
        pc2 = PlanComponent.objects.create(
            billable_metric=unique_lang,
            cost_per_batch=5
        )
        pc3 = PlanComponent.objects.create(
            billable_metric=num_seats,
            cost_per_batch=10
        )
        bp_40_language_seats.components.add(pc1, pc2, pc3)
        bp_40_language_seats.save()
        bp_100_language_seats = BillingPlan.objects.create(
            organization=organization,
            interval="month",
            name="100K Words Plan - UB Language + Seats",
            description="100K words per month + usage based pricing on Languages and Seats",
            flat_rate=59,
            pay_in_advance=True,
            billing_plan_id="100_language_seats",
        )
        pc1 = PlanComponent.objects.create(
            billable_metric=sum_words,
            max_metric_units=100_000
        )
        pc2 = PlanComponent.objects.create(
            billable_metric=unique_lang,
            cost_per_batch=5
        )
        pc3 = PlanComponent.objects.create(
            billable_metric=num_seats,
            cost_per_batch=10
        )
        bp_300_language_seats = BillingPlan.objects.create(
            organization=organization,
            interval="month",
            name="300K Words Plan - UB Language + Seats",
            description="300K words per month + usage based pricing on Languages and Seats",
            flat_rate=179,
            pay_in_advance=True,
            billing_plan_id="300_language_seats",
        )
        bp_40_calls_subsections = BillingPlan.objects.create(
            organization=organization,
            interval="month",
            name="40K Words Plan - UB Calls + Subsections",
            description="40K words per month + usage based pricing on Calls and Subsections",
            flat_rate=0,
            pay_in_advance=True,
            billing_plan_id="40_calls_subsections",
        )
        bp_100_calls_subsections = BillingPlan.objects.create(
            organization=organization,
            interval="month",
            name="100K Words Plan - UB Calls + Subsections",
            description="100K words per month + usage based pricing on Calls and Subsections",
            flat_rate=0,
            pay_in_advance=True,
            billing_plan_id="100_calls_subsections",
        )
        bp_300_calls_subsections = BillingPlan.objects.create(
            organization=organization,
            interval="month",
            name="300K Words Plan - UB Calls + Subsections",
            description="300K words per month + usage based pricing on Calls and Subsections",
            flat_rate=0,
            pay_in_advance=True,
            billing_plan_id="300_calls_subsections",
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
