import logging
import uuid

from django.core.management.base import BaseCommand
from metering_billing.aggregation.billable_metrics import METRIC_HANDLER_MAP
from metering_billing.demos import create_pc_and_tiers, make_subscription_record
from metering_billing.invoice import generate_invoice
from metering_billing.models import (
    AddOnSpecification,
    Customer,
    CustomerBalanceAdjustment,
    Feature,
    Organization,
    Plan,
    PlanVersion,
    PricingUnit,
    RecurringCharge,
)
from metering_billing.serializers.model_serializers import APITokenSerializer
from metering_billing.utils import now_utc
from metering_billing.utils.enums import (
    EVENT_TYPE,
    METRIC_TYPE,
    PLAN_DURATION,
    PLAN_VERSION_STATUS,
)

logger = logging.getLogger("django.server")


class Command(BaseCommand):
    "Django command to execute calculate invoice"

    def handle(self, *args, **options):
        organization = Organization.objects.create(
            organization_name="test",
        )
        organization.update_subscription_filter_settings(["region"])
        Customer.objects.create(
            organization=organization, customer_name="test", email="test@test.com"
        )

        # API key
        _, key = APITokenSerializer().create(
            {
                "name": "test",
                "organization": organization,
            }
        )
        print(f"KEY={key}")

        # plan
        customer = Customer.objects.create(
            organization=organization,
            customer_name="BigCompany " + str(uuid.uuid4().hex)[:6],
            email=f"{str(uuid.uuid4().hex)}@{str(uuid.uuid4().hex)}.com",
        )
        metrics_map = {}
        for property_name, usage_aggregation_type, billable_metric_name, name in zip(
            [None, "words", "compute_time", "language", "subsection"],
            ["count", "sum", "sum", "unique", "unique"],
            ["API Calls", "Words", "Compute Time", "Unique Languages", "Content Types"],
            ["calls", "sum_words", "sum_compute", "unique_lang", "unique_subsections"],
        ):
            validated_data = {
                "organization": organization,
                "event_name": "test_event",
                "property_name": property_name,
                "usage_aggregation_type": usage_aggregation_type,
                "billable_metric_name": billable_metric_name,
                "metric_type": METRIC_TYPE.COUNTER,
            }
            metric = METRIC_HANDLER_MAP[METRIC_TYPE.COUNTER].create_metric(
                validated_data
            )
            metrics_map[name] = metric
        for property_name, usage_aggregation_type, billable_metric_name, name in zip(
            ["qty"], ["max"], ["User Seats"], ["num_seats"]
        ):
            validated_data = {
                "organization": organization,
                "event_name": "test_event",
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
                "event_name": "test_event",
                "property_name": property_name,
                "usage_aggregation_type": usage_aggregation_type,
                "billable_metric_name": billable_metric_name,
                "metric_type": METRIC_TYPE.COUNTER,
                "is_cost_metric": True,
            }
            metric = METRIC_HANDLER_MAP[METRIC_TYPE.COUNTER].create_metric(
                validated_data
            )
            assert metric is not None
            metrics_map[name] = metric
        metrics_map["calls"]
        sum_words = metrics_map["sum_words"]
        metrics_map["sum_compute"]
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
            organization,
            plan_version=free_bp,
            billable_metric=sum_words,
            free_units=2_000,
        )
        create_pc_and_tiers(
            organization,
            plan_version=free_bp,
            billable_metric=num_seats,
            free_units=1,
        )
        pc = free_bp.plan_components.all().first()
        tier = pc.tiers.all().first()
        tier.range_end = None
        tier.save()
        plan.save()

        print(f"PLAN_ID=plan_{plan.plan_id.hex}")

        sr = make_subscription_record(
            organization=organization,
            customer=customer,
            plan=free_bp,
            start_date=now_utc(),
            is_new=True,
        )

        # invoice
        invoice = generate_invoice(sr, draft=True)[0]
        print(f"INVOICE_ID=invoice_{invoice.invoice_id.hex}")

        # credit
        CustomerBalanceAdjustment.objects.create(
            organization=organization,
            customer=customer,
            amount=100,
        )

        # addon
        premium_support_feature = Feature.objects.create(
            organization=organization,
            feature_name="test_feature",
            feature_description="premium support",
        )
        flat_fee_addon_spec = AddOnSpecification.objects.create(
            organization=organization,
            billing_frequency=AddOnSpecification.BillingFrequency.ONE_TIME,
            flat_fee_invoicing_behavior_on_attach=AddOnSpecification.FlatFeeInvoicingBehaviorOnAttach.INVOICE_ON_ATTACH,
        )
        flat_fee_addon = Plan.objects.create(
            organization=organization,
            plan_name="flat_fee_addon",
            addon_spec=flat_fee_addon_spec,
        )
        flat_fee_addon_version = PlanVersion.objects.create(
            organization=organization,
            description="flat_fee_addon",
            plan=flat_fee_addon,
            status=PLAN_VERSION_STATUS.ACTIVE,
        )
        RecurringCharge.objects.create(
            organization=plan.organization,
            plan_version=flat_fee_addon_version,
            charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
            charge_behavior=RecurringCharge.ChargeBehaviorType.PRORATE,
            amount=10,
            pricing_unit=flat_fee_addon_version.currency,
        )
        flat_fee_addon_version.features.add(premium_support_feature)
        print(f"ADDON_ID=addon_{flat_fee_addon.plan_id.hex}")

        # metric + feature
        print(f"METRIC_ID=metric_{sum_words.metric_id.hex}")
        unused_metric = metrics_map["unique_lang"]
        print(f"UNUSED_MID=metric_{unused_metric.metric_id.hex}")
        print(f"FEATURE_ID=feature_{premium_support_feature.feature_id.hex}")
        print(f"EVENT_NAME={sum_words.event_name}")
        print(f"FEATURE_NAME={premium_support_feature.feature_name}")

        # custometr
        print(f"CUSTOMER_ID={customer.customer_id}")
        logger.info("Done creating test data")
