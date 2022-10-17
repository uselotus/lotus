import datetime
import itertools
import os
import random
import time
import uuid
from datetime import timezone

import numpy as np
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
        try:
            Organization.objects.get(company_name="c.ai").delete()
        except:
            print("organization doesn't exist")
        fake = Faker()
        user, created = User.objects.get_or_create(username="cai", email="cai@cai.com")
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
            name=itertools.cycle(
                [
                    "Big Company 1",
                    "Big Company 2",
                    "Big Company 3",
                    "Medium Company 1",
                    "Medium Company 2",
                    "Medium Company 3",
                    "Small Company 1",
                    "Small Company 2",
                    "Small Company 3",
                ]
            ),
            customer_id=(fake.unique.ean() for _ in range(9)),
        )
        calls, sum_words, sum_compute, unique_lang, unique_subsections = baker.make(
            BillableMetric,
            organization=organization,
            event_name="generate_text",
            property_name=itertools.cycle(
                ["", "words", "compute_time", "language", "subsection"]
            ),
            aggregation_type=itertools.cycle(
                ["count", "sum", "sum", "unique", "unique"]
            ),
            metric_type="aggregation",
            _quantity=5,
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
        for bm in [
            calls,
            sum_words,
            sum_compute,
            unique_lang,
            unique_subsections,
            num_seats,
        ]:
            serializer = BillableMetricSerializer(bm)
            dict_repr = serializer.data
            dict_repr.pop("billable_metric_name")
            new_name = serializer.custom_name(dict_repr)
            bm.billable_metric_name = new_name
            bm.save()
        # SET THE BILLING PLANS
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
            billable_metric=sum_words, max_metric_units=2_000
        )
        pc2 = PlanComponent.objects.create(
            billable_metric=num_seats,
            max_metric_units=1,
        )
        free_bp.components.add(pc1, pc2)
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
            billable_metric=sum_words, max_metric_units=40_000
        )
        pc2 = PlanComponent.objects.create(
            billable_metric=num_seats,
            max_metric_units=5,
        )
        bp_40_og.components.add(pc1, pc2)
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
            billable_metric=sum_words, max_metric_units=100_000
        )
        pc2 = PlanComponent.objects.create(
            billable_metric=num_seats,
            max_metric_units=5,
        )
        bp_100_og.components.add(pc1, pc2)
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
            billable_metric=sum_words, max_metric_units=300_000
        )
        pc2 = PlanComponent.objects.create(
            billable_metric=num_seats,
            max_metric_units=5,
        )
        bp_300_og.components.add(pc1, pc2)
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
            billable_metric=sum_words, max_metric_units=40_000
        )
        pc2 = PlanComponent.objects.create(
            billable_metric=unique_lang, cost_per_batch=5
        )
        pc3 = PlanComponent.objects.create(billable_metric=num_seats, cost_per_batch=10)
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
            billable_metric=sum_words, max_metric_units=100_000
        )
        pc2 = PlanComponent.objects.create(
            billable_metric=unique_lang, cost_per_batch=5
        )
        pc3 = PlanComponent.objects.create(billable_metric=num_seats, cost_per_batch=12)
        bp_100_language_seats.components.add(pc1, pc2, pc3)
        bp_300_language_seats = BillingPlan.objects.create(
            organization=organization,
            interval="month",
            name="300K Words Plan - UB Language + Seats",
            description="300K words per month + usage based pricing on Languages and Seats",
            flat_rate=179,
            pay_in_advance=True,
            billing_plan_id="300_language_seats",
        )
        pc1 = PlanComponent.objects.create(
            billable_metric=sum_words, max_metric_units=300_000
        )
        pc2 = PlanComponent.objects.create(
            billable_metric=unique_lang, cost_per_batch=7
        )
        pc3 = PlanComponent.objects.create(
            billable_metric=num_seats,
            cost_per_batch=17,
        )
        bp_300_language_seats.components.add(pc1, pc2, pc3)
        bp_40_calls_subsections = BillingPlan.objects.create(
            organization=organization,
            interval="month",
            name="40K Words Plan - UB Calls + Subsections",
            description="40K words per month + usage based pricing on Calls and Subsections",
            flat_rate=0,
            pay_in_advance=True,
            billing_plan_id="40_calls_subsections",
        )
        pc1 = PlanComponent.objects.create(
            billable_metric=sum_words, max_metric_units=40_000
        )
        pc2 = PlanComponent.objects.create(billable_metric=calls, cost_per_batch=0.30)
        pc3 = PlanComponent.objects.create(
            billable_metric=unique_subsections,
            free_metric_units=5,
            cost_per_batch=2,
        )
        bp_40_calls_subsections.components.add(pc1, pc2, pc3)
        bp_40_calls_subsections.save()
        bp_100_calls_subsections = BillingPlan.objects.create(
            organization=organization,
            interval="month",
            name="100K Words Plan - UB Calls + Subsections",
            description="100K words per month + usage based pricing on Calls and Subsections",
            flat_rate=0,
            pay_in_advance=True,
            billing_plan_id="100_calls_subsections",
        )
        pc1 = PlanComponent.objects.create(
            billable_metric=sum_words, max_metric_units=100_000
        )
        pc2 = PlanComponent.objects.create(billable_metric=calls, cost_per_batch=0.25)
        pc3 = PlanComponent.objects.create(
            billable_metric=unique_subsections,
            free_metric_units=6,
            cost_per_batch=3,
        )
        bp_100_calls_subsections.components.add(pc1, pc2, pc3)
        bp_100_calls_subsections.save()
        bp_300_calls_subsections = BillingPlan.objects.create(
            organization=organization,
            interval="month",
            name="300K Words Plan - UB Calls + Subsections",
            description="300K words per month + usage based pricing on Calls and Subsections",
            flat_rate=0,
            pay_in_advance=True,
            billing_plan_id="300_calls_subsections",
        )
        pc1 = PlanComponent.objects.create(
            billable_metric=sum_words, max_metric_units=300_000
        )
        pc2 = PlanComponent.objects.create(billable_metric=calls, cost_per_batch=0.20)
        pc3 = PlanComponent.objects.create(
            billable_metric=unique_subsections,
            free_metric_units=7,
            cost_per_batch=4,
        )
        bp_300_calls_subsections.components.add(pc1, pc2, pc3)
        six_months_ago = (
            datetime.date.today() - relativedelta(months=6) - relativedelta(days=2)
        )
        five_months_ago = six_months_ago + relativedelta(months=1)
        four_months_ago = five_months_ago + relativedelta(months=1)
        three_months_ago = four_months_ago + relativedelta(months=1)
        two_months_ago = three_months_ago + relativedelta(months=1)
        one_month_ago = two_months_ago + relativedelta(months=1)
        for i, customer in enumerate(customer_set):
            for time in [
                six_months_ago,
                five_months_ago,
                four_months_ago,
                three_months_ago,
                two_months_ago,
                one_month_ago,
            ]:
                if i < 3:
                    plan = (
                        bp_40_og
                        if time == six_months_ago
                        else (bp_100_og if time == five_months_ago else bp_300_og)
                    )
                    languages = [
                        "en",
                        "es",
                        "fr",
                        "de",
                        "it",
                        "pt",
                        "ru",
                    ]
                    users_mean, users_sd = 4.5, 0.5
                elif i < 6:
                    plan = bp_40_og if time == six_months_ago else bp_100_og
                    languages = [
                        "en",
                        "es",
                        "fr",
                        "de",
                        "it",
                    ]
                    users_mean, users_sd = 3, 1
                else:
                    plan = (
                        free_bp
                        if time in [six_months_ago, five_months_ago]
                        else bp_40_og
                    )
                    languages = [
                        "en",
                    ]
                    users_mean, users_sd = 2, 0.75
                scale = (
                    1.4 if plan == bp_40_og else (1.12 if plan == bp_100_og else 0.95)
                )
                sub = Subscription.objects.create(
                    organization=organization,
                    customer=customer,
                    billing_plan=plan,
                    start_date=time,
                    status="ended",
                    is_new=time == six_months_ago,
                )
                word_limit = plan.components.get(
                    billable_metric=sum_words
                ).max_metric_units
                word_count = 0
                while word_count < word_limit:
                    event_words = random.gauss(350, 30)
                    if word_count + event_words > word_limit:
                        break
                    compute_time = event_words * random.gauss(0.1, 0.02)
                    language = random.choice(languages)
                    subsection = (
                        1 if plan == free_bp else np.random.exponential(scale=scale)
                    )
                    subsection = str(subsection // 1)
                    for tc in random_date(sub.start_date, sub.end_date, 1):
                        tc = tc
                    Event.objects.create(
                        organization=organization,
                        customer=customer,
                        event_name="generate_text",
                        time_created=tc,
                        idempotency_id=uuid.uuid4(),
                        properties={
                            "language": language,
                            "subsection": subsection,
                            "compute_time": compute_time,
                            "words": event_words,
                        },
                    )
                    word_count += event_words
                max_users = float(
                    plan.components.get(billable_metric=num_seats).max_metric_units
                )
                n = int(random.gauss(6, 1.5) // 1)
                print(n)
                baker.make(
                    Event,
                    organization=organization,
                    customer=customer,
                    event_name="log_num_seats",
                    properties=gaussian_users(n, users_mean, users_sd, max_users),
                    time_created=random_date(sub.start_date, sub.end_date, n),
                    idempotency_id=uuid.uuid4,
                    _quantity=n,
                )


def random_date(start, end, n):
    """Generate a random datetime between `start` and `end`"""
    for _ in range(n):
        dt = start + relativedelta(
            # Get a random amount of seconds between `start` and `end`
            seconds=random.randint(0, int((end - start).total_seconds())),
        )
        yield dt.replace(tzinfo=timezone.utc)


def gaussian_raise_issue(n):
    "Generate `n` stacktrace lengths with a gaussian distribution"
    for _ in range(n):
        yield {
            "stacktrace_len": round(random.gauss(300, 15), 0),
            "latency": round(max(random.gauss(350, 50), 0), 2),
            "project": random.choice(["project1", "project2", "project3"]),
        }


def gaussian_users(n, mean=3, sd=1, mx=None):
    "Generate `n` latencies with a gaussian distribution"
    for _ in range(n):
        qty = round(random.gauss(mean, sd), 0)
        if max is not None:
            qty = min(qty, mx)
        yield {
            "qty": max(qty, 1),
        }
