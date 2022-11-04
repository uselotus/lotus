import datetime
import itertools
import random
import uuid

import numpy as np
import pytz
from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from faker import Faker
from metering_billing.models import (
    BillableMetric,
    Customer,
    Event,
    Organization,
    Plan,
    PlanComponent,
    PlanVersion,
    Subscription,
    User,
)
from metering_billing.utils import date_as_max_dt, date_as_min_dt, now_utc
from metering_billing.utils.enums import (
    FLAT_FEE_BILLING_TYPE,
    PLAN_DURATION,
    PLAN_STATUS,
    PLAN_VERSION_STATUS,
    SUBSCRIPTION_STATUS,
)
from model_bakery import baker


class Command(BaseCommand):
    "Django command to pause execution until the database is available"

    def handle(self, *args, **options):
        try:
            Organization.objects.get(company_name="demo2").delete()
        except Organization.DoesNotExist:
            print("organization doesn't exist")
        user, created = User.objects.get_or_create(
            username="demo2", email="demo2@demo2.com"
        )
        if created:
            user.set_password("demo2")
            user.save()
        if user.organization is None:
            organization, _ = Organization.objects.get_or_create(company_name="demo2")
            user.organization = organization
            user.save()
        organization = user.organization
        big_customers = []
        for _ in range(10):
            customer = Customer.objects.create(
                organization=organization,
                customer_name="BigComp" + str(uuid.uuid4())[:6],
            )
            big_customers.append(customer)
        medium_customers = []
        for _ in range(25):
            customer = Customer.objects.create(
                organization=organization,
                customer_name="MediumCompany" + str(uuid.uuid4())[:6],
            )
            medium_customers.append(customer)
        small_customers = []
        for _ in range(75):
            customer = Customer.objects.create(
                organization=organization,
                customer_name="SmallCompany" + str(uuid.uuid4())[:6],
            )
            small_customers.append(customer)
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
            billable_metric_name=itertools.cycle(
                [
                    "API Calls",
                    "Words",
                    "Compute Time",
                    "Unique Languages",
                    "Content Types",
                ]
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
            billable_metric_name="User Seats",
            _quantity=1,
        )
        # SET THE BILLING PLANS
        plan = Plan.objects.create(
            plan_name="Free Plan",
            organization=organization,
            plan_duration=PLAN_DURATION.MONTHLY,
            status=PLAN_STATUS.ACTIVE,
        )
        free_bp = PlanVersion.objects.create(
            organization=organization,
            description="The free tier",
            version=1,
            flat_fee_billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
            plan=plan,
            status=PLAN_VERSION_STATUS.ACTIVE,
            flat_rate=0,
            version_id="free",
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
        plan = Plan.objects.create(
            plan_name="40K Words Plan",
            organization=organization,
            plan_duration=PLAN_DURATION.MONTHLY,
            status=PLAN_STATUS.ACTIVE,
        )
        bp_40_og = PlanVersion.objects.create(
            organization=organization,
            description="40K Words Plan",
            version=1,
            flat_fee_billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
            plan=plan,
            status=PLAN_VERSION_STATUS.ACTIVE,
            flat_rate=49,
            version_id="40_og",
        )
        pc1 = PlanComponent.objects.create(
            billable_metric=sum_words,
            max_metric_units=40_000,
        )
        pc2 = PlanComponent.objects.create(
            billable_metric=num_seats,
            max_metric_units=5,
        )
        bp_40_og.components.add(pc1, pc2)
        bp_40_og.save()
        plan = Plan.objects.create(
            plan_name="100K Words Plan",
            organization=organization,
            plan_duration=PLAN_DURATION.MONTHLY,
            status=PLAN_STATUS.ACTIVE,
        )
        bp_100_og = PlanVersion.objects.create(
            organization=organization,
            description="100K words per month",
            version=1,
            flat_fee_billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
            plan=plan,
            status=PLAN_VERSION_STATUS.ACTIVE,
            flat_rate=99,
            version_id="100_og",
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
        plan = Plan.objects.create(
            plan_name="300K Words Plan",
            organization=organization,
            plan_duration=PLAN_DURATION.MONTHLY,
            status=PLAN_STATUS.ACTIVE,
        )
        bp_300_og = PlanVersion.objects.create(
            organization=organization,
            description="300K words per month",
            version=1,
            flat_fee_billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
            plan=plan,
            status=PLAN_VERSION_STATUS.ACTIVE,
            flat_rate=279,
            version_id="300_og",
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
        plan = Plan.objects.create(
            plan_name="40K Words Plan - UB Language + Seats",
            organization=organization,
            plan_duration=PLAN_DURATION.MONTHLY,
            status=PLAN_STATUS.ACTIVE,
        )
        bp_40_language_seats = PlanVersion.objects.create(
            organization=organization,
            description="40K words per month + usage based pricing on Languages and Seats",
            version=1,
            flat_fee_billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
            plan=plan,
            status=PLAN_VERSION_STATUS.ACTIVE,
            flat_rate=19,
            version_id="40_language_seats",
        )
        pc1 = PlanComponent.objects.create(
            billable_metric=sum_words, max_metric_units=40_000
        )
        pc2 = PlanComponent.objects.create(
            billable_metric=unique_lang,
            cost_per_batch=7,
            metric_units_per_batch=1,
            free_metric_units=0,
        )
        pc3 = PlanComponent.objects.create(
            billable_metric=num_seats,
            cost_per_batch=10,
            metric_units_per_batch=1,
            free_metric_units=0,
        )
        bp_40_language_seats.components.add(pc1, pc2, pc3)
        bp_40_language_seats.save()
        plan = Plan.objects.create(
            plan_name="100K Words Plan - UB Language + Seats",
            organization=organization,
            plan_duration=PLAN_DURATION.MONTHLY,
            status=PLAN_STATUS.ACTIVE,
        )
        bp_100_language_seats = PlanVersion.objects.create(
            organization=organization,
            description="100K words per month + usage based pricing on Languages and Seats",
            version=1,
            flat_fee_billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
            plan=plan,
            status=PLAN_VERSION_STATUS.ACTIVE,
            flat_rate=59,
            version_id="100_language_seats",
        )
        pc1 = PlanComponent.objects.create(
            billable_metric=sum_words, max_metric_units=100_000
        )
        pc2 = PlanComponent.objects.create(
            billable_metric=unique_lang,
            cost_per_batch=10,
            metric_units_per_batch=1,
            free_metric_units=0,
        )
        pc3 = PlanComponent.objects.create(
            billable_metric=num_seats,
            cost_per_batch=12,
            metric_units_per_batch=1,
            free_metric_units=0,
        )
        bp_100_language_seats.components.add(pc1, pc2, pc3)
        plan = Plan.objects.create(
            plan_name="300K Words Plan - UB Language + Seats",
            organization=organization,
            plan_duration=PLAN_DURATION.MONTHLY,
            status=PLAN_STATUS.ACTIVE,
        )
        bp_300_language_seats = PlanVersion.objects.create(
            organization=organization,
            description="300K words per month + usage based pricing on Languages and Seats",
            version=1,
            flat_fee_billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
            plan=plan,
            status=PLAN_VERSION_STATUS.ACTIVE,
            flat_rate=179,
            version_id="300_language_seats",
        )
        pc1 = PlanComponent.objects.create(
            billable_metric=sum_words, max_metric_units=300_000
        )
        pc2 = PlanComponent.objects.create(
            billable_metric=unique_lang,
            cost_per_batch=10,
            metric_units_per_batch=1,
            free_metric_units=0,
        )
        pc3 = PlanComponent.objects.create(
            billable_metric=num_seats, cost_per_batch=10, free_metric_units=0
        )
        bp_300_language_seats.components.add(pc1, pc2, pc3)
        plan = Plan.objects.create(
            plan_name="40K Words Plan - UB Calls + Content Types",
            organization=organization,
            plan_duration=PLAN_DURATION.MONTHLY,
            status=PLAN_STATUS.ACTIVE,
        )
        bp_40_calls_subsections = PlanVersion.objects.create(
            organization=organization,
            description="40K words per month + usage based pricing on Calls and Content Types",
            version=1,
            flat_fee_billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
            plan=plan,
            status=PLAN_VERSION_STATUS.ACTIVE,
            flat_rate=0,
            version_id="40_calls_subsections",
        )
        pc1 = PlanComponent.objects.create(
            billable_metric=sum_words, max_metric_units=40_000
        )
        pc2 = PlanComponent.objects.create(
            billable_metric=calls,
            cost_per_batch=0.30,
            metric_units_per_batch=1,
            free_metric_units=0,
        )
        pc3 = PlanComponent.objects.create(
            billable_metric=unique_subsections,
            free_metric_units=5,
            cost_per_batch=2,
            metric_units_per_batch=1,
        )
        bp_40_calls_subsections.components.add(pc1, pc2, pc3)
        bp_40_calls_subsections.save()
        plan = Plan.objects.create(
            plan_name="100K Words Plan - UB Calls + Content Types",
            organization=organization,
            plan_duration=PLAN_DURATION.MONTHLY,
            status=PLAN_STATUS.ACTIVE,
        )
        bp_100_calls_subsections = PlanVersion.objects.create(
            organization=organization,
            description="100K words per month + usage based pricing on Calls and Content Types",
            version=1,
            flat_fee_billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
            plan=plan,
            status=PLAN_VERSION_STATUS.ACTIVE,
            flat_rate=0,
            version_id="100_calls_subsections",
        )
        pc1 = PlanComponent.objects.create(
            billable_metric=sum_words, max_metric_units=100_000
        )
        pc2 = PlanComponent.objects.create(
            billable_metric=calls,
            cost_per_batch=0.25,
            metric_units_per_batch=1,
            free_metric_units=0,
        )
        pc3 = PlanComponent.objects.create(
            billable_metric=unique_subsections,
            free_metric_units=6,
            cost_per_batch=3,
            metric_units_per_batch=1,
        )
        bp_100_calls_subsections.components.add(pc1, pc2, pc3)
        bp_100_calls_subsections.save()
        plan = Plan.objects.create(
            plan_name="300K Words Plan - UB Calls + Content Types",
            organization=organization,
            plan_duration=PLAN_DURATION.MONTHLY,
            status=PLAN_STATUS.ACTIVE,
        )
        bp_300_calls_subsections = PlanVersion.objects.create(
            organization=organization,
            description="300K words per month + usage based pricing on Calls and Content Types",
            version=1,
            flat_fee_billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
            plan=plan,
            status=PLAN_VERSION_STATUS.ACTIVE,
            flat_rate=0,
            version_id="300_calls_subsections",
        )
        pc1 = PlanComponent.objects.create(
            billable_metric=sum_words, max_metric_units=300_000
        )
        pc2 = PlanComponent.objects.create(
            billable_metric=calls,
            cost_per_batch=0.20,
            metric_units_per_batch=1,
            free_metric_units=0,
        )
        pc3 = PlanComponent.objects.create(
            billable_metric=unique_subsections,
            free_metric_units=7,
            cost_per_batch=4,
            metric_units_per_batch=1,
        )
        bp_300_calls_subsections.components.add(pc1, pc2, pc3)
        bp_300_calls_subsections.save()
        six_months_ago = now_utc() - relativedelta(months=6) - relativedelta(days=5)
        for i, customer in enumerate(big_customers):
            beginning = six_months_ago
            offset = np.random.randint(0, 30)
            beginning = beginning + relativedelta(days=offset)
            for months in range(6):
                sub_start = beginning + relativedelta(months=months)
                plan = (
                    bp_40_og
                    if months == 0
                    else (bp_100_og if months == 1 else bp_300_og)
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
                scale = (
                    1.1 if plan == bp_40_og else (0.95 if plan == bp_100_og else 0.80)
                )
                sub = Subscription.objects.create(
                    organization=organization,
                    customer=customer,
                    billing_plan=plan,
                    start_date=sub_start,
                    status="ended",
                    is_new=months == 0,
                )
                tot_word_limit = float(
                    plan.components.get(billable_metric=sum_words).max_metric_units
                )
                word_limit = tot_word_limit - np.random.randint(0, tot_word_limit * 0.2)
                word_count = 0
                while word_count < word_limit:
                    event_words = random.gauss(350, 60)
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
        for i, customer in enumerate(medium_customers):
            beginning = six_months_ago
            offset = np.random.randint(0, 30)
            beginning = beginning + relativedelta(days=offset)
            for months in range(6):
                sub_start = beginning + relativedelta(months=months)
                plan = bp_40_og if months in [0, 1] else bp_100_og
                languages = [
                    "en",
                    "es",
                    "fr",
                    "de",
                    "it",
                ]
                users_mean, users_sd = 3, 1
                scale = 1.2 if plan == bp_40_og else (1 if plan == bp_100_og else 0.85)
                sub = Subscription.objects.create(
                    organization=organization,
                    customer=customer,
                    billing_plan=plan,
                    start_date=sub_start,
                    status="ended",
                    is_new=months == 0,
                )
                tot_word_limit = float(
                    plan.components.get(billable_metric=sum_words).max_metric_units
                )
                word_limit = tot_word_limit - np.random.randint(0, tot_word_limit * 0.2)
                word_count = 0
                while word_count < word_limit:
                    event_words = random.gauss(350, 60)
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
        for i, customer in enumerate(small_customers):
            beginning = six_months_ago
            offset = np.random.randint(0, 30)  # random.gauss(0, 15)//1
            beginning = beginning + relativedelta(days=offset)
            for months in range(6):
                sub_start = beginning + relativedelta(months=months)
                plan = free_bp if months in [0, 1] else bp_40_og
                languages = [
                    "en",
                ]
                users_mean, users_sd = 2, 0.75
                scale = (
                    1.4 if plan == bp_40_og else (1.1 if plan == bp_100_og else 0.95)
                )
                sub = Subscription.objects.create(
                    organization=organization,
                    customer=customer,
                    billing_plan=plan,
                    start_date=sub_start,
                    status="ended",
                    is_new=months == 0,
                )
                tot_word_limit = float(
                    plan.components.get(billable_metric=sum_words).max_metric_units
                )
                word_limit = tot_word_limit - np.random.randint(0, tot_word_limit * 0.2)
                word_count = 0
                while word_count < word_limit:
                    event_words = random.gauss(350, 60)
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
                n = int(max(random.gauss(6, 1.5) // 1, 1))
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
        now = now_utc()
        Subscription.objects.filter(
            organization=organization,
            status=SUBSCRIPTION_STATUS.ENDED,
            end_date__gt=now,
        ).update(status=SUBSCRIPTION_STATUS.ACTIVE)


def random_date(start, end, n):
    """Generate a random datetime between `start` and `end`"""
    if type(start) is datetime.date:
        start = date_as_min_dt(start)
    if type(end) is datetime.date:
        end = date_as_max_dt(end)
    for _ in range(n):
        dt = start + relativedelta(
            # Get a random amount of seconds between `start` and `end`
            seconds=random.randint(0, int((end - start).total_seconds())),
        )
        yield dt


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
            "qty": int(max(qty, 1)),
        }
