import itertools
import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from metering_billing.aggregation.billable_metrics import METRIC_HANDLER_MAP
from metering_billing.models import (
    BillingRecord,
    Event,
    Invoice,
    Metric,
    Plan,
    PlanComponent,
    PlanVersion,
    PriceTier,
    PricingUnit,
    RecurringCharge,
    SubscriptionRecord,
)
from metering_billing.serializers.serializer_utils import DjangoJSONEncoder
from metering_billing.utils import now_utc
from metering_billing.utils.enums import (
    CHARGEABLE_ITEM_TYPE,
    FLAT_FEE_BEHAVIOR,
    INVOICING_BEHAVIOR,
    PLAN_DURATION,
    USAGE_BEHAVIOR,
)
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APIClient


@pytest.fixture
def subscription_test_common_setup(
    generate_org_and_api_key,
    add_users_to_org,
    api_client_with_api_key_auth,
    add_subscription_record_to_org,
    add_customers_to_org,
    add_product_to_org,
    add_plan_to_product,
):
    def do_subscription_test_common_setup(
        *, num_subscriptions, auth_method, user_org_and_api_key_org_different=False
    ):
        # set up organizations and api keys
        org, key = generate_org_and_api_key()
        org2, key2 = generate_org_and_api_key()
        setup_dict = {
            "org": org,
            "key": key,
            "org2": org2,
            "key2": key2,
        }
        # set up the client with the appropriate api key spec
        if auth_method == "api_key":
            client = api_client_with_api_key_auth(key)
        elif auth_method == "session_auth":
            client = APIClient()
            (user,) = add_users_to_org(org, n=1)
            client.force_authenticate(user=user)
            setup_dict["user"] = user
        else:
            client = api_client_with_api_key_auth(key)
            if user_org_and_api_key_org_different:
                (user,) = add_users_to_org(org2, n=1)
            else:
                (user,) = add_users_to_org(org, n=1)
            client.force_authenticate(user=user)
            setup_dict["user"] = user
        setup_dict["client"] = client

        metric_set = baker.make(
            Metric,
            organization=org,
            event_name="email_sent",
            property_name=itertools.cycle(["num_characters", "peak_bandwith", ""]),
            usage_aggregation_type=itertools.cycle(["sum", "max", "count"]),
            billable_metric_name=itertools.cycle(
                ["count_chars", "peak_bandwith", "email_sent"]
            ),
            _quantity=3,
        )
        for metric in metric_set:
            METRIC_HANDLER_MAP[metric.metric_type].create_continuous_aggregate(metric)
        setup_dict["metrics"] = metric_set
        product = add_product_to_org(org)
        setup_dict["product"] = product
        plan = add_plan_to_product(product)
        setup_dict["plan"] = plan
        billing_plan = baker.make(
            PlanVersion,
            organization=org,
            plan=plan,
            currency=PricingUnit.objects.get(organization=org, code="USD"),
        )
        plan.save()
        for i, (fmu, cpb, mupb) in enumerate(
            zip([50, 0, 1], [5, 0.05, 2], [100, 1, 1])
        ):
            pc = PlanComponent.objects.create(
                plan_version=billing_plan,
                billable_metric=metric_set[i],
            )
            start = 0
            if fmu > 0:
                PriceTier.objects.create(
                    plan_component=pc,
                    type=PriceTier.PriceTierType.FREE,
                    range_start=0,
                    range_end=fmu,
                )
                start = fmu
            PriceTier.objects.create(
                plan_component=pc,
                type=PriceTier.PriceTierType.PER_UNIT,
                range_start=start,
                cost_per_batch=cpb,
                metric_units_per_batch=mupb,
            )
        setup_dict["billing_plan"] = billing_plan

        (customer,) = add_customers_to_org(org, n=1)
        if num_subscriptions > 0:
            setup_dict["org_subscription"] = add_subscription_record_to_org(
                org, billing_plan, customer
            )
        payload = {
            "start_date": now_utc() - timedelta(days=5),
            "customer_id": customer.customer_id,
            "version_id": billing_plan.version_id,
        }
        setup_dict["payload"] = payload
        setup_dict["customer"] = customer

        return setup_dict

    return do_subscription_test_common_setup


@pytest.mark.django_db(transaction=True)
class TestCreateSubscription:
    def test_api_key_can_create_subscription_empty_before(
        self, subscription_test_common_setup, get_subscription_records_in_org
    ):
        # covers num_subscriptions_before_insert = 0, has_org_api_key=true, user_in_org=true, user_org_and_api_key_org_different=false
        num_subscriptions = 0
        setup_dict = subscription_test_common_setup(
            num_subscriptions=num_subscriptions,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )

        response = setup_dict["client"].post(
            reverse("subscription-list"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0  # check that the response is not empty
        assert len(get_subscription_records_in_org(setup_dict["org"])) == 1

    def test_session_auth_can_create_subscription_nonempty_before(
        self,
        subscription_test_common_setup,
        get_subscription_records_in_org,
        add_customers_to_org,
    ):
        # covers num_subscriptions_before_insert = 0, has_org_api_key=true, user_in_org=true, user_org_and_api_key_org_different=false, authenticated=true
        num_subscriptions = 1
        setup_dict = subscription_test_common_setup(
            num_subscriptions=num_subscriptions,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )
        num_subscription_records_before = len(
            get_subscription_records_in_org(setup_dict["org"])
        )

        setup_dict["org"].update_subscription_filter_settings(["email"])

        setup_dict["payload"]["start_date"] = now_utc()
        setup_dict["payload"]["subscription_filters"] = [
            {"property_name": "email", "value": "123"}
        ]
        (customer,) = add_customers_to_org(setup_dict["org"], n=1)
        setup_dict["payload"]["customer_id"] = customer.customer_id
        response = setup_dict["client"].post(
            reverse("subscription-list"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0
        assert (
            len(get_subscription_records_in_org(setup_dict["org"]))
            == num_subscriptions + 1
        )
        assert (
            len(get_subscription_records_in_org(setup_dict["org"]))
            == num_subscription_records_before + 1
        )

    def test_reject_overlapping_subscriptions(
        self, subscription_test_common_setup, get_subscription_records_in_org
    ):
        # covers num_subscriptions_before_insert = 0, has_org_api_key=true, user_in_org=true, user_org_and_api_key_org_different=false
        num_subscriptions = 0
        setup_dict = subscription_test_common_setup(
            num_subscriptions=num_subscriptions,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )

        response = setup_dict["client"].post(
            reverse("subscription-list"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0  # check that the response is not empty
        assert len(get_subscription_records_in_org(setup_dict["org"])) == 1

        response = setup_dict["client"].post(
            reverse("subscription-list"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert len(response.data) > 0  # check that the response is not empty
        assert len(get_subscription_records_in_org(setup_dict["org"])) == 1


@pytest.mark.django_db(transaction=True)
class TestUpdateSub:
    def test_end_subscription_generate_invoice(self, subscription_test_common_setup):
        setup_dict = subscription_test_common_setup(
            num_subscriptions=1, auth_method="session_auth"
        )

        prev_invoices_len = Invoice.objects.all().count()
        sub = SubscriptionRecord.objects.all()[0]
        payload = {
            "flat_fee_behavior": FLAT_FEE_BEHAVIOR.CHARGE_FULL,
            "bill_usage": True,
        }
        response = setup_dict["client"].post(
            reverse(
                "subscription-cancel",
                kwargs={
                    "subscription_id": sub.subscription_record_id,
                },
            ),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        new_invoices_len = Invoice.objects.all().count()
        assert response.status_code == status.HTTP_200_OK
        assert new_invoices_len == prev_invoices_len + 1

    def test_end_subscription_dont_generate_invoice(
        self, subscription_test_common_setup
    ):
        setup_dict = subscription_test_common_setup(
            num_subscriptions=1, auth_method="session_auth"
        )

        active_subscriptions = SubscriptionRecord.objects.active().filter(
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        )
        prev_invoices_len = Invoice.objects.all().count()
        assert len(active_subscriptions) == 1

        sub = SubscriptionRecord.objects.all()[0]
        payload = {
            "flat_fee_behavior": FLAT_FEE_BEHAVIOR.CHARGE_FULL,
            "invoicing_behavior": INVOICING_BEHAVIOR.ADD_TO_NEXT_INVOICE,
        }
        response = setup_dict["client"].post(
            reverse(
                "subscription-cancel",
                kwargs={
                    "subscription_id": sub.subscription_record_id,
                },
            ),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        after_active_subscriptions = SubscriptionRecord.objects.active().filter(
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        )
        after_canceled_subscriptions = SubscriptionRecord.objects.ended().filter(
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        )
        new_invoices_len = Invoice.objects.all().count()
        assert response.status_code == status.HTTP_200_OK
        assert len(after_active_subscriptions) + 1 == len(active_subscriptions)
        assert len(after_canceled_subscriptions) == 1
        assert new_invoices_len == prev_invoices_len

    def test_cancel_auto_renew(self, subscription_test_common_setup):
        setup_dict = subscription_test_common_setup(
            num_subscriptions=1, auth_method="session_auth"
        )

        autorenew_subscription_records = SubscriptionRecord.objects.filter(
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
            auto_renew=True,
        )
        prev_invoices_len = Invoice.objects.all().count()
        assert len(autorenew_subscription_records) == 1

        payload = {
            "turn_off_auto_renew": True,
        }
        sub = SubscriptionRecord.objects.all()[0]
        response = setup_dict["client"].post(
            reverse(
                "subscription-update",
                kwargs={
                    "subscription_id": sub.subscription_record_id,
                },
            ),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        after_autorenew_subscription_records = (
            SubscriptionRecord.objects.active().filter(
                organization=setup_dict["org"],
                customer=setup_dict["customer"],
                auto_renew=True,
            )
        )
        new_invoices_len = Invoice.objects.all().count()

        assert response.status_code == status.HTTP_200_OK
        assert len(after_autorenew_subscription_records) + 1 == len(
            autorenew_subscription_records
        )
        assert new_invoices_len == prev_invoices_len

    def test_switch_plan_with_different_duration_fails(
        self, subscription_test_common_setup
    ):
        setup_dict = subscription_test_common_setup(
            num_subscriptions=0, auth_method="session_auth"
        )

        prev_subscription_records_len = SubscriptionRecord.objects.all().count()
        assert prev_subscription_records_len == 0

        payload = {
            "name": "test_subscription",
            "start_date": now_utc() - timedelta(days=5),
            "customer_id": setup_dict["customer"].customer_id,
            "plan_id": setup_dict["billing_plan"].plan.plan_id,
        }
        response = setup_dict["client"].post(
            reverse("subscription-list"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        after_subscription_records_len = SubscriptionRecord.objects.all().count()

        assert response.status_code == status.HTTP_201_CREATED
        assert after_subscription_records_len == prev_subscription_records_len + 1

        baker.make(
            Event,
            organization=setup_dict["org"],
            cust_id=setup_dict["customer"].customer_id,
            event_name="email_sent",
            time_created=now_utc() - timedelta(days=3),
            properties={},
            _quantity=20,
        )

        new_plan = Plan.objects.create(
            organization=setup_dict["org"],
            plan_name="yearly plan",
            plan_duration=PLAN_DURATION.YEARLY,
        )
        Invoice.objects.all().count()

        pv = baker.make(
            PlanVersion,
            organization=setup_dict["org"],
            plan=new_plan,
        )
        payload = {
            "new_version_id": pv.version_id,
        }
        sub = SubscriptionRecord.objects.all()[0]
        response = setup_dict["client"].post(
            reverse(
                "subscription-switch_plan",
                kwargs={
                    "subscription_id": sub.subscription_record_id,
                },
            ),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        Invoice.objects.all().count()
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_switch_plan_transfers_usage_by_default(
        self, subscription_test_common_setup
    ):
        setup_dict = subscription_test_common_setup(
            num_subscriptions=0, auth_method="session_auth"
        )

        prev_subscription_records_len = SubscriptionRecord.objects.all().count()
        assert prev_subscription_records_len == 0

        payload = {
            "name": "test_subscription",
            "start_date": now_utc() - timedelta(days=5),
            "customer_id": setup_dict["customer"].customer_id,
            "plan_id": setup_dict["billing_plan"].plan.plan_id,
        }
        response = setup_dict["client"].post(
            reverse("subscription-list"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        after_subscription_records_len = SubscriptionRecord.objects.all().count()

        assert response.status_code == status.HTTP_201_CREATED
        assert after_subscription_records_len == prev_subscription_records_len + 1

        baker.make(
            Event,
            organization=setup_dict["org"],
            cust_id=setup_dict["customer"].customer_id,
            event_name="emails_sent",
            time_created=now_utc() - timedelta(days=3),
            properties={},
            _quantity=20,
        )

        new_plan = Plan.objects.create(
            organization=setup_dict["org"],
            plan_name="yearly plan",
            plan_duration=PLAN_DURATION.MONTHLY,
        )
        before_invoices = Invoice.objects.all().count()

        pv = baker.make(
            PlanVersion,
            organization=setup_dict["org"],
            plan=new_plan,
            currency=PricingUnit.objects.get(
                code="USD", organization=setup_dict["org"]
            ),
        )
        new_plan.save()
        for i, (fmu, cpb, mupb) in enumerate(
            zip([50, 0, 1], [5, 0.05, 2], [100, 1, 1])
        ):
            pc = PlanComponent.objects.create(
                plan_version=pv,
                billable_metric=setup_dict["metrics"][i],
            )
            start = 0
            if fmu > 0:
                PriceTier.objects.create(
                    plan_component=pc,
                    type=PriceTier.PriceTierType.FREE,
                    range_start=0,
                    range_end=fmu,
                )
                start = fmu
            PriceTier.objects.create(
                plan_component=pc,
                type=PriceTier.PriceTierType.PER_UNIT,
                range_start=start,
                cost_per_batch=cpb,
                metric_units_per_batch=mupb,
            )
        payload = {
            "new_version_id": pv.version_id,
        }
        sub = SubscriptionRecord.objects.all()[0]
        response = setup_dict["client"].post(
            reverse(
                "subscription-switch_plan",
                kwargs={
                    "subscription_id": sub.subscription_record_id,
                },
            ),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        after_invoices = Invoice.objects.all().count()
        # no new invoices since we transferred all the usage and that shouldn't have intermediate invoiced
        assert before_invoices == after_invoices
        assert sub.billing_records.count() == 0  # all transferred away!
        new_sr = SubscriptionRecord.objects.all().order_by("-id").first()
        assert new_sr.billing_records.count() == 3  # all transferred away!

    def test_keep_usage_separate_on_plan_transfer(self, subscription_test_common_setup):
        setup_dict = subscription_test_common_setup(
            num_subscriptions=0, auth_method="session_auth"
        )

        prev_subscription_records_len = SubscriptionRecord.objects.all().count()
        assert prev_subscription_records_len == 0

        payload = {
            "name": "test_subscription",
            "start_date": now_utc() - timedelta(days=5),
            "customer_id": setup_dict["customer"].customer_id,
            "plan_id": setup_dict["billing_plan"].plan.plan_id,
        }
        response = setup_dict["client"].post(
            reverse("subscription-list"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        after_subscription_records_len = SubscriptionRecord.objects.all().count()

        assert response.status_code == status.HTTP_201_CREATED
        assert after_subscription_records_len == prev_subscription_records_len + 1

        baker.make(
            Event,
            organization=setup_dict["org"],
            cust_id=setup_dict["customer"].customer_id,
            event_name="email_sent",
            time_created=now_utc() - timedelta(days=3),
            properties={},
            _quantity=20,
        )

        new_plan = Plan.objects.create(
            organization=setup_dict["org"],
            plan_name="yearly plan",
            plan_duration=PLAN_DURATION.MONTHLY,
        )
        before_invoices = Invoice.objects.all().count()

        pv = baker.make(
            PlanVersion,
            organization=setup_dict["org"],
            plan=new_plan,
            currency=PricingUnit.objects.get(
                code="USD", organization=setup_dict["org"]
            ),
        )
        new_plan.save()
        for i, (fmu, cpb, mupb) in enumerate(
            zip([50, 0, 1], [5, 0.05, 2], [100, 1, 1])
        ):
            pc = PlanComponent.objects.create(
                plan_version=pv,
                billable_metric=setup_dict["metrics"][i],
            )
            start = 0
            if fmu > 0:
                PriceTier.objects.create(
                    plan_component=pc,
                    type=PriceTier.PriceTierType.FREE,
                    range_start=0,
                    range_end=fmu,
                )
                start = fmu
            PriceTier.objects.create(
                plan_component=pc,
                type=PriceTier.PriceTierType.PER_UNIT,
                range_start=start,
                cost_per_batch=cpb,
                metric_units_per_batch=mupb,
            )
        payload = {
            "new_version_id": pv.version_id,
            "usage_behavior": USAGE_BEHAVIOR.KEEP_SEPARATE,
        }
        sub = SubscriptionRecord.objects.all()[0]
        response = setup_dict["client"].post(
            reverse(
                "subscription-switch_plan",
                kwargs={
                    "subscription_id": sub.subscription_record_id,
                },
            ),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        after_invoices = Invoice.objects.all().count()
        assert before_invoices + 1 == after_invoices
        most_recent_invoice = Invoice.objects.all().order_by("-id").first()
        assert CHARGEABLE_ITEM_TYPE.USAGE_CHARGE in list(
            most_recent_invoice.line_items.all().values_list(
                "chargeable_item_type", flat=True
            )
        )
        new_sr = SubscriptionRecord.objects.all().order_by("-id").first()
        assert (
            sub.billing_records.count() == 3
        )  # not transferred, just ended + restarted
        assert new_sr.billing_records.count() == 3  # all new ones


@pytest.mark.django_db(transaction=True)
class TestRegressions:
    def test_list_serializer_on_subs_not_valid(self, subscription_test_common_setup):
        setup_dict = subscription_test_common_setup(
            num_subscriptions=0, auth_method="session_auth"
        )

        prev_subscription_records_len = SubscriptionRecord.objects.all().count()
        assert prev_subscription_records_len == 0

        response = setup_dict["client"].post(
            reverse("subscription-list"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        after_subscription_records_len = SubscriptionRecord.objects.all().count()

        assert response.status_code == status.HTTP_201_CREATED
        assert after_subscription_records_len == prev_subscription_records_len + 1
        payload = {
            "customer_id": setup_dict["customer"].customer_id,
        }
        response = setup_dict["client"].get(reverse("subscription-list"), payload)
        assert response.status_code == status.HTTP_200_OK
        payload = {
            "customer_id": "1234567890fcfghjkldscfvgbhjo",
        }
        response = setup_dict["client"].get(reverse("subscription-list"), payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_refresh_rate_metric_doesnt_fail(self, subscription_test_common_setup):
        from metering_billing.utils.enums import (
            METRIC_AGGREGATION,
            METRIC_GRANULARITY,
            METRIC_TYPE,
        )

        setup_dict = subscription_test_common_setup(
            num_subscriptions=0, auth_method="session_auth"
        )
        Metric.objects.create(
            organization=setup_dict["org"],
            event_name="rows_inserted",
            property_name="num_rows",
            usage_aggregation_type=METRIC_AGGREGATION.SUM,
            billable_aggregation_type=METRIC_AGGREGATION.MAX,
            metric_type=METRIC_TYPE.RATE,
            granularity=METRIC_GRANULARITY.DAY,
        )
        try:
            setup_dict["org"].update_subscription_filter_settings(["email"])
        except Exception as e:
            assert False, e


@pytest.mark.django_db(transaction=True)
class TestResetAndInvoicingIntervals:
    def test_monthly_plan_with_weekly_invoicing_creates_correct_number_of_billing_records_for_pcs(
        self,
        subscription_test_common_setup,
    ):
        num_subscriptions = 0
        setup_dict = subscription_test_common_setup(
            num_subscriptions=num_subscriptions,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )
        customer = setup_dict["customer"]
        PlanVersion.objects.all().delete()
        billing_plan = baker.make(
            PlanVersion,
            organization=setup_dict["org"],
            plan=setup_dict["plan"],
            currency=PricingUnit.objects.get(
                organization=setup_dict["org"], code="USD"
            ),
        )
        for i, (fmu, cpb, mupb) in enumerate(
            zip([50, 0, 1], [5, 0.05, 2], [100, 1, 1])
        ):
            pc = PlanComponent.objects.create(
                plan_version=billing_plan,
                billable_metric=setup_dict["metrics"][i],
                invoicing_interval_unit=PlanComponent.IntervalLengthType.WEEK,
                invoicing_interval_count=1,
            )
            start = 0
            if fmu > 0:
                PriceTier.objects.create(
                    plan_component=pc,
                    type=PriceTier.PriceTierType.FREE,
                    range_start=0,
                    range_end=fmu,
                )
                start = fmu
            PriceTier.objects.create(
                plan_component=pc,
                type=PriceTier.PriceTierType.PER_UNIT,
                range_start=start,
                cost_per_batch=cpb,
                metric_units_per_batch=mupb,
            )
        payload = {
            "start_date": now_utc() - timedelta(days=5),
            "customer_id": customer.customer_id,
            "version_id": billing_plan.version_id,
        }
        sr_before = SubscriptionRecord.objects.all().count()
        br_before = BillingRecord.objects.all().count()
        response = setup_dict["client"].post(
            reverse("subscription-list"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        sr_after = SubscriptionRecord.objects.all().count()
        br_after = BillingRecord.objects.all().count()
        assert response.status_code == status.HTTP_201_CREATED
        assert sr_after == sr_before + 1
        assert br_after == br_before + 3  # 3 billing records for 3 plan components
        new_br = BillingRecord.objects.all().order_by("-id").first()
        # new billign record should have a billing date at 7, 14, 21, 28 days from start date, plus end date, so 5
        assert len(new_br.invoicing_dates) == 5
        assert (
            new_br.next_invoicing_date == new_br.invoicing_dates[0]
        )  # no billing dates have passed
        assert new_br.fully_billed is False

    def test_monthly_plan_with_daily_reset_creates_correct_amount_of_billing_records_for_pcs(
        self,
        subscription_test_common_setup,
    ):
        num_subscriptions = 0
        setup_dict = subscription_test_common_setup(
            num_subscriptions=num_subscriptions,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )
        customer = setup_dict["customer"]
        PlanVersion.objects.all().delete()
        billing_plan = baker.make(
            PlanVersion,
            organization=setup_dict["org"],
            plan=setup_dict["plan"],
            currency=PricingUnit.objects.get(
                organization=setup_dict["org"], code="USD"
            ),
        )
        for i, (fmu, cpb, mupb) in enumerate(
            zip([50, 0, 1], [5, 0.05, 2], [100, 1, 1])
        ):
            pc = PlanComponent.objects.create(
                plan_version=billing_plan,
                billable_metric=setup_dict["metrics"][i],
                reset_interval_unit=PlanComponent.IntervalLengthType.DAY,
                reset_interval_count=1,
            )
            start = 0
            if fmu > 0:
                PriceTier.objects.create(
                    plan_component=pc,
                    type=PriceTier.PriceTierType.FREE,
                    range_start=0,
                    range_end=fmu,
                )
                start = fmu
            PriceTier.objects.create(
                plan_component=pc,
                type=PriceTier.PriceTierType.PER_UNIT,
                range_start=start,
                cost_per_batch=cpb,
                metric_units_per_batch=mupb,
            )
        payload = {
            "start_date": now_utc() - timedelta(days=5),
            "customer_id": customer.customer_id,
            "version_id": billing_plan.version_id,
        }
        sr_before = SubscriptionRecord.objects.all()
        sr_before_ct = len(sr_before)
        br_before = BillingRecord.objects.all()
        br_before_ct = len(br_before)
        response = setup_dict["client"].post(
            reverse("subscription-list"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        sr_after = SubscriptionRecord.objects.all()
        br_after = BillingRecord.objects.all()
        assert response.status_code == status.HTTP_201_CREATED
        assert sr_after.count() == sr_before_ct + 1
        assert (
            br_before_ct + 3 * 28 <= br_after.count() <= br_before_ct + 3 * 31
        )  # 3 billing records for 3 plan components, 28-31 days
        for br in br_after:
            assert len(br.invoicing_dates) == 1  # just the subscription end date!
            assert br.next_invoicing_date == br.invoicing_dates[0]
            assert br.fully_billed is False
            assert br.unadjusted_duration_microseconds == 86400000000 or (
                br.start_date == br.subscription.start_date
                or br.end_date == br.subscription.end_date
            )
            assert br.next_invoicing_date == br.subscription.end_date

    def test_monthly_plan_with_mixed_reset_and_invoicing_generates_correct_brs_for_pcs(
        self,
        subscription_test_common_setup,
    ):
        num_subscriptions = 0
        setup_dict = subscription_test_common_setup(
            num_subscriptions=num_subscriptions,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )
        customer = setup_dict["customer"]
        PlanVersion.objects.all().delete()
        billing_plan = baker.make(
            PlanVersion,
            organization=setup_dict["org"],
            plan=setup_dict["plan"],
            currency=PricingUnit.objects.get(
                organization=setup_dict["org"], code="USD"
            ),
        )
        for i, (fmu, cpb, mupb) in enumerate(
            zip([50, 0, 1], [5, 0.05, 2], [100, 1, 1])
        ):
            pc = PlanComponent.objects.create(
                plan_version=billing_plan,
                billable_metric=setup_dict["metrics"][i],
                reset_interval_unit=PlanComponent.IntervalLengthType.WEEK,
                reset_interval_count=1,
                invoicing_interval_unit=PlanComponent.IntervalLengthType.DAY,
                invoicing_interval_count=2,
            )
            start = 0
            if fmu > 0:
                PriceTier.objects.create(
                    plan_component=pc,
                    type=PriceTier.PriceTierType.FREE,
                    range_start=0,
                    range_end=fmu,
                )
                start = fmu
            PriceTier.objects.create(
                plan_component=pc,
                type=PriceTier.PriceTierType.PER_UNIT,
                range_start=start,
                cost_per_batch=cpb,
                metric_units_per_batch=mupb,
            )
        payload = {
            "start_date": now_utc() - timedelta(days=5),
            "customer_id": customer.customer_id,
            "version_id": billing_plan.version_id,
        }
        sr_before = SubscriptionRecord.objects.all()
        sr_before_ct = len(sr_before)
        br_before = BillingRecord.objects.all()
        br_before_ct = len(br_before)
        response = setup_dict["client"].post(
            reverse("subscription-list"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        sr_after = SubscriptionRecord.objects.all()
        br_after = BillingRecord.objects.all()
        assert response.status_code == status.HTTP_201_CREATED
        assert sr_after.count() == sr_before_ct + 1
        assert (
            br_before_ct + 3 * 4 <= br_after.count() <= br_before_ct + 3 * 5
        )  # 3 billing records for 3 plan components, 4-5 weeks
        new_br = br_after.exclude(id__in=br_before)
        # new billign record should have a billing date at 7, 14, 21, 28 days from start date, plus end date, so 5
        for br in new_br:
            assert (
                3 <= len(br.invoicing_dates) <= 4
                or br.end_date == br.subscription.end_date
            )
            assert br.next_invoicing_date == br.invoicing_dates[0]
            assert br.fully_billed is False
            assert br.unadjusted_duration_microseconds == 7 * 86400000000 or (
                br.end_date == br.subscription.end_date
            )

    def test_monthly_plan_with_weekly_invoicing_creates_correct_number_of_billing_records_for_recurring_charges(
        self,
        subscription_test_common_setup,
    ):
        num_subscriptions = 0
        setup_dict = subscription_test_common_setup(
            num_subscriptions=num_subscriptions,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )
        customer = setup_dict["customer"]
        PlanVersion.objects.all().delete()
        billing_plan = baker.make(
            PlanVersion,
            organization=setup_dict["org"],
            plan=setup_dict["plan"],
            currency=PricingUnit.objects.get(
                organization=setup_dict["org"], code="USD"
            ),
        )
        RecurringCharge.objects.create(
            organization=billing_plan.organization,
            plan_version=billing_plan,
            charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
            charge_behavior=RecurringCharge.ChargeBehaviorType.PRORATE,
            amount=10,
            pricing_unit=billing_plan.currency,
            invoicing_interval_unit=RecurringCharge.IntervalLengthType.WEEK,
            invoicing_interval_count=1,
        )
        payload = {
            "start_date": now_utc() - timedelta(days=5),
            "customer_id": customer.customer_id,
            "version_id": billing_plan.version_id,
        }
        sr_before = SubscriptionRecord.objects.all().count()
        br_before = BillingRecord.objects.all().count()
        response = setup_dict["client"].post(
            reverse("subscription-list"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        sr_after = SubscriptionRecord.objects.all().count()
        br_after = BillingRecord.objects.all().count()
        assert response.status_code == status.HTTP_201_CREATED
        assert sr_after == sr_before + 1
        assert br_after == br_before + 1  # 1 billing record for 1 recurring charge
        new_br = BillingRecord.objects.all().order_by("-id").first()
        # new billign record should have a billing date at 0, 7, 14, 21, 28 days from start date, plus end date, so 5
        assert len(new_br.invoicing_dates) == 6
        assert (
            new_br.next_invoicing_date == new_br.invoicing_dates[1]
        )  # Only the initial date has passed
        assert (
            new_br.fully_billed is False
        )  # until we're done with all the invoicing dates
        new_invoice = Invoice.objects.all().order_by("-id").first()
        min_value = 10 * (Decimal("28") - Decimal("1")) / Decimal("28")
        assert min_value < new_invoice.cost_due < 10

    def test_monthly_plan_with_daily_reset_creates_correct_amount_of_billing_records_for_recurring_charges(
        self,
        subscription_test_common_setup,
    ):
        num_subscriptions = 0
        setup_dict = subscription_test_common_setup(
            num_subscriptions=num_subscriptions,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )
        customer = setup_dict["customer"]
        PlanVersion.objects.all().delete()
        billing_plan = baker.make(
            PlanVersion,
            organization=setup_dict["org"],
            plan=setup_dict["plan"],
            currency=PricingUnit.objects.get(
                organization=setup_dict["org"], code="USD"
            ),
        )
        RecurringCharge.objects.create(
            organization=billing_plan.organization,
            plan_version=billing_plan,
            charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
            charge_behavior=RecurringCharge.ChargeBehaviorType.PRORATE,
            amount=10,
            pricing_unit=billing_plan.currency,
            reset_interval_unit=RecurringCharge.IntervalLengthType.DAY,
            reset_interval_count=1,
        )
        payload = {
            "start_date": now_utc() - timedelta(days=5),
            "customer_id": customer.customer_id,
            "version_id": billing_plan.version_id,
        }
        sr_before = SubscriptionRecord.objects.all()
        sr_before_ct = len(sr_before)
        br_before = BillingRecord.objects.all()
        br_before_ct = len(br_before)
        response = setup_dict["client"].post(
            reverse("subscription-list"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        sr_after = SubscriptionRecord.objects.all()
        br_after = BillingRecord.objects.all()
        assert response.status_code == status.HTTP_201_CREATED
        assert sr_after.count() == sr_before_ct + 1
        assert (
            br_before_ct + 28 <= br_after.count() <= br_before_ct + 31
        )  #  28-31 days for a single recurring charge
        for br in br_after:
            assert len(br.invoicing_dates) == 2  # start and end of every day
            assert br.unadjusted_duration_microseconds == 86400000000 or (
                br.end_date == br.subscription.end_date
            )
            if br.fully_billed is True:
                assert br.next_invoicing_date == br.invoicing_dates[-1]
            else:
                assert (
                    br.next_invoicing_date == br.invoicing_dates[0]
                    or br.invoicing_dates[0] < now_utc()  # for the case of today
                )

        assert (
            Invoice.objects.all().first().cost_due == 6 * 10
        )  # 5 days ago, incl. todays in advance charge thats 60

    # def test_monthly_plan_with_mixed_reset_and_invoicing_generates_correct_brs_for_recurring_charges(
    #     self,
    #     subscription_test_common_setup,
    # ):
    #     num_subscriptions = 0
    #     setup_dict = subscription_test_common_setup(
    #         num_subscriptions=num_subscriptions,
    #         auth_method="api_key",
    #         user_org_and_api_key_org_different=False,
    #     )
    #     customer = setup_dict["customer"]
    #     PlanVersion.objects.all().delete()
    #     billing_plan = baker.make(
    #         PlanVersion,
    #         organization=setup_dict["org"],
    #         plan=setup_dict["plan"],
    #         currency=PricingUnit.objects.get(
    #             organization=setup_dict["org"], code="USD"
    #         ),
    #     )
    #     RecurringCharge.objects.create(
    #         organization=billing_plan.organization,
    #         plan_version=billing_plan,
    #         charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
    #         charge_behavior=RecurringCharge.ChargeBehaviorType.PRORATE,
    #         amount=10,
    #         pricing_unit=billing_plan.currency,
    #         reset_interval_unit=PlanComponent.IntervalLengthType.WEEK,
    #             reset_interval_count=1,
    #             invoicing_interval_unit=PlanComponent.IntervalLengthType.DAY,
    #             invoicing_interval_count=2,
    #     )
    #     payload = {
    #         "start_date": now_utc() - timedelta(days=5),
    #         "customer_id": customer.customer_id,
    #         "version_id": billing_plan.version_id,
    #     }
    #     sr_before = SubscriptionRecord.objects.all()
    #     sr_before_ct = len(sr_before)
    #     br_before = BillingRecord.objects.all()
    #     br_before_ct = len(br_before)
    #     response = setup_dict["client"].post(
    #         reverse("subscription-list"),
    #         data=json.dumps(payload, cls=DjangoJSONEncoder),
    #         content_type="application/json",
    #     )
    #     sr_after = SubscriptionRecord.objects.all()
    #     br_after = BillingRecord.objects.all()
    #     assert response.status_code == status.HTTP_201_CREATED
    #     assert sr_after.count() == sr_before_ct + 1
    #     assert (
    #         br_before_ct + 4 <= br_after.count() <= br_before_ct + 5
    #     )  # 1 billing records for 1 recurring charge, 4-5 weeks
    #     # new billign record should have a billing date at 7, 14, 21, 28 days from start date, plus end date, so 5
    #     for br in br_after:
    #         assert (
    #             3 <= len(br.invoicing_dates) <= 4
    #             or br.end_date == br.subscription.end_date
    #         )
    #         assert br.next_invoicing_date == br.invoicing_dates[0]
    #         assert br.fully_billed is False
    #         assert br.unadjusted_duration_microseconds == 7 * 86400000000 or (
    #             br.end_date == br.subscription.end_date
    #         )
