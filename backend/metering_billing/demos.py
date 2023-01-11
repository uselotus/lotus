import datetime
import itertools
import logging
import random
import time
import uuid

import numpy as np
import pytz
from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from faker import Faker
from metering_billing.aggregation.billable_metrics import METRIC_HANDLER_MAP
from metering_billing.invoice import generate_invoice
from metering_billing.models import *
from metering_billing.payment_providers import PAYMENT_PROVIDER_MAP
from metering_billing.tasks import run_backtest, run_generate_invoice
from metering_billing.utils import (
    calculate_end_date,
    date_as_max_dt,
    date_as_min_dt,
    now_utc,
    plan_version_uuid,
)
from metering_billing.utils.enums import (
    BACKTEST_KPI,
    EVENT_TYPE,
    FLAT_FEE_BILLING_TYPE,
    METRIC_AGGREGATION,
    METRIC_GRANULARITY,
    METRIC_TYPE,
    PLAN_DURATION,
    PLAN_STATUS,
    PLAN_VERSION_STATUS,
    PRICE_TIER_TYPE,
)
from model_bakery import baker

logger = logging.getLogger("django.server")


def setup_demo3(
    organization_name,
    username=None,
    email=None,
    password=None,
    mode="create",
    org_type=Organization.OrganizationType.EXTERNAL_DEMO,
):
    if mode == "create":
        try:
            org = Organization.objects.get(organization_name=organization_name)
            team = org.team
            Event.objects.filter(organization=org).delete()
            org.delete()
            if team is not None:
                team.delete()
            logger.info("[DEMO3]: Deleted existing organization, replacing")
        except Organization.DoesNotExist:
            logger.info("[DEMO3]: creating from scratch")
        try:
            user = User.objects.get(username=username, email=email)
        except:
            user = User.objects.create_user(
                username=username, email=email, password=password
            )
        if user.organization is None:
            organization, _ = Organization.objects.get_or_create(
                organization_name=organization_name
            )
            organization.organization_type = org_type
            user.organization = organization
            user.team = organization.team
            user.save()
            organization.save()
    elif mode == "regenerate":
        organization = Organization.objects.get(organization_name=organization_name)
        user = organization.users.all().first()
        WebhookEndpoint.objects.filter(organization=organization).delete()
        WebhookTrigger.objects.filter(organization=organization).delete()
        Subscription.objects.filter(organization=organization).delete()
        PlanVersion.objects.filter(organization=organization).delete()
        Plan.objects.filter(organization=organization).delete()
        Customer.objects.filter(organization=organization).delete()
        Event.objects.filter(organization=organization).delete()
        Metric.objects.filter(organization=organization).delete()
        Product.objects.filter(organization=organization).delete()
        CustomerBalanceAdjustment.objects.filter(organization=organization).delete()
        Feature.objects.filter(organization=organization).delete()
        Invoice.objects.filter(organization=organization).delete()
        APIToken.objects.filter(organization=organization).delete()
        TeamInviteToken.objects.filter(organization=organization).delete()
        PriceAdjustment.objects.filter(organization=organization).delete()
        ExternalPlanLink.objects.filter(organization=organization).delete()
        SubscriptionRecord.objects.filter(organization=organization).delete()
        Backtest.objects.filter(organization=organization).delete()
        PricingUnit.objects.filter(organization=organization).delete()
        NumericFilter.objects.filter(organization=organization).delete()
        CategoricalFilter.objects.filter(organization=organization).delete()
        PriceTier.objects.filter(organization=organization).delete()
        PlanComponent.objects.filter(organization=organization).delete()
        InvoiceLineItem.objects.filter(organization=organization).delete()
        BacktestSubstitution.objects.filter(organization=organization).delete()
        CustomPricingUnitConversion.objects.filter(organization=organization).delete()
        if user is None:
            organization.delete()
            return
    organization = user.organization
    big_customers = []
    for _ in range(1):
        customer = Customer.objects.create(
            organization=organization,
            customer_name="BigCompany " + str(uuid.uuid4().hex)[:6],
            email=f"{str(uuid.uuid4().hex)}@{str(uuid.uuid4().hex)}.com",
        )
        big_customers.append(customer)
    medium_customers = []
    for _ in range(2):
        customer = Customer.objects.create(
            organization=organization,
            customer_name="MediumCompany " + str(uuid.uuid4().hex)[:6],
            email=f"{str(uuid.uuid4().hex)}@{str(uuid.uuid4().hex)}.com",
        )
        medium_customers.append(customer)
    small_customers = []
    for _ in range(5):
        customer = Customer.objects.create(
            organization=organization,
            customer_name="SmallCompany " + str(uuid.uuid4().hex)[:6],
            email=f"{str(uuid.uuid4().hex)}@{str(uuid.uuid4().hex)}.com",
        )
        small_customers.append(customer)
    metrics_map = {}
    for property_name, usage_aggregation_type, billable_metric_name, name in zip(
        [None, "words", "compute_time", "language", "subsection"],
        ["count", "sum", "sum", "unique", "unique"],
        ["API Calls", "Words", "Compute Time", "Unique Languages", "Content Types"],
        ["calls", "sum_words", "sum_compute", "unique_lang", "unique_subsections"],
    ):
        validated_data = {
            "organization": organization,
            "event_name": "generate_text",
            "property_name": property_name,
            "usage_aggregation_type": usage_aggregation_type,
            "billable_metric_name": billable_metric_name,
            "metric_type": METRIC_TYPE.COUNTER,
        }
        metric = METRIC_HANDLER_MAP[METRIC_TYPE.COUNTER].create_metric(validated_data)
        metrics_map[name] = metric
    for property_name, usage_aggregation_type, billable_metric_name, name in zip(
        ["qty"], ["max"], ["User Seats"], ["num_seats"]
    ):
        validated_data = {
            "organization": organization,
            "event_name": "log_num_seats",
            "property_name": property_name,
            "usage_aggregation_type": usage_aggregation_type,
            "billable_metric_name": billable_metric_name,
            "metric_type": METRIC_TYPE.GAUGE,
            "event_type": EVENT_TYPE.TOTAL,
        }
        metric = METRIC_HANDLER_MAP[METRIC_TYPE.GAUGE].create_metric(validated_data)
        metrics_map[name] = metric
    for property_name, usage_aggregation_type, billable_metric_name, name in zip(
        ["cost"], ["sum"], ["Compute Cost"], ["compute_cost"]
    ):
        validated_data = {
            "organization": organization,
            "event_name": "computation",
            "property_name": property_name,
            "usage_aggregation_type": usage_aggregation_type,
            "billable_metric_name": billable_metric_name,
            "metric_type": METRIC_TYPE.COUNTER,
            "is_cost_metric": True,
        }
        metric = METRIC_HANDLER_MAP[METRIC_TYPE.COUNTER].create_metric(validated_data)
        assert metric is not None
        metrics_map[name] = metric
    calls = metrics_map["calls"]
    sum_words = metrics_map["sum_words"]
    sum_compute = metrics_map["sum_compute"]
    unique_lang = metrics_map["unique_lang"]
    unique_subsections = metrics_map["unique_subsections"]
    num_seats = metrics_map["num_seats"]
    compute_cost = metrics_map["compute_cost"]
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
        version_id=plan_version_uuid(),
    )
    create_pc_and_tiers(
        organization, plan_version=free_bp, billable_metric=sum_words, free_units=2_000
    )
    create_pc_and_tiers(
        organization, plan_version=free_bp, billable_metric=num_seats, free_units=1
    )
    plan.display_version = free_bp
    plan.save()
    plan = Plan.objects.create(
        plan_name="10K Words Plan",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
        status=PLAN_STATUS.ACTIVE,
    )
    bp_10_og = PlanVersion.objects.create(
        organization=organization,
        description="10K Words Plan",
        version=1,
        flat_fee_billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
        plan=plan,
        status=PLAN_VERSION_STATUS.ACTIVE,
        flat_rate=49,
        version_id=plan_version_uuid(),
    )
    create_pc_and_tiers(
        organization,
        plan_version=bp_10_og,
        billable_metric=sum_words,
        free_units=10_000,
    )
    create_pc_and_tiers(
        organization, plan_version=bp_10_og, billable_metric=num_seats, free_units=5
    )
    plan.display_version = bp_10_og
    plan.save()
    plan = Plan.objects.create(
        plan_name="25K Words Plan",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
        status=PLAN_STATUS.ACTIVE,
    )
    bp_25_og = PlanVersion.objects.create(
        organization=organization,
        description="25K words per month",
        version=1,
        flat_fee_billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
        plan=plan,
        status=PLAN_VERSION_STATUS.ACTIVE,
        flat_rate=99,
        version_id=plan_version_uuid(),
    )
    create_pc_and_tiers(
        organization,
        plan_version=bp_25_og,
        billable_metric=sum_words,
        free_units=25_000,
    )
    create_pc_and_tiers(
        organization, plan_version=bp_25_og, billable_metric=num_seats, free_units=5
    )
    plan.display_version = bp_25_og
    plan.save()
    plan = Plan.objects.create(
        plan_name="50K Words Plan",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
        status=PLAN_STATUS.ACTIVE,
    )
    bp_50_og = PlanVersion.objects.create(
        organization=organization,
        description="50K words per month",
        version=1,
        flat_fee_billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
        plan=plan,
        status=PLAN_VERSION_STATUS.ACTIVE,
        flat_rate=279,
        version_id=plan_version_uuid(),
    )
    create_pc_and_tiers(
        organization,
        plan_version=bp_50_og,
        billable_metric=sum_words,
        free_units=50_000,
    )
    create_pc_and_tiers(
        organization, plan_version=bp_50_og, billable_metric=num_seats, free_units=5
    )
    plan.display_version = bp_50_og
    plan.save()
    plan = Plan.objects.create(
        plan_name="10K Words Plan - UB Compute + Seats",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
        status=PLAN_STATUS.ACTIVE,
    )
    bp_10_compute_seats = PlanVersion.objects.create(
        organization=organization,
        description="10K words per month + usage based pricing on Compute Time and Seats",
        version=1,
        flat_fee_billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
        plan=plan,
        status=PLAN_VERSION_STATUS.ACTIVE,
        flat_rate=19,
        version_id=plan_version_uuid(),
    )
    create_pc_and_tiers(
        organization,
        plan_version=bp_10_compute_seats,
        billable_metric=sum_words,
        free_units=10_000,
    )
    create_pc_and_tiers(
        organization,
        plan_version=bp_10_compute_seats,
        billable_metric=sum_compute,
        free_units=75,
        cost_per_batch=0.33,
        metric_units_per_batch=10,
    )
    create_pc_and_tiers(
        organization,
        plan_version=bp_10_compute_seats,
        billable_metric=num_seats,
        free_units=None,
        cost_per_batch=10,
        metric_units_per_batch=1,
    )
    plan.display_version = bp_10_compute_seats
    plan.save()
    plan = Plan.objects.create(
        plan_name="25K Words Plan - UB Compute + Seats",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
        status=PLAN_STATUS.ACTIVE,
    )
    bp_25_compute_seats = PlanVersion.objects.create(
        organization=organization,
        description="25K words per month + usage based pricing on Compute Time and Seats",
        version=1,
        flat_fee_billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
        plan=plan,
        status=PLAN_VERSION_STATUS.ACTIVE,
        flat_rate=59,
        version_id=plan_version_uuid(),
    )
    create_pc_and_tiers(
        organization,
        plan_version=bp_25_compute_seats,
        billable_metric=sum_words,
        free_units=25_000,
    )
    create_pc_and_tiers(
        organization,
        plan_version=bp_25_compute_seats,
        billable_metric=sum_compute,
        free_units=100,
        cost_per_batch=0.47,
        metric_units_per_batch=10,
    )
    create_pc_and_tiers(
        organization,
        plan_version=bp_25_compute_seats,
        billable_metric=num_seats,
        free_units=None,
        cost_per_batch=12,
        metric_units_per_batch=1,
    )
    plan.display_version = bp_25_compute_seats
    plan.save()
    plan = Plan.objects.create(
        plan_name="50K Words Plan - UB Compute + Seats",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
        status=PLAN_STATUS.ACTIVE,
    )
    bp_50_compute_seats = PlanVersion.objects.create(
        organization=organization,
        description="50K words per month + usage based pricing on Compute Time and Seats",
        version=1,
        flat_fee_billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
        plan=plan,
        status=PLAN_VERSION_STATUS.ACTIVE,
        flat_rate=179,
        version_id=plan_version_uuid(),
    )
    create_pc_and_tiers(
        organization,
        plan_version=bp_50_compute_seats,
        billable_metric=sum_words,
        free_units=50_000,
    )
    create_pc_and_tiers(
        organization,
        plan_version=bp_50_compute_seats,
        billable_metric=sum_compute,
        free_units=200,
        cost_per_batch=0.67,
        metric_units_per_batch=10,
    )
    create_pc_and_tiers(
        organization,
        plan_version=bp_50_compute_seats,
        billable_metric=num_seats,
        free_units=None,
        cost_per_batch=10,
        metric_units_per_batch=1,
    )
    plan.display_version = bp_50_compute_seats
    plan.save()
    six_months_ago = now_utc() - relativedelta(months=6) - relativedelta(days=5)
    for cust_set_name, cust_set in [
        ("big", big_customers),
        ("medium", medium_customers),
        ("small", small_customers),
    ]:
        plan_dict = {
            "big": {
                0: bp_10_compute_seats,
                1: bp_25_compute_seats,
                2: bp_50_compute_seats,
                3: bp_50_compute_seats,
                4: bp_50_compute_seats,
                5: bp_50_compute_seats,
            },
            "medium": {
                0: bp_10_compute_seats,
                1: bp_10_compute_seats,
                2: bp_25_compute_seats,
                3: bp_25_compute_seats,
                4: bp_25_compute_seats,
                5: bp_25_compute_seats,
            },
            "small": {
                0: free_bp,
                1: free_bp,
                2: bp_10_compute_seats,
                3: bp_10_compute_seats,
                4: bp_10_compute_seats,
                5: bp_10_compute_seats,
            },
        }
        for i, customer in enumerate(cust_set):
            beginning = six_months_ago
            offset = np.random.randint(0, 30)
            beginning = beginning + relativedelta(days=offset)
            for months in range(6):
                sub_start = beginning + relativedelta(months=months)
                plan = plan_dict[cust_set_name][months]
                languages = [
                    "en",
                    "es",
                    "fr",
                    "de",
                    "it",
                    "pt",
                    "ru",
                ]
                if cust_set_name == "big":
                    users_mean, users_sd = 4.5, 0.5
                    scale = (
                        1.1
                        if plan == bp_10_og
                        else (0.95 if plan == bp_25_og else 0.80)
                    )
                    ct_mean, ct_sd = 0.1, 0.02
                elif cust_set_name == "medium":
                    languages = languages[:5]
                    scale = (
                        1.2
                        if plan == bp_10_compute_seats
                        else (1 if plan == bp_25_compute_seats else 0.85)
                    )
                    ct_mean, ct_sd = 0.075, 0.01
                elif cust_set_name == "small":
                    languages = languages[:1]
                    scale = (
                        1.4
                        if plan == bp_10_compute_seats
                        else (1.1 if plan == bp_25_compute_seats else 0.95)
                    )
                    ct_mean, ct_sd = 0.065, 0.01

                sub, sr = make_subscription_and_subscription_record(
                    organization=organization,
                    customer=customer,
                    plan=plan,
                    start_date=sub_start,
                    is_new=months == 0,
                )
                tot_word_limit = float(
                    max(
                        x.range_end
                        for x in plan.plan_components.get(
                            billable_metric=sum_words
                        ).tiers.all()
                    )
                )
                word_limit = tot_word_limit - np.random.randint(0, tot_word_limit * 0.2)
                word_count = 0
                while word_count < word_limit:
                    event_words = random.gauss(325, 60)
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
                        idempotency_id=str(uuid.uuid4().hex),
                        properties={
                            "language": language,
                            "subsection": subsection,
                            "compute_time": compute_time,
                            "words": event_words,
                        },
                        cust_id=customer.customer_id,
                    )
                    Event.objects.create(
                        organization=organization,
                        customer=customer,
                        event_name="computation",
                        time_created=tc,
                        idempotency_id=str(uuid.uuid4().hex),
                        properties={
                            "cost": abs(compute_time * random.gauss(ct_mean, ct_sd)),
                        },
                        cust_id=customer.customer_id,
                    )
                    word_count += event_words
                max_users = max(
                    x.range_end
                    for x in plan.plan_components.get(
                        billable_metric=num_seats
                    ).tiers.all()
                )
                n = max(int(random.gauss(6, 1.5) // 1), 1)
                baker.make(
                    Event,
                    organization=organization,
                    customer=customer,
                    event_name="log_num_seats",
                    properties=gaussian_users(n, users_mean, users_sd, max_users),
                    time_created=random_date(sub.start_date, sub.end_date, n),
                    idempotency_id=itertools.cycle(
                        [str(uuid.uuid4().hex) for _ in range(n)]
                    ),
                    _quantity=n,
                    cust_id=customer.customer_id,
                )

                next_plan = (
                    bp_10_compute_seats
                    if months + 1 == 0
                    else (
                        bp_25_compute_seats if months + 1 == 1 else bp_50_compute_seats
                    )
                )
                if months == 0:
                    run_generate_invoice.delay(
                        sub.pk,
                        [sr.pk],
                        issue_date=sub.start_date,
                    )
                if months != 5:
                    cur_replace_with = sr.billing_plan.replace_with
                    sr.billing_plan.replace_with = next_plan
                    sr.save()
                    run_generate_invoice.delay(
                        sub.pk, [sr.pk], issue_date=sub.end_date, charge_next_plan=True
                    )
                    sr.billing_plan.replace_with = cur_replace_with
                    sr.save()
    now = now_utc()
    backtest = Backtest.objects.create(
        backtest_name=organization,
        start_date="2022-08-01",
        end_date="2022-11-01",
        organization=organization,
        time_created=now,
        kpis=[BACKTEST_KPI.TOTAL_REVENUE],
    )
    BacktestSubstitution.objects.create(
        backtest=backtest,
        original_plan=bp_10_compute_seats,
        new_plan=bp_10_og,
        organization=organization,
    )
    run_backtest.delay(backtest.backtest_id)
    return user


def setup_demo4(
    organization_name,
    username=None,
    email=None,
    password=None,
    mode="create",
    org_type=Organization.OrganizationType.EXTERNAL_DEMO,
):
    if mode == "create":
        try:
            org = Organization.objects.get(organization_name=organization_name)
            Event.objects.filter(organization=org).delete()
            org.delete()
            logger.info("[DEMO4]: Deleted existing organization, replacing")
        except Organization.DoesNotExist:
            logger.info("[DEMO4]: creating from scratch")
        try:
            user = User.objects.get(username=username, email=email)
        except:
            user = User.objects.create_user(
                username=username, email=email, password=password
            )
        if user.organization is None:
            organization, _ = Organization.objects.get_or_create(
                organization_name=organization_name
            )
            organization.organization_type = org_type
            user.organization = organization
            user.save()
            organization.save()
    elif mode == "regenerate":
        organization = Organization.objects.get(organization_name=organization_name)
        user = organization.users.all().first()
        WebhookEndpoint.objects.filter(organization=organization).delete()
        WebhookTrigger.objects.filter(organization=organization).delete()
        Subscription.objects.filter(organization=organization).delete()
        PlanVersion.objects.filter(organization=organization).delete()
        Plan.objects.filter(organization=organization).delete()
        Customer.objects.filter(organization=organization).delete()
        Event.objects.filter(organization=organization).delete()
        Metric.objects.filter(organization=organization).delete()
        Product.objects.filter(organization=organization).delete()
        CustomerBalanceAdjustment.objects.filter(organization=organization).delete()
        Feature.objects.filter(organization=organization).delete()
        Invoice.objects.filter(organization=organization).delete()
        APIToken.objects.filter(organization=organization).delete()
        TeamInviteToken.objects.filter(organization=organization).delete()
        PriceAdjustment.objects.filter(organization=organization).delete()
        ExternalPlanLink.objects.filter(organization=organization).delete()
        SubscriptionRecord.objects.filter(organization=organization).delete()
        Backtest.objects.filter(organization=organization).delete()
        PricingUnit.objects.filter(organization=organization).delete()
        NumericFilter.objects.filter(organization=organization).delete()
        CategoricalFilter.objects.filter(organization=organization).delete()
        PriceTier.objects.filter(organization=organization).delete()
        PlanComponent.objects.filter(organization=organization).delete()
        InvoiceLineItem.objects.filter(organization=organization).delete()
        BacktestSubstitution.objects.filter(organization=organization).delete()
        CustomPricingUnitConversion.objects.filter(organization=organization).delete()
        if user is None:
            organization.delete()
            return
    organization = user.organization
    big_customers = []
    for _ in range(1):
        customer = Customer.objects.create(
            organization=organization,
            customer_name="BigCompany " + str(uuid.uuid4().hex)[:6],
            email=f"{str(uuid.uuid4().hex)}@{str(uuid.uuid4().hex)}.com",
        )
        big_customers.append(customer)
    medium_customers = []
    for _ in range(2):
        customer = Customer.objects.create(
            organization=organization,
            customer_name="MediumCompany " + str(uuid.uuid4().hex)[:6],
            email=f"{str(uuid.uuid4().hex)}@{str(uuid.uuid4().hex)}.com",
        )
        medium_customers.append(customer)
    small_customers = []
    for _ in range(4):
        customer = Customer.objects.create(
            organization=organization,
            customer_name="SmallCompany " + str(uuid.uuid4().hex)[:6],
            email=f"{str(uuid.uuid4().hex)}@{str(uuid.uuid4().hex)}.com",
        )
        small_customers.append(customer)
    metrics_map = {}
    for property_name, usage_aggregation_type, billable_metric_name, name in zip(
        [None, "user_id"],
        ["count", "unique"],
        ["Analytics Events", "Unique Users Tracked"],
        ["calls", "unique_users"],
    ):
        validated_data = {
            "organization": organization,
            "event_name": "analytics_event",
            "property_name": property_name,
            "usage_aggregation_type": usage_aggregation_type,
            "billable_metric_name": billable_metric_name,
            "metric_type": METRIC_TYPE.COUNTER,
        }
        metric = METRIC_HANDLER_MAP[METRIC_TYPE.COUNTER].create_metric(validated_data)
        metrics_map[name] = metric
    for property_name, usage_aggregation_type, billable_metric_name, name in zip(
        [None, "recording_length"],
        [
            "count",
            "sum",
        ],
        ["Session Recordings", "Session Recording Time"],
        ["session_recordings", "sum_time"],
    ):
        validated_data = {
            "organization": organization,
            "event_name": "session_recording",
            "property_name": property_name,
            "usage_aggregation_type": usage_aggregation_type,
            "billable_metric_name": billable_metric_name,
            "metric_type": METRIC_TYPE.COUNTER,
        }
        metric = METRIC_HANDLER_MAP[METRIC_TYPE.COUNTER].create_metric(validated_data)
        metrics_map[name] = metric
    for property_name, usage_aggregation_type, billable_metric_name, name in zip(
        ["qty"], ["max"], ["User Seats"], ["num_seats"]
    ):
        validated_data = {
            "organization": organization,
            "event_name": "log_num_seats",
            "property_name": property_name,
            "usage_aggregation_type": usage_aggregation_type,
            "billable_metric_name": billable_metric_name,
            "metric_type": METRIC_TYPE.GAUGE,
            "event_type": EVENT_TYPE.TOTAL,
        }
        metric = METRIC_HANDLER_MAP[METRIC_TYPE.GAUGE].create_metric(validated_data)
        metrics_map[name] = metric
    for property_name, usage_aggregation_type, billable_metric_name, name in zip(
        ["cost"], ["sum"], ["Server Costs"], ["server_costs"]
    ):
        validated_data = {
            "organization": organization,
            "event_name": "server_cost_logging",
            "property_name": property_name,
            "usage_aggregation_type": usage_aggregation_type,
            "billable_metric_name": billable_metric_name,
            "metric_type": METRIC_TYPE.COUNTER,
            "is_cost_metric": True,
        }
        metric = METRIC_HANDLER_MAP[METRIC_TYPE.COUNTER].create_metric(validated_data)
        assert metric is not None
        metrics_map[name] = metric
    calls = metrics_map["calls"]
    unique_users = metrics_map["unique_users"]
    session_recordings = metrics_map["session_recordings"]
    sum_time = metrics_map["sum_time"]
    num_seats = metrics_map["num_seats"]
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
        version_id=plan_version_uuid(),
    )
    create_pc_and_tiers(
        organization, plan_version=free_bp, billable_metric=calls, free_units=50
    )
    create_pc_and_tiers(
        organization,
        plan_version=free_bp,
        billable_metric=num_seats,
        free_units=1,
        max_units=1,
    )
    plan.display_version = free_bp
    plan.save()
    plan = Plan.objects.create(
        plan_name="Events-only - Basic",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
        status=PLAN_STATUS.ACTIVE,
    )
    bp_basic_events = PlanVersion.objects.create(
        organization=organization,
        description="Basic plan, with access to only analytics events. $29/month flat fee + 20 cents per_usage",
        version=1,
        flat_fee_billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
        plan=plan,
        status=PLAN_VERSION_STATUS.ACTIVE,
        flat_rate=29,
        version_id=plan_version_uuid(),
    )
    create_pc_and_tiers(
        organization,
        plan_version=bp_basic_events,
        billable_metric=calls,
        free_units=10,
        max_units=100,
        cost_per_batch=0.20,
        metric_units_per_batch=1,
    )
    create_pc_and_tiers(
        organization,
        plan_version=bp_basic_events,
        billable_metric=num_seats,
        free_units=3,
    )
    plan.display_version = bp_basic_events
    plan.save()
    plan = Plan.objects.create(
        plan_name="Events-only - Pro",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
        status=PLAN_STATUS.ACTIVE,
    )
    bp_pro_events = PlanVersion.objects.create(
        organization=organization,
        description="Pro plan, with access to only analytics events. $69/month flat fee + 25 cents charge for events",
        version=1,
        flat_fee_billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
        plan=plan,
        status=PLAN_VERSION_STATUS.ACTIVE,
        flat_rate=69,
        version_id=plan_version_uuid(),
    )
    create_pc_and_tiers(
        organization,
        plan_version=bp_pro_events,
        billable_metric=calls,
        free_units=100,
        max_units=500,
        cost_per_batch=0.25,
        metric_units_per_batch=1,
    )
    create_pc_and_tiers(
        organization,
        plan_version=bp_pro_events,
        billable_metric=num_seats,
        free_units=5,
    )
    plan.display_version = bp_pro_events
    plan.save()
    plan = Plan.objects.create(
        plan_name="Events + Recordings - Basic",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
        status=PLAN_STATUS.ACTIVE,
    )
    bp_basic_both = PlanVersion.objects.create(
        organization=organization,
        description="Basic plan, with access to analytics events + session recordings. $59/month flat fee + 20 cent per_usage charge for events + $0.35 per session recording",
        version=1,
        flat_fee_billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
        plan=plan,
        status=PLAN_VERSION_STATUS.ACTIVE,
        flat_rate=59,
        version_id=plan_version_uuid(),
    )
    create_pc_and_tiers(
        organization,
        plan_version=bp_basic_both,
        billable_metric=calls,
        free_units=10,
        max_units=100,
        cost_per_batch=0.20,
        metric_units_per_batch=1,
    )
    create_pc_and_tiers(
        organization,
        plan_version=bp_basic_both,
        billable_metric=session_recordings,
        cost_per_batch=0.35,
        metric_units_per_batch=1,
    )
    create_pc_and_tiers(
        organization,
        plan_version=bp_basic_both,
        billable_metric=num_seats,
        free_units=3,
    )
    plan.display_version = bp_basic_both
    plan.save()
    plan = Plan.objects.create(
        plan_name="Events + Recordings - Pro",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
        status=PLAN_STATUS.ACTIVE,
    )
    bp_pro_both = PlanVersion.objects.create(
        organization=organization,
        description="Pro plan, with access to analytics events + session recordings. $119/month flat fee + 25 cent per_usage charge + $0.35 per session recording",
        version=1,
        flat_fee_billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
        plan=plan,
        status=PLAN_VERSION_STATUS.ACTIVE,
        flat_rate=119,
        version_id=plan_version_uuid(),
    )
    create_pc_and_tiers(
        organization,
        plan_version=bp_pro_both,
        billable_metric=calls,
        free_units=100,
        max_units=500,
        cost_per_batch=0.25,
        metric_units_per_batch=1,
    )
    create_pc_and_tiers(
        organization,
        plan_version=bp_pro_both,
        billable_metric=session_recordings,
        cost_per_batch=0.35,
        metric_units_per_batch=1,
    )
    create_pc_and_tiers(
        organization,
        plan_version=bp_pro_both,
        billable_metric=num_seats,
        free_units=5,
    )
    plan.display_version = bp_pro_both
    plan.save()
    plan = Plan.objects.create(
        plan_name="Experimental - Events + Recording Time",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
        status=PLAN_STATUS.ACTIVE,
    )
    bp_experimental = PlanVersion.objects.create(
        organization=organization,
        description="Experimental Plan for charging based on Recording Time instead of number of recordings",
        version=1,
        flat_fee_billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
        plan=plan,
        status=PLAN_VERSION_STATUS.ACTIVE,
        flat_rate=89,
        version_id=plan_version_uuid(),
    )
    create_pc_and_tiers(
        organization,
        plan_version=bp_experimental,
        billable_metric=calls,
        free_units=100,
        max_units=500,
        cost_per_batch=0.25,
        metric_units_per_batch=1,
    )
    create_pc_and_tiers(
        organization,
        plan_version=bp_experimental,
        billable_metric=sum_time,
        cost_per_batch=0.35 / 60,
        metric_units_per_batch=1,
    )
    create_pc_and_tiers(
        organization,
        plan_version=bp_experimental,
        billable_metric=num_seats,
        free_units=5,
    )
    plan.display_version = bp_experimental
    plan.save()
    six_months_ago = now_utc() - relativedelta(months=6) - relativedelta(days=5)
    for cust_set_name, cust_set in [
        ("big", big_customers),
        ("medium", medium_customers),
        ("small", small_customers),
    ]:
        plan_dict = {
            "big": {
                0: bp_basic_both,
                1: bp_basic_both,
                2: bp_pro_both,
                3: bp_pro_both,
                4: bp_pro_both,
                5: bp_pro_both,
            },
            "medium": {
                0: bp_basic_events,
                1: bp_basic_both,
                2: bp_pro_events,
                3: bp_pro_events,
                4: bp_pro_events,
                5: bp_pro_events,
            },
            "small": {
                0: free_bp,
                1: free_bp,
                2: bp_basic_events,
                3: bp_basic_events,
                4: bp_basic_events,
                5: bp_basic_events,
            },
        }
        for i, customer in enumerate(cust_set):
            beginning = six_months_ago
            offset = np.random.randint(0, 30)
            beginning = beginning + relativedelta(days=offset)
            for months in range(6):
                start_time = time.time()
                sub_start = beginning + relativedelta(months=months)
                plan = plan_dict[cust_set_name][months]
                if cust_set_name == "big":
                    if plan == bp_basic_both:
                        n_analytics = max(min(int(random.gauss(80, 10) // 1), 100), 1)
                        n_recordings = max(int(random.gauss(200, 20) // 1), 1)
                    elif plan == bp_pro_both:
                        n_analytics = max(min(int(random.gauss(400, 50) // 1), 500), 1)
                        n_recordings = max(int(random.gauss(200, 20) // 1), 1)
                    n_cust = 100
                    users_mean, users_sd = 4.5, 0.5
                elif cust_set_name == "medium":
                    if plan == bp_basic_events:
                        n_analytics = max(min(int(random.gauss(80, 10) // 1), 100), 1)
                        n_recordings = 0
                    elif plan == bp_pro_events:
                        n_analytics = max(min(int(random.gauss(400, 50) // 1), 500), 1)
                        n_recordings = 0
                    elif plan == bp_pro_both:
                        n_analytics = max(min(int(random.gauss(400, 50) // 1), 500), 1)
                        n_recordings = max(int(random.gauss(150, 10) // 1), 1)
                    n_cust = 40
                    users_mean, users_sd = 3.5, 0.5
                elif cust_set_name == "small":
                    if plan == free_bp:
                        n_analytics = max(int(random.gauss(20, 10) // 1), 50)
                        n_recordings = 0
                    elif plan == bp_basic_events:
                        n_analytics = max(min(int(random.gauss(80, 10) // 1), 100), 1)
                        n_recordings = 0
                    n_cust = 10
                    users_mean, users_sd = 1.5, 0.5

                sub, sr = make_subscription_and_subscription_record(
                    organization=organization,
                    customer=customer,
                    plan=plan,
                    start_date=sub_start,
                    is_new=months == 0,
                )
                if n_analytics != 0:
                    events = []
                    for i in range(n_analytics):
                        dts = list(
                            random_date(sub.start_date, sub.end_date, n_analytics)
                        )
                        user_ids = np.random.randint(1, n_cust, n_analytics)
                        buttons_clicked = np.random.randint(1, 10, n_analytics)
                        page = np.random.randint(1, 100, n_analytics)
                        e = Event(
                            organization=organization,
                            customer=customer,
                            event_name="analytics_event",
                            properties={
                                "user_id": user_ids[i].item(),
                                "buttons_clicked": buttons_clicked[i].item(),
                                "page_url": f"https://www.example.com/{page[i].item()}",
                            },
                            time_created=dts[i],
                            idempotency_id=uuid.uuid4().hex,
                            cust_id=customer.customer_id,
                        )
                        events.append(e)
                    Event.objects.bulk_create(events)
                if n_recordings != 0:
                    events = []
                    for i in range(n_recordings):
                        dts = list(
                            random_date(sub.start_date, sub.end_date, n_recordings)
                        )
                        user_ids = np.random.randint(1, n_cust, n_recordings)
                        recording_lengths = np.random.randint(1, 3600, n_recordings)
                        e = Event(
                            organization=organization,
                            customer=customer,
                            event_name="session_recording",
                            properties={
                                "user_id": user_ids[i].item(),
                                "recording_length": recording_lengths[i].item(),
                            },
                            time_created=dts[i],
                            idempotency_id=uuid.uuid4().hex,
                            cust_id=customer.customer_id,
                        )
                        events.append(e)
                    Event.objects.bulk_create(events)
                n_cost = (n_recordings + n_analytics) // 10
                rnd = np.random.random(n_cost) * 10
                baker.make(
                    Event,
                    organization=organization,
                    customer=customer,
                    event_name="server_cost_logging",
                    properties=itertools.cycle(
                        [
                            {
                                "cost": rnd[i].item(),
                            }
                            for i in range(n_cost)
                        ]
                    ),
                    time_created=random_date(sub.start_date, sub.end_date, n_cost),
                    idempotency_id=itertools.cycle(
                        [uuid.uuid4().hex for _ in range(n_cost)]
                    ),
                    _quantity=n_cost,
                    cust_id=customer.customer_id,
                )
                max_users = max(
                    x.range_end
                    for x in plan.plan_components.get(
                        billable_metric=num_seats
                    ).tiers.all()
                )
                n = max(int(random.gauss(6, 1.5) // 1), 1)
                baker.make(
                    Event,
                    organization=organization,
                    customer=customer,
                    event_name="log_num_seats",
                    properties=gaussian_users(n, users_mean, users_sd, max_users),
                    time_created=random_date(sub.start_date, sub.end_date, n),
                    idempotency_id=itertools.cycle(
                        [str(uuid.uuid4().hex) for _ in range(n)]
                    ),
                    _quantity=n,
                    cust_id=customer.customer_id,
                )

                next_plan = plan_dict[cust_set_name].get(months + 1, plan)
                if months == 0:
                    run_generate_invoice.delay(
                        sub.pk,
                        [sr.pk],
                        issue_date=sub.start_date,
                    )
                if months != 5:
                    cur_replace_with = sr.billing_plan.replace_with
                    sr.billing_plan.replace_with = next_plan
                    sr.save()
                    run_generate_invoice.delay(
                        sub.pk, [sr.pk], issue_date=sub.end_date, charge_next_plan=True
                    )
                    sr.fully_billed = True
                    sr.billing_plan.replace_with = cur_replace_with
                    sr.save()
                end_time = time.time()
                print("Time to generate 1 month data: ", end_time - start_time)
    now = now_utc()
    # backtest = Backtest.objects.create(
    #     backtest_name=organization,
    #     start_date="2022-08-01",
    #     end_date="2022-11-01",
    #     organization=organization,
    #     time_created=now,
    #     kpis=[BACKTEST_KPI.TOTAL_REVENUE],
    # )
    # BacktestSubstitution.objects.create(
    #     backtest=backtest,
    #     original_plan=bp_pro_both,
    #     new_plan=bp_experimental,
    #     organization=organization,
    # )
    # run_backtest.delay(backtest.backtest_id)
    return user


def setup_paas_demo(
    organization_name="paas",
    username="paas",
    email="paas@paas.com",
    password="paas",
    org_type=Organization.OrganizationType.EXTERNAL_DEMO,
):
    try:
        org = Organization.objects.get(organization_name=organization_name)
        Event.objects.filter(organization=org).delete()
        org.delete()
        logger.info("[PAAS DEMO]: Deleted existing organization, replacing")
    except Organization.DoesNotExist:
        logger.info("[PAAS DEMO]: creating from scratch")
    try:
        user = User.objects.get(username=username, email=email)
    except:
        user = User.objects.create_user(
            username=username, email=email, password=password
        )
    if user.organization is None:
        organization, _ = Organization.objects.get_or_create(
            organization_name=organization_name
        )
        user.organization = organization
        organization.organization_type = org_type
        user.save()
        organization.save()
    organization = user.organization
    setting = organization.settings.get(
        setting_name=ORGANIZATION_SETTING_NAMES.SUBSCRIPTION_FILTERS
    )
    setting.setting_values = ["shard_id"]
    big_customers = []
    for _ in range(1):
        customer = Customer.objects.create(
            organization=organization,
            customer_name="BigCompany " + str(uuid.uuid4().hex)[:6],
            email=f"{str(uuid.uuid4().hex)}@{str(uuid.uuid4().hex)}.com",
        )
        big_customers.append(customer)
    medium_customers = []
    for _ in range(2):
        customer = Customer.objects.create(
            organization=organization,
            customer_name="MediumCompany " + str(uuid.uuid4().hex)[:6],
            email=f"{str(uuid.uuid4().hex)}@{str(uuid.uuid4().hex)}.com",
        )
        medium_customers.append(customer)
    small_customers = []
    for _ in range(5):
        customer = Customer.objects.create(
            organization=organization,
            customer_name="SmallCompany " + str(uuid.uuid4().hex)[:6],
            email=f"{str(uuid.uuid4().hex)[:8]}@{str(uuid.uuid4().hex)[:8]}.com",
        )
        small_customers.append(customer)
    (
        valnodes,
        rpcnodes,
        ixnodes,
        evixnodes,
        tntxns,
        mntxns,
        tntxns_rate,
        mntxns_rate,
    ) = baker.make(
        Metric,
        organization=organization,
        event_name=itertools.cycle(
            [
                "num_validators_change",
                "rpc_nodes_change",
                "indexer_nodes_change",
                "event_indexer_nodes_change",
                "testnet_transaction",
                "mainnet_transaction",
                "testnet_transaction",
                "mainnet_transaction",
            ]
        ),
        property_name=itertools.cycle(["change"] * 4 + [""] * 4),
        usage_aggregation_type=itertools.cycle(
            [METRIC_AGGREGATION.MAX] * 4 + [METRIC_AGGREGATION.COUNT] * 4
        ),
        billable_metric_name=itertools.cycle(
            [
                "Validator Nodes",
                "RPC Nodes",
                "Indexer Nodes",
                "Event Indexer Nodes",
                "Testnet Transactions",
                "Mainnet Transactions",
                "Ratelimit Testnet Transactions",
                "Ratelimit Mainnet Transactions",
            ]
        ),
        metric_type=itertools.cycle(
            [METRIC_TYPE.GAUGE] * 4 + [METRIC_TYPE.COUNTER] * 2 + [METRIC_TYPE.RATE] * 2
        ),
        proration=itertools.cycle([METRIC_GRANULARITY.MINUTE] * 4 + [None] * 4),
        event_type=itertools.cycle([EVENT_TYPE.DELTA] * 4 + [None] * 4),
        billable_aggregation_type=itertools.cycle(
            [None] * 6 + [METRIC_AGGREGATION.MAX] * 2
        ),
        granularity=itertools.cycle(
            [METRIC_GRANULARITY.MONTH] * 4 + [None] * 2 + [METRIC_GRANULARITY.HOUR] * 2
        ),
        _quantity=8,
    )
    plan = Plan.objects.create(
        plan_name="Basic Plan",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
        status=PLAN_STATUS.ACTIVE,
    )
    basic_plan = PlanVersion.objects.create(
        organization=organization,
        description="Basic Plan with access to testnet",
        version=1,
        flat_fee_billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
        plan=plan,
        status=PLAN_VERSION_STATUS.ACTIVE,
        flat_rate=125,
    )
    create_pc_and_tiers(
        organization,
        plan_version=basic_plan,
        billable_metric=tntxns,
        free_units=None,
        max_units=2000,
        cost_per_batch=0.05,
        metric_units_per_batch=1,
    )
    create_pc_and_tiers(
        organization,
        plan_version=basic_plan,
        billable_metric=tntxns_rate,
        free_units=50,
    )
    plan.display_version = basic_plan
    plan.save()
    plan = Plan.objects.create(
        plan_name="Professional Plan",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
        status=PLAN_STATUS.ACTIVE,
    )
    professional_plan = PlanVersion.objects.create(
        organization=organization,
        description="Customizable Professional Pla",
        version=1,
        flat_fee_billing_type=FLAT_FEE_BILLING_TYPE.IN_ADVANCE,
        plan=plan,
        status=PLAN_VERSION_STATUS.ACTIVE,
        flat_rate=0,
    )
    create_pc_and_tiers(
        organization,
        plan_version=professional_plan,
        billable_metric=valnodes,
        free_units=2,
        max_units=10,
        cost_per_batch=200,
        metric_units_per_batch=1,
    )
    create_pc_and_tiers(
        organization,
        plan_version=professional_plan,
        billable_metric=rpcnodes,
        free_units=2,
        max_units=10,
        cost_per_batch=200,
        metric_units_per_batch=1,
    )
    create_pc_and_tiers(
        organization,
        plan_version=professional_plan,
        billable_metric=ixnodes,
        free_units=2,
        max_units=10,
        cost_per_batch=200,
        metric_units_per_batch=1,
    )
    create_pc_and_tiers(
        organization,
        plan_version=professional_plan,
        billable_metric=evixnodes,
        free_units=2,
        max_units=10,
        cost_per_batch=200,
        metric_units_per_batch=1,
    )
    create_pc_and_tiers(
        organization,
        plan_version=professional_plan,
        billable_metric=tntxns,
        free_units=None,
        max_units=5000,
        cost_per_batch=0.05,
        metric_units_per_batch=1,
    )
    create_pc_and_tiers(
        organization,
        plan_version=professional_plan,
        billable_metric=tntxns_rate,
        free_units=50,
    )
    create_pc_and_tiers(
        organization,
        plan_version=professional_plan,
        billable_metric=mntxns,
        free_units=None,
        max_units=5000,
        cost_per_batch=0.25,
        metric_units_per_batch=1,
    )
    create_pc_and_tiers(
        organization,
        plan_version=professional_plan,
        billable_metric=mntxns_rate,
        free_units=100,
    )
    plan.display_version = professional_plan
    plan.save()
    for component in professional_plan.plan_components.all():
        if component.billable_metric.metric_type == METRIC_TYPE.GAUGE:
            component.save()


def create_pc_and_tiers(
    organization,
    plan_version,
    billable_metric,
    max_units=None,
    free_units=None,
    cost_per_batch=None,
    metric_units_per_batch=None,
):
    pc = PlanComponent.objects.create(
        plan_version=plan_version,
        billable_metric=billable_metric,
        organization=organization,
    )
    range_start = 0
    if free_units is not None:
        PriceTier.objects.create(
            plan_component=pc,
            range_start=0,
            range_end=free_units,
            type=PRICE_TIER_TYPE.FREE,
            organization=organization,
        )
        range_start = free_units
    if cost_per_batch is not None:
        PriceTier.objects.create(
            plan_component=pc,
            range_start=range_start,
            range_end=max_units,
            type=PRICE_TIER_TYPE.PER_UNIT,
            cost_per_batch=cost_per_batch,
            metric_units_per_batch=metric_units_per_batch,
            organization=organization,
        )


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
            "stacktrace_len": round(random.gauss(50, 15), 0),
            "latency": round(max(random.gauss(325, 25), 0), 2),
            "project": random.choice(["project1", "project2", "project3"]),
        }


def gaussian_users(n, mean=3, sd=1, mx=None):
    "Generate `n` latencies with a gaussian distribution"
    for _ in range(n):
        qty = round(random.gauss(mean, sd), 0)
        if mx is not None:
            qty = min(qty, mx)
        yield {
            "qty": int(max(qty, 1)),
        }


def make_subscription_and_subscription_record(
    organization,
    customer,
    plan,
    start_date,
    is_new,
):
    end_date = calculate_end_date(
        plan.plan.plan_duration,
        start_date,
    )
    sub = Subscription.objects.create(
        organization=organization,
        customer=customer,
        start_date=start_date,
        end_date=end_date,
    )
    sub.handle_attach_plan(
        plan_day_anchor=plan.day_anchor,
        plan_month_anchor=plan.month_anchor,
        plan_start_date=start_date,
        plan_duration=plan.plan.plan_duration,
    )
    sr = SubscriptionRecord.objects.create(
        organization=organization,
        customer=customer,
        billing_plan=plan,
        start_date=start_date,
    )
    sub.save()
    return sub, sr
