import datetime
import itertools
import logging
import random
import time
import uuid

import numpy as np
import pytz
from dateutil.relativedelta import relativedelta
from metering_billing.aggregation.billable_metrics import METRIC_HANDLER_MAP
from metering_billing.invoice import generate_invoice
from metering_billing.models import (
    APIToken,
    Backtest,
    BacktestSubstitution,
    CategoricalFilter,
    ComponentFixedCharge,
    Customer,
    CustomerBalanceAdjustment,
    CustomPricingUnitConversion,
    Event,
    ExternalPlanLink,
    Feature,
    Invoice,
    InvoiceLineItem,
    Metric,
    NumericFilter,
    Organization,
    Plan,
    PlanComponent,
    PlanVersion,
    PriceAdjustment,
    PriceTier,
    PricingUnit,
    Product,
    RecurringCharge,
    SubscriptionRecord,
    TeamInviteToken,
    User,
    WebhookEndpoint,
    WebhookTrigger,
)
from metering_billing.tasks import run_backtest, run_generate_invoice
from metering_billing.utils import date_as_max_dt, date_as_min_dt, now_utc
from metering_billing.utils.enums import (
    BACKTEST_KPI,
    EVENT_TYPE,
    METRIC_AGGREGATION,
    METRIC_GRANULARITY,
    METRIC_TYPE,
    PLAN_DURATION,
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
        except Exception:
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
        PlanVersion.objects.filter(organization=organization).delete()
        Plan.objects.filter(
            organization=organization, parent_plan__isnull=False
        ).delete()
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
    metrics_map["calls"]
    sum_words = metrics_map["sum_words"]
    sum_compute = metrics_map["sum_compute"]
    metrics_map["unique_lang"]
    metrics_map["unique_subsections"]
    num_seats = metrics_map["num_seats"]
    metrics_map["compute_cost"]
    # SET THE BILLING PLANS
    plan = Plan.objects.create(
        plan_name="Free Plan",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
    )
    free_bp = PlanVersion.objects.create(
        organization=organization,
        plan=plan,
        version=1,
        currency=PricingUnit.objects.get(organization=organization, code="USD"),
    )
    RecurringCharge.objects.create(
        organization=organization,
        plan_version=free_bp,
        amount=0,
        name="Flat Rate",
        charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
        pricing_unit=free_bp.currency,
    )
    create_pc_and_tiers(
        organization, plan_version=free_bp, billable_metric=sum_words, free_units=2_000
    )
    create_pc_and_tiers(
        organization, plan_version=free_bp, billable_metric=num_seats, free_units=1
    )
    plan.save()
    plan = Plan.objects.create(
        plan_name="10K Words Plan",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
    )
    bp_10_og = PlanVersion.objects.create(
        organization=organization,
        plan=plan,
        version=1,
        currency=PricingUnit.objects.get(organization=organization, code="USD"),
    )
    RecurringCharge.objects.create(
        organization=organization,
        plan_version=bp_10_og,
        amount=49,
        name="Flat Rate",
        charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
        pricing_unit=bp_10_og.currency,
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
    plan.save()
    plan = Plan.objects.create(
        plan_name="25K Words Plan",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
    )
    bp_25_og = PlanVersion.objects.create(
        organization=organization,
        plan=plan,
        version=1,
        currency=PricingUnit.objects.get(organization=organization, code="USD"),
    )
    RecurringCharge.objects.create(
        organization=organization,
        plan_version=bp_25_og,
        amount=99,
        name="Flat Rate",
        charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
        pricing_unit=bp_25_og.currency,
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
    plan.save()
    plan = Plan.objects.create(
        plan_name="50K Words Plan",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
    )
    bp_50_og = PlanVersion.objects.create(
        organization=organization,
        plan=plan,
        version=1,
        currency=PricingUnit.objects.get(organization=organization, code="USD"),
    )
    RecurringCharge.objects.create(
        organization=organization,
        plan_version=bp_50_og,
        amount=279,
        name="Flat Rate",
        charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
        pricing_unit=bp_50_og.currency,
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
    plan.save()
    plan = Plan.objects.create(
        plan_name="10K Words Plan - UB Compute + Seats",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
    )
    bp_10_compute_seats = PlanVersion.objects.create(
        organization=organization,
        plan=plan,
        version=1,
        currency=PricingUnit.objects.get(organization=organization, code="USD"),
    )
    RecurringCharge.objects.create(
        organization=organization,
        plan_version=bp_10_compute_seats,
        amount=19,
        name="Flat Rate",
        charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
        pricing_unit=bp_10_compute_seats.currency,
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
    plan.save()
    plan = Plan.objects.create(
        plan_name="25K Words Plan - UB Compute + Seats",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
    )
    bp_25_compute_seats = PlanVersion.objects.create(
        organization=organization,
        plan=plan,
        version=1,
        currency=PricingUnit.objects.get(organization=organization, code="USD"),
    )
    RecurringCharge.objects.create(
        organization=organization,
        plan_version=bp_25_compute_seats,
        amount=59,
        name="Flat Rate",
        charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
        pricing_unit=bp_25_compute_seats.currency,
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
    plan.save()
    plan = Plan.objects.create(
        plan_name="50K Words Plan - UB Compute + Seats",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
    )
    bp_50_compute_seats = PlanVersion.objects.create(
        organization=organization,
        plan=plan,
        version=1,
        currency=PricingUnit.objects.get(organization=organization, code="USD"),
    )
    RecurringCharge.objects.create(
        organization=organization,
        plan_version=bp_50_compute_seats,
        amount=179,
        name="Flat Rate",
        charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
        pricing_unit=bp_50_compute_seats.currency,
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

                sr = make_subscription_record(
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
                    for tc in random_date(sr.start_date, sr.end_date, 1):
                        tc = tc
                    Event.objects.create(
                        organization=organization,
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
                    event_name="log_num_seats",
                    properties=gaussian_users(n, users_mean, users_sd, max_users),
                    time_created=random_date(sr.start_date, sr.end_date, n),
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
                    try:
                        run_generate_invoice.delay(
                            [sr.pk],
                            issue_date=sr.start_date,
                        )
                    except Exception as e:
                        print(e)
                        pass
                if months != 5:
                    cur_replace_with = sr.billing_plan.replace_with
                    sr.billing_plan.replace_with = next_plan
                    sr.save()
                    try:
                        run_generate_invoice.delay(
                            [sr.pk], issue_date=sr.end_date, charge_next_plan=True
                        )
                    except Exception as e:
                        print(e)
                        pass
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
    try:
        run_backtest.delay(backtest.backtest_id)
    except Exception as e:
        print(e)
        pass
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
        except Exception:
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
    metrics_map["unique_users"]
    session_recordings = metrics_map["session_recordings"]
    sum_time = metrics_map["sum_time"]
    num_seats = metrics_map["num_seats"]
    # SET THE BILLING PLANS
    plan = Plan.objects.create(
        plan_name="Free Plan",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
    )
    free_bp = PlanVersion.objects.create(
        organization=organization,
        plan=plan,
        version=1,
        currency=PricingUnit.objects.get(organization=organization, code="USD"),
    )
    RecurringCharge.objects.create(
        organization=organization,
        plan_version=free_bp,
        amount=0,
        name="Flat Rate",
        charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
        pricing_unit=free_bp.currency,
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
    plan.save()
    plan = Plan.objects.create(
        plan_name="Events-only - Basic",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
    )
    bp_basic_events = PlanVersion.objects.create(
        organization=organization,
        plan=plan,
        version=1,
        currency=PricingUnit.objects.get(organization=organization, code="USD"),
    )
    RecurringCharge.objects.create(
        organization=organization,
        plan_version=bp_basic_events,
        amount=29,
        name="Flat Rate",
        charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
        pricing_unit=bp_basic_events.currency,
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
    plan.save()
    plan = Plan.objects.create(
        plan_name="Events-only - Pro",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
    )
    bp_pro_events = PlanVersion.objects.create(
        organization=organization,
        plan=plan,
        version=1,
        currency=PricingUnit.objects.get(organization=organization, code="USD"),
    )
    RecurringCharge.objects.create(
        organization=organization,
        plan_version=bp_pro_events,
        amount=69,
        name="Flat Rate",
        charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
        pricing_unit=bp_pro_events.currency,
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
    plan.save()
    plan = Plan.objects.create(
        plan_name="Events + Recordings - Basic",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
    )
    bp_basic_both = PlanVersion.objects.create(
        organization=organization,
        plan=plan,
        version=1,
        currency=PricingUnit.objects.get(organization=organization, code="USD"),
    )
    RecurringCharge.objects.create(
        organization=organization,
        plan_version=bp_basic_both,
        amount=59,
        name="Flat Rate",
        charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
        pricing_unit=bp_basic_both.currency,
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
    plan.save()
    plan = Plan.objects.create(
        plan_name="Events + Recordings - Pro",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
    )
    bp_pro_both = PlanVersion.objects.create(
        organization=organization,
        plan=plan,
        version=1,
        currency=PricingUnit.objects.get(organization=organization, code="USD"),
    )
    RecurringCharge.objects.create(
        organization=organization,
        plan_version=bp_pro_both,
        amount=119,
        name="Flat Rate",
        charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
        pricing_unit=bp_pro_both.currency,
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
    plan.save()
    plan = Plan.objects.create(
        plan_name="Experimental - Events + Recording Time",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
    )
    bp_experimental = PlanVersion.objects.create(
        organization=organization,
        plan=plan,
        version=1,
        currency=PricingUnit.objects.get(organization=organization, code="USD"),
    )
    RecurringCharge.objects.create(
        organization=organization,
        plan_version=bp_experimental,
        amount=89,
        name="Flat Rate",
        charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
        pricing_unit=bp_experimental.currency,
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
                time.time()
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

                sr = make_subscription_record(
                    organization=organization,
                    customer=customer,
                    plan=plan,
                    start_date=sub_start,
                    is_new=months == 0,
                )
                if n_analytics != 0:
                    events = []
                    for i in range(n_analytics):
                        dts = list(random_date(sr.start_date, sr.end_date, n_analytics))
                        user_ids = np.random.randint(1, n_cust, n_analytics)
                        buttons_clicked = np.random.randint(1, 10, n_analytics)
                        page = np.random.randint(1, 100, n_analytics)
                        e = Event(
                            organization=organization,
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
                            random_date(sr.start_date, sr.end_date, n_recordings)
                        )
                        user_ids = np.random.randint(1, n_cust, n_recordings)
                        recording_lengths = np.random.randint(1, 3600, n_recordings)
                        e = Event(
                            organization=organization,
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
                    event_name="server_cost_logging",
                    properties=itertools.cycle(
                        [
                            {
                                "cost": rnd[i].item(),
                            }
                            for i in range(n_cost)
                        ]
                    ),
                    time_created=random_date(sr.start_date, sr.end_date, n_cost),
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
                    event_name="log_num_seats",
                    properties=gaussian_users(n, users_mean, users_sd, max_users),
                    time_created=random_date(sr.start_date, sr.end_date, n),
                    idempotency_id=itertools.cycle(
                        [str(uuid.uuid4().hex) for _ in range(n)]
                    ),
                    _quantity=n,
                    cust_id=customer.customer_id,
                )

                next_plan = plan_dict[cust_set_name].get(months + 1, plan)
                if months == 0:
                    try:
                        run_generate_invoice.delay(
                            [sr.pk],
                            issue_date=sr.start_date,
                        )
                    except Exception as e:
                        print(e)
                        pass
                if months != 5:
                    cur_replace_with = sr.billing_plan.replace_with
                    sr.billing_plan.replace_with = next_plan
                    sr.save()
                    try:
                        run_generate_invoice.delay(
                            [sr.pk], issue_date=sr.end_date, charge_next_plan=True
                        )
                    except Exception as e:
                        print(e)
                        pass
                    sr.fully_billed = True
                    sr.billing_plan.replace_with = cur_replace_with
                    sr.save()
                time.time()
    now_utc()
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
    except Exception:
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
    organization.subscription_filter_keys = ["shard_id"]
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
    )
    basic_plan = PlanVersion.objects.create(
        organization=organization,
        plan=plan,
        version=1,
        currency=PricingUnit.objects.get(organization=organization, code="USD"),
    )
    RecurringCharge.objects.create(
        organization=organization,
        plan_version=basic_plan,
        amount=125,
        name="Flat Rate",
        charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
        pricing_unit=basic_plan.currency,
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
    plan.save()
    plan = Plan.objects.create(
        plan_name="Professional Plan",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
    )
    professional_plan = PlanVersion.objects.create(
        organization=organization,
        plan=plan,
        version=1,
        currency=PricingUnit.objects.get(organization=organization, code="USD"),
    )
    RecurringCharge.objects.create(
        organization=organization,
        plan_version=professional_plan,
        amount=0,
        name="Flat Rate",
        charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
        pricing_unit=professional_plan.currency,
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
    plan.save()
    for component in professional_plan.plan_components.all():
        if component.billable_metric.metric_type == METRIC_TYPE.GAUGE:
            component.save()


def setup_database_demo(
    organization_name,
    username=None,
    email=None,
    password=None,
    mode="create",
    org_type=Organization.OrganizationType.EXTERNAL_DEMO,
    size="small",
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
        except Exception:
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
    for _ in range(1 if size == "small" else 5):
        customer = Customer.objects.create(
            organization=organization,
            customer_name="BigCompany " + str(uuid.uuid4().hex)[:6],
            email=f"{str(uuid.uuid4().hex)}@{str(uuid.uuid4().hex)}.com",
        )
        big_customers.append(customer)
    medium_customers = []
    for _ in range(2 if size == "small" else 10):
        customer = Customer.objects.create(
            organization=organization,
            customer_name="MediumCompany " + str(uuid.uuid4().hex)[:6],
            email=f"{str(uuid.uuid4().hex)}@{str(uuid.uuid4().hex)}.com",
        )
        medium_customers.append(customer)
    small_customers = []
    for _ in range(4 if size == "small" else 20):
        customer = Customer.objects.create(
            organization=organization,
            customer_name="SmallCompany " + str(uuid.uuid4().hex)[:6],
            email=f"{str(uuid.uuid4().hex)}@{str(uuid.uuid4().hex)}.com",
        )
        small_customers.append(customer)
    organization.subscription_filter_keys = ["environment"]
    organization.save()
    gb_storage = METRIC_HANDLER_MAP[METRIC_TYPE.GAUGE].create_metric(
        {
            "organization": organization,
            "event_name": "storage_change",
            "property_name": "gb_storage",
            "usage_aggregation_type": METRIC_AGGREGATION.MAX,
            "billable_metric_name": "GB Months",
            "metric_type": METRIC_TYPE.GAUGE,
            "granularity": METRIC_GRANULARITY.MONTH,
            "event_type": EVENT_TYPE.TOTAL,
        }
    )
    gb_storage_hours = METRIC_HANDLER_MAP[METRIC_TYPE.GAUGE].create_metric(
        {
            "organization": organization,
            "event_name": "storage_change",
            "property_name": "gb_storage",
            "usage_aggregation_type": METRIC_AGGREGATION.MAX,
            "billable_metric_name": "GB Hours - Minute Proration",
            "metric_type": METRIC_TYPE.GAUGE,
            "granularity": METRIC_GRANULARITY.HOUR,
            "proration": METRIC_GRANULARITY.MINUTE,
            "event_type": EVENT_TYPE.TOTAL,
        }
    )
    data_egress = METRIC_HANDLER_MAP[METRIC_TYPE.COUNTER].create_metric(
        {
            "organization": organization,
            "event_name": "data_egress",
            "property_name": "gb_data_egress",
            "usage_aggregation_type": METRIC_AGGREGATION.SUM,
            "billable_metric_name": "GB Data Egress",
            "metric_type": METRIC_TYPE.COUNTER,
        }
    )
    insert_rate = METRIC_HANDLER_MAP[METRIC_TYPE.RATE].create_metric(
        {
            "organization": organization,
            "event_name": "db_insert",
            "property_name": "num_rows",
            "usage_aggregation_type": METRIC_AGGREGATION.SUM,
            "billable_aggregation_type": METRIC_AGGREGATION.MAX,
            "billable_metric_name": "Rows Insert Rate",
            "metric_type": METRIC_TYPE.RATE,
            "granularity": METRIC_GRANULARITY.DAY,
        }
    )
    METRIC_HANDLER_MAP[METRIC_TYPE.COUNTER].create_metric(
        {
            "organization": organization,
            "event_name": "server_costs",
            "property_name": "cost",
            "usage_aggregation_type": METRIC_AGGREGATION.SUM,
            "billable_metric_name": "AWS Server Costs",
            "metric_type": METRIC_TYPE.COUNTER,
            "is_cost_metric": True,
        }
    )
    gb_ram = METRIC_HANDLER_MAP[METRIC_TYPE.GAUGE].create_metric(
        {
            "organization": organization,
            "event_name": "ram_change",
            "property_name": "gb_ram",
            "usage_aggregation_type": METRIC_AGGREGATION.MAX,
            "billable_metric_name": "GB RAM Months - Daily Proration",
            "metric_type": METRIC_TYPE.GAUGE,
            "granularity": METRIC_GRANULARITY.MONTH,
            "proration": METRIC_GRANULARITY.DAY,
            "event_type": EVENT_TYPE.TOTAL,
        }
    )
    number_cpus = METRIC_HANDLER_MAP[METRIC_TYPE.GAUGE].create_metric(
        {
            "organization": organization,
            "event_name": "cpu_change",
            "property_name": "number_cpus",
            "usage_aggregation_type": METRIC_AGGREGATION.MAX,
            "billable_metric_name": "CPU Months - Daily Proration",
            "metric_type": METRIC_TYPE.GAUGE,
            "granularity": METRIC_GRANULARITY.MONTH,
            "proration": METRIC_GRANULARITY.DAY,
            "event_type": EVENT_TYPE.TOTAL,
        }
    )
    # SET THE BILLING PLANS
    # FREE PLAN -- up to 10 GB storage, 100 GB data egress, 1000 rows/hour insert rate, 4GB RAM, 2 CPU -- flat fee
    plan = Plan.objects.create(
        plan_name="Free Plan",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
    )
    free_bp = PlanVersion.objects.create(
        organization=organization,
        plan=plan,
        version=1,
        currency=PricingUnit.objects.get(organization=organization, code="USD"),
    )
    RecurringCharge.objects.create(
        organization=organization,
        plan_version=free_bp,
        amount=0,
        name="Flat Rate",
        charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
        pricing_unit=free_bp.currency,
    )
    create_pc_plus_tiers_new(
        [free_bp],
        pcs_dict={
            gb_storage: {
                "tiers": [
                    {
                        "range_start": 0,
                        "range_end": 10,
                        "batch_rounding_type": PriceTier.BatchRoundingType.NO_ROUNDING,
                        "type": PriceTier.PriceTierType.FREE,
                    }
                ],
            },
            data_egress: {
                "tiers": [
                    {
                        "range_start": 0,
                        "range_end": 100,
                        "batch_rounding_type": PriceTier.BatchRoundingType.NO_ROUNDING,
                        "type": PriceTier.PriceTierType.FREE,
                    }
                ],
            },
            insert_rate: {
                "tiers": [
                    {
                        "range_start": 0,
                        "range_end": 1000,
                        "batch_rounding_type": PriceTier.BatchRoundingType.NO_ROUNDING,
                        "type": PriceTier.PriceTierType.FREE,
                    }
                ],
            },
            gb_ram: {
                "tiers": [
                    {
                        "range_start": 0,
                        "range_end": 4,
                        "batch_rounding_type": PriceTier.BatchRoundingType.NO_ROUNDING,
                        "type": PriceTier.PriceTierType.FREE,
                    }
                ],
            },
            number_cpus: {
                "tiers": [
                    {
                        "range_start": 0,
                        "range_end": 2,
                        "batch_rounding_type": PriceTier.BatchRoundingType.NO_ROUNDING,
                        "type": PriceTier.PriceTierType.FREE,
                    }
                ],
            },
        },
    )
    # BASIC PLAN -- up to 100 GB storage, 1000 GB data egress, 10,000 rows/hour insert rate, 8GB RAM, 4 CPUs -- flat fee
    plan = Plan.objects.create(
        plan_name="Basic Plan",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
    )
    basic_bp_monthly = PlanVersion.objects.create(
        organization=organization,
        plan=plan,
        version=1,
        currency=free_bp.currency,
    )
    RecurringCharge.objects.create(
        organization=organization,
        plan_version=basic_bp_monthly,
        amount=250,
        name="Flat Rate",
        charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
        pricing_unit=basic_bp_monthly.currency,
    )
    plan_yearly = Plan.objects.create(
        plan_name="Basic Plan",
        organization=organization,
        plan_duration=PLAN_DURATION.YEARLY,
    )
    basic_bp_yearly = PlanVersion.objects.create(
        organization=organization,
        plan=plan_yearly,
        version=1,
        currency=free_bp.currency,
    )
    RecurringCharge.objects.create(
        organization=organization,
        plan_version=basic_bp_yearly,
        amount=2500,
        name="Flat Rate",
        charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
        pricing_unit=basic_bp_yearly.currency,
    )
    create_pc_plus_tiers_new(
        [basic_bp_monthly, basic_bp_yearly],
        pcs_dict={
            gb_storage: {
                "tiers": [
                    {
                        "range_start": 0,
                        "range_end": 100,
                        "batch_rounding_type": PriceTier.BatchRoundingType.NO_ROUNDING,
                        "type": PriceTier.PriceTierType.FREE,
                    }
                ],
                "reset_interval_unit": PlanComponent.IntervalLengthType.MONTH,
                "reset_interval_count": 1,
            },
            data_egress: {
                "tiers": [
                    {
                        "range_start": 0,
                        "range_end": 1000,
                        "batch_rounding_type": PriceTier.BatchRoundingType.NO_ROUNDING,
                        "type": PriceTier.PriceTierType.FREE,
                    }
                ],
                "reset_interval_unit": PlanComponent.IntervalLengthType.MONTH,
                "reset_interval_count": 1,
            },
            insert_rate: {
                "tiers": [
                    {
                        "range_start": 0,
                        "range_end": 10_000,
                        "batch_rounding_type": PriceTier.BatchRoundingType.NO_ROUNDING,
                        "type": PriceTier.PriceTierType.FREE,
                    }
                ],
                "reset_interval_unit": PlanComponent.IntervalLengthType.MONTH,
                "reset_interval_count": 1,
            },
            gb_ram: {
                "tiers": [
                    {
                        "range_start": 0,
                        "range_end": 8,
                        "batch_rounding_type": PriceTier.BatchRoundingType.NO_ROUNDING,
                        "type": PriceTier.PriceTierType.FREE,
                    }
                ],
                "reset_interval_unit": PlanComponent.IntervalLengthType.MONTH,
                "reset_interval_count": 1,
            },
            number_cpus: {
                "tiers": [
                    {
                        "range_start": 0,
                        "range_end": 4,
                        "batch_rounding_type": PriceTier.BatchRoundingType.NO_ROUNDING,
                        "type": PriceTier.PriceTierType.FREE,
                    }
                ],
                "reset_interval_unit": PlanComponent.IntervalLengthType.MONTH,
                "reset_interval_count": 1,
            },
        },
    )

    # PAY AS YOU GO PLAN -- unlimited BUT pay for what you use.. $0.01/GB/hour storage above 24*30*100 = 7200 GB/hr, $0.05 per GB data egress above 1000 GB, 100,000 rows/hour insert rate, $50 per month per 4GB RAM up to 32GB with 8 prepaid, $25 per month per 1 CPU up to 16 CPUs with 4 prepaid
    plan = Plan.objects.create(
        plan_name="Pay As You Go Plan",
        organization=organization,
        plan_duration=PLAN_DURATION.MONTHLY,
    )
    pay_as_you_go_bp_monthly = PlanVersion.objects.create(
        organization=organization,
        plan=plan,
        version=1,
        currency=free_bp.currency,
    )
    RecurringCharge.objects.create(
        organization=organization,
        plan_version=pay_as_you_go_bp_monthly,
        amount=100,
        name="Flat Rate",
        charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
        pricing_unit=pay_as_you_go_bp_monthly.currency,
    )
    plan_yearly = Plan.objects.create(
        plan_name="Pay As You Go Plan",
        organization=organization,
        plan_duration=PLAN_DURATION.YEARLY,
    )
    pay_as_you_go_bp_yearly = PlanVersion.objects.create(
        organization=organization,
        plan=plan_yearly,
        version=1,
        currency=free_bp.currency,
    )
    RecurringCharge.objects.create(
        organization=organization,
        plan_version=pay_as_you_go_bp_yearly,
        amount=1000,
        name="Flat Rate",
        charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
        pricing_unit=pay_as_you_go_bp_yearly.currency,
    )
    create_pc_plus_tiers_new(
        [pay_as_you_go_bp_monthly, pay_as_you_go_bp_yearly],
        pcs_dict={
            gb_storage: {
                "tiers": [
                    {
                        "range_start": 0,
                        "range_end": 4000,
                        "batch_rounding_type": PriceTier.BatchRoundingType.NO_ROUNDING,
                        "type": PriceTier.PriceTierType.FREE,
                    }
                ],
                "reset_interval_unit": PlanComponent.IntervalLengthType.MONTH,
                "reset_interval_count": 1,
            },
            gb_storage_hours: {
                "tiers": [
                    {
                        "range_start": 0,
                        "range_end": 7200,
                        "batch_rounding_type": PriceTier.BatchRoundingType.NO_ROUNDING,
                        "type": PriceTier.PriceTierType.FREE,
                    },
                    {
                        "range_start": 7200,
                        "range_end": 20000,
                        "batch_rounding_type": PriceTier.BatchRoundingType.NO_ROUNDING,
                        "type": PriceTier.PriceTierType.PER_UNIT,
                        "cost_per_batch": 0.0001,
                    },
                    {
                        "range_start": 20000,
                        "range_end": None,
                        "batch_rounding_type": PriceTier.BatchRoundingType.NO_ROUNDING,
                        "type": PriceTier.PriceTierType.PER_UNIT,
                        "cost_per_batch": 0.00005,
                    },
                ],
                "reset_interval_unit": PlanComponent.IntervalLengthType.MONTH,
                "reset_interval_count": 1,
            },
            data_egress: {
                "tiers": [
                    {
                        "range_start": 0,
                        "range_end": 1000,
                        "batch_rounding_type": PriceTier.BatchRoundingType.NO_ROUNDING,
                        "type": PriceTier.PriceTierType.FREE,
                    },
                    {
                        "range_start": 1000,
                        "range_end": None,
                        "batch_rounding_type": PriceTier.BatchRoundingType.NO_ROUNDING,
                        "type": PriceTier.PriceTierType.PER_UNIT,
                        "cost_per_batch": 0.05,
                    },
                ],
                "reset_interval_unit": PlanComponent.IntervalLengthType.MONTH,
                "reset_interval_count": 1,
            },
            insert_rate: {
                "tiers": [
                    {
                        "range_start": 0,
                        "range_end": 100_000,
                        "batch_rounding_type": PriceTier.BatchRoundingType.NO_ROUNDING,
                        "type": PriceTier.PriceTierType.FREE,
                    }
                ],
                "reset_interval_unit": PlanComponent.IntervalLengthType.MONTH,
                "reset_interval_count": 1,
            },
            gb_ram: {
                "tiers": [
                    {
                        "range_start": 0,
                        "range_end": 32,
                        "batch_rounding_type": PriceTier.BatchRoundingType.NO_ROUNDING,
                        "type": PriceTier.PriceTierType.PER_UNIT,
                        "cost_per_batch": 50,
                        "metric_units_per_batch": 4,
                    },
                ],
                "reset_interval_unit": PlanComponent.IntervalLengthType.MONTH,
                "reset_interval_count": 1,
                "prepaid_charge": {
                    "units": 8,
                    "charge_behavior": ComponentFixedCharge.ChargeBehavior.FULL,
                },
            },
            number_cpus: {
                "tiers": [
                    {
                        "range_start": 0,
                        "range_end": 16,
                        "batch_rounding_type": PriceTier.BatchRoundingType.NO_ROUNDING,
                        "type": PriceTier.PriceTierType.PER_UNIT,
                        "cost_per_batch": 25,
                        "metric_units_per_batch": 1,
                    },
                ],
                "reset_interval_unit": PlanComponent.IntervalLengthType.MONTH,
                "reset_interval_count": 1,
                "prepaid_charge": {
                    "units": 4,
                    "charge_behavior": ComponentFixedCharge.ChargeBehavior.FULL,
                },
            },
        },
    )
    n_months = 4 if size == "small" else 12
    start_of_sim = now_utc() - relativedelta(months=n_months) - relativedelta(days=5)
    for cust_set_name, cust_set in [
        ("big", big_customers),
        ("medium", medium_customers),
        ("small", small_customers),
    ]:
        plan_dict = {
            "big": [(0, basic_bp_monthly), (1 / 3, pay_as_you_go_bp_monthly)],
            "medium": [
                (0, free_bp),
                (1 / 6, basic_bp_monthly),
                (1 / 2, pay_as_you_go_bp_monthly),
            ],
            "small": [(0, free_bp), (1 / 3, basic_bp_monthly)],
        }
        for customer in cust_set:
            offset = np.random.randint(0, 30)
            beginning = start_of_sim + relativedelta(days=offset)
            for months in range(n_months):
                sub_start = beginning + relativedelta(months=months)
                cur_pct = (months + 1) / n_months
                for i in range(len(plan_dict[cust_set_name])):
                    lower_bound = plan_dict[cust_set_name][i][0]
                    upper_bound = (
                        plan_dict[cust_set_name][i + 1][0]
                        if i + 1 < len(plan_dict[cust_set_name])
                        else float("inf")
                    )
                    if lower_bound < cur_pct <= upper_bound:
                        plan = plan_dict[cust_set_name][i][1]
                        break
                # number of gauge events is irrespective
                n_storage_events = max(int(random.gauss(100, 20) // 1), 1)
                n_gb_ram_events = max(int(random.gauss(20, 3) // 1), 1)
                n_cpu_events = max(int(random.gauss(10, 2) // 1), 1)
                if plan == free_bp:
                    max_storage = 10
                    max_gb_ram = 4
                    max_cpus = 2
                    max_egress = 100
                    max_insert_rate = 1000
                elif plan == basic_bp_monthly:
                    max_storage = 100
                    max_gb_ram = 8
                    max_cpus = 4
                    max_egress = 1000
                    max_insert_rate = 10_000
                else:
                    max_storage = 4000
                    max_gb_ram = 32
                    max_cpus = 16
                    max_egress = 10_000
                    max_insert_rate = 100_000
                if cust_set_name == "big":
                    pct_of_max__mean = 0.8
                elif cust_set_name == "medium":
                    pct_of_max__mean = 0.6
                else:
                    pct_of_max__mean = 0.6
                if months == 0:
                    sr = make_subscription_record(
                        organization=organization,
                        customer=customer,
                        plan=plan,
                        start_date=sub_start,
                        is_new=months == 0,
                    )
                else:
                    sr = SubscriptionRecord.objects.get(
                        organization=organization,
                        customer=customer,
                        start_date__gt=sr.start_date,
                    )
                # ALL EVENTS
                events = []
                # storage events
                dts = list(random_date(sr.start_date, sr.end_date, n_storage_events))
                for dt in dts:
                    gb_storage = (
                        min(random.gauss(pct_of_max__mean, 0.05), 1) * max_storage
                    )
                    e = Event(
                        organization=organization,
                        event_name="storage_change",
                        properties={
                            "gb_storage": gb_storage,
                        },
                        time_created=dt,
                        idempotency_id=uuid.uuid4().hex,
                        cust_id=customer.customer_id,
                    )
                    events.append(e)
                # gb ram events
                dts = list(random_date(sr.start_date, sr.end_date, n_gb_ram_events))
                for dt in dts:
                    gb_ram = min(random.gauss(pct_of_max__mean, 0.05), 1) * max_gb_ram
                    e = Event(
                        organization=organization,
                        event_name="ram_change",
                        properties={
                            "gb_ram": gb_ram,
                        },
                        time_created=dt,
                        idempotency_id=uuid.uuid4().hex,
                        cust_id=customer.customer_id,
                    )
                    events.append(e)
                # cpu events
                dts = list(random_date(sr.start_date, sr.end_date, n_cpu_events))
                for dt in dts:
                    number_cpus = (
                        min(random.gauss(pct_of_max__mean, 0.05), 1) * max_cpus
                    )
                    e = Event(
                        organization=organization,
                        event_name="cpu_change",
                        properties={
                            "number_cpus": number_cpus,
                        },
                        time_created=dt,
                        idempotency_id=uuid.uuid4().hex,
                        cust_id=customer.customer_id,
                    )
                    events.append(e)
                # data egress events
                target_egress = (
                    min(random.gauss(pct_of_max__mean, 0.05), 1) * max_egress
                )
                cur_egress = 0
                n_egress_events = 0
                while cur_egress < target_egress:
                    dt = next(random_date(sr.start_date, sr.end_date, 1))
                    egress = np.random.random() * 25
                    if cur_egress + egress > target_egress:
                        break
                    e = Event(
                        organization=organization,
                        event_name="data_egress",
                        properties={
                            "gb_data_egress": egress,
                        },
                        time_created=dt,
                        idempotency_id=uuid.uuid4().hex,
                        cust_id=customer.customer_id,
                    )
                    events.append(e)
                    cur_egress += egress
                    n_egress_events += 1
                # db insert events
                target_rows = (
                    min(random.gauss(pct_of_max__mean, 0.05), 1) * max_insert_rate * 10
                )
                cur_rows = 0
                n_insert_events = 0
                while cur_rows < target_rows:
                    dt = next(random_date(sr.start_date, sr.end_date, 1))
                    rows = np.random.random() * 800
                    if cur_rows + rows > target_rows:
                        break
                    e = Event(
                        organization=organization,
                        event_name="db_insert",
                        properties={
                            "num_rows": rows,
                        },
                        time_created=dt,
                        idempotency_id=uuid.uuid4().hex,
                        cust_id=customer.customer_id,
                    )
                    events.append(e)
                    cur_rows += rows
                    n_insert_events += 1
                # cost events
                total_events = (
                    n_cpu_events + n_gb_ram_events + n_storage_events + n_egress_events
                )
                n_cost_events = total_events // 10
                dts = list(random_date(sr.start_date, sr.end_date, n_cost_events))
                for dt in dts:
                    cost = np.random.random() * 8
                    e = Event(
                        organization=organization,
                        event_name="server_costs",
                        properties={
                            "cost": cost,
                        },
                        time_created=dt,
                        idempotency_id=uuid.uuid4().hex,
                        cust_id=customer.customer_id,
                    )
                    events.append(e)

                next_pct = (months + 2) / n_months
                for i in range(len(plan_dict[cust_set_name])):
                    lower_bound = plan_dict[cust_set_name][i][0]
                    upper_bound = (
                        plan_dict[cust_set_name][i + 1][0]
                        if i + 1 < len(plan_dict[cust_set_name])
                        else float("inf")
                    )
                    if lower_bound < next_pct <= upper_bound:
                        next_plan = plan_dict[cust_set_name][i][1]
                        break
                Event.objects.bulk_create(events)
                if months == 0:
                    generate_invoice(
                        [sr],
                        issue_date=sr.start_date,
                    )
                if now_utc() > sr.end_date:
                    cur_bp = sr.billing_plan
                    cur_replace_with = cur_bp.replace_with
                    cur_bp.replace_with = next_plan
                    cur_bp.save()
                    generate_invoice(
                        [sr],
                        issue_date=sr.end_date,
                        charge_next_plan=True,
                        generate_next_subscription_record=True,
                    )
                    cur_bp.replace_with = cur_replace_with
                    cur_bp.save()

    return user


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
            type=PriceTier.PriceTierType.FREE,
            organization=organization,
        )
        range_start = free_units
    if cost_per_batch is not None:
        PriceTier.objects.create(
            plan_component=pc,
            range_start=range_start,
            range_end=max_units,
            type=PriceTier.PriceTierType.PER_UNIT,
            cost_per_batch=cost_per_batch,
            metric_units_per_batch=metric_units_per_batch,
            organization=organization,
            batch_rounding_type=PriceTier.BatchRoundingType.NO_ROUNDING,
        )


def random_date(start, end, n):
    """Generate a random datetime between `start` and `end`"""
    if type(start) is datetime.date:
        start = date_as_min_dt(start, timezone=pytz.UTC)
    if type(end) is datetime.date:
        end = date_as_max_dt(end, timezone=pytz.UTC)
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


def make_subscription_record(
    organization,
    customer,
    plan,
    start_date,
    is_new,
):
    sr = SubscriptionRecord.create_subscription_record(
        start_date=start_date,
        end_date=None,
        billing_plan=plan,
        customer=customer,
        organization=organization,
        subscription_filters=None,
        is_new=is_new,
        quantity=1,
        do_generate_invoice=False,
    )
    return sr


def create_pc_plus_tiers_new(plan_versions, pcs_dict):
    for plan_version in plan_versions:
        for metric, pc_info in pcs_dict.items():
            pc = PlanComponent.objects.create(
                plan_version=plan_version,
                billable_metric=metric,
                organization=plan_version.organization,
                pricing_unit=plan_version.currency,
                invoicing_interval_unit=pc_info.get("invoicing_interval_unit"),
                invoicing_interval_count=pc_info.get("invoicing_interval_count"),
                reset_interval_unit=pc_info.get("reset_interval_unit"),
                reset_interval_count=pc_info.get("reset_interval_count"),
            )
            if pc_info.get("fixed_charge"):
                fc = ComponentFixedCharge.objects.create(
                    organization=plan_version.organization,
                    units=pc_info.get("units"),
                    charge_behavior=pc_info.get("charge_behavior"),
                )
                pc.fixed_charge = fc
                pc.save()
            if pc_info.get("tiers"):
                for tier in pc_info.get("tiers"):
                    PriceTier.objects.create(
                        plan_component=pc,
                        range_start=tier.get("range_start"),
                        range_end=tier.get("range_end"),
                        type=tier.get("type"),
                        cost_per_batch=tier.get("cost_per_batch"),
                        metric_units_per_batch=tier.get("metric_units_per_batch", 1),
                        organization=plan_version.organization,
                        batch_rounding_type=tier.get("batch_rounding_type"),
                    )
