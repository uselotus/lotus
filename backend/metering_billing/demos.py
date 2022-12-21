import datetime
import itertools
import logging
import random
import uuid

import numpy as np
import pytz
from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from faker import Faker
from metering_billing.invoice import generate_invoice
from metering_billing.models import *
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


def setup_demo_3(company_name, username=None, email=None, password=None, mode="create"):
    if mode == "create":
        try:
            Organization.objects.get(company_name=company_name).delete()
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
                company_name=company_name
            )
            user.organization = organization
            user.save()
            organization.save()
    elif mode == "regenerate":
        organization = Organization.objects.get(company_name=company_name)
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
        OrganizationInviteToken.objects.filter(organization=organization).delete()
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
    calls, sum_words, sum_compute, unique_lang, unique_subsections = baker.make(
        Metric,
        organization=organization,
        event_name="generate_text",
        property_name=itertools.cycle(
            ["", "words", "compute_time", "language", "subsection"]
        ),
        usage_aggregation_type=itertools.cycle(
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
        metric_type=METRIC_TYPE.COUNTER,
        _quantity=5,
    )
    (num_seats,) = baker.make(
        Metric,
        organization=organization,
        event_name="log_num_seats",
        property_name=itertools.cycle(
            [
                "qty",
            ]
        ),
        usage_aggregation_type=itertools.cycle(["max"]),
        metric_type=METRIC_TYPE.STATEFUL,
        billable_metric_name="User Seats",
        _quantity=1,
    )
    compute_cost = Metric.objects.create(
        organization=organization,
        event_name="computation",
        property_name="cost",
        billable_metric_name="Compute Cost",
        metric_type=METRIC_TYPE.COUNTER,
        usage_aggregation_type="sum",
        is_cost_metric=True,
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
                    idempotency_id=str(uuid.uuid4().hex),
                    _quantity=n,
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
    SubscriptionRecord.objects.filter(
        organization=organization,
        status=SUBSCRIPTION_STATUS.ENDED,
        end_date__gt=now,
    ).update(status=SUBSCRIPTION_STATUS.ACTIVE)
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


def setup_paas_demo(
    company_name="paas", username="paas", email="paas@paas.com", password="paas"
):
    try:
        Organization.objects.get(company_name=company_name).delete()
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
        organization, _ = Organization.objects.get_or_create(company_name=company_name)
        user.organization = organization
        user.save()
        organization.save()
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
            [METRIC_TYPE.STATEFUL] * 4
            + [METRIC_TYPE.COUNTER] * 2
            + [METRIC_TYPE.RATE] * 2
        ),
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
        if component.billable_metric.metric_type == METRIC_TYPE.STATEFUL:
            component.proration_granularity = METRIC_GRANULARITY.MINUTE
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
        plan.day_anchor, plan.month_anchor, start_date, plan.plan.plan_duration
    )
    sr = SubscriptionRecord.objects.create(
        organization=organization,
        customer=customer,
        billing_plan=plan,
        start_date=start_date,
        status=SUBSCRIPTION_STATUS.ENDED,
    )
    sub.status = SUBSCRIPTION_STATUS.ENDED
    sub.save()
    return sub, sr
