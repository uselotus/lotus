import itertools
import json
import urllib.parse
from datetime import timedelta
from decimal import Decimal

import pytest
from dateutil.relativedelta import relativedelta
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from djmoney.money import Money
from metering_billing.models import (
    Invoice,
    Metric,
    Plan,
    PlanComponent,
    PlanVersion,
    PriceTier,
    Subscription,
    SubscriptionRecord,
)
from metering_billing.utils import now_utc
from metering_billing.utils.enums import (
    FLAT_FEE_BEHAVIOR,
    PLAN_DURATION,
    PLAN_STATUS,
    PRICE_TIER_TYPE,
    REPLACE_IMMEDIATELY_TYPE,
    SUBSCRIPTION_STATUS,
    USAGE_BILLING_FREQUENCY,
)
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APIClient


@pytest.fixture
def subscription_test_common_setup(
    generate_org_and_api_key,
    add_users_to_org,
    api_client_with_api_key_auth,
    add_subscription_to_org,
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
            _quantity=3,
        )
        setup_dict["metrics"] = metric_set
        product = add_product_to_org(org)
        setup_dict["product"] = product
        plan = add_plan_to_product(product)
        setup_dict["plan"] = plan
        billing_plan = baker.make(
            PlanVersion,
            organization=org,
            description="test_plan for testing",
            flat_rate=30.0,
            plan=plan,
        )
        plan.display_version = billing_plan
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
                    type=PRICE_TIER_TYPE.FREE,
                    range_start=0,
                    range_end=fmu,
                )
                start = fmu
            PriceTier.objects.create(
                plan_component=pc,
                type=PRICE_TIER_TYPE.PER_UNIT,
                range_start=start,
                cost_per_batch=cpb,
                metric_units_per_batch=mupb,
            )
        setup_dict["billing_plan"] = billing_plan

        (customer,) = add_customers_to_org(org, n=1)
        if num_subscriptions > 0:
            setup_dict["org_subscription"] = add_subscription_to_org(
                org, billing_plan, customer
            )
        payload = {
            "name": "test_subscription",
            "start_date": now_utc().date() - timedelta(days=35),
            "customer_id": customer.customer_id,
            "plan_id": billing_plan.plan.plan_id,
        }
        setup_dict["payload"] = payload
        setup_dict["customer"] = customer

        return setup_dict

    return do_subscription_test_common_setup


@pytest.mark.django_db(transaction=True)
class TestCreateSubscription:
    def test_api_key_can_create_subscription_empty_before(
        self, subscription_test_common_setup, get_subscriptions_in_org
    ):
        # covers num_subscriptions_before_insert = 0, has_org_api_key=true, user_in_org=true, user_org_and_api_key_org_different=false
        num_subscriptions = 0
        setup_dict = subscription_test_common_setup(
            num_subscriptions=num_subscriptions,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )

        response = setup_dict["client"].post(
            reverse("subscription-plans"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0  # check that the response is not empty
        assert len(get_subscriptions_in_org(setup_dict["org"])) == 1

    def test_session_auth_can_create_subscription_nonempty_before(
        self,
        subscription_test_common_setup,
        get_subscriptions_in_org,
        get_subscription_records_in_org,
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

        response = setup_dict["client"].post(
            reverse("subscription-plans"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0
        assert len(get_subscriptions_in_org(setup_dict["org"])) == num_subscriptions
        assert (
            len(get_subscription_records_in_org(setup_dict["org"]))
            == num_subscription_records_before + 1
        )

    def test_user_org_and_api_key_different_reject_creation(
        self, subscription_test_common_setup, get_subscriptions_in_org
    ):
        # covers user_org_and_api_key_org_different = True
        num_subscriptions = 1
        setup_dict = subscription_test_common_setup(
            num_subscriptions=num_subscriptions,
            auth_method="both",
            user_org_and_api_key_org_different=True,
        )

        response = setup_dict["client"].post(
            reverse("subscription-plans"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_406_NOT_ACCEPTABLE
        assert len(get_subscriptions_in_org(setup_dict["org"])) == num_subscriptions


@pytest.mark.django_db(transaction=True)
class TestUpdateSub:
    def test_end_subscription_generate_invoice(self, subscription_test_common_setup):
        setup_dict = subscription_test_common_setup(
            num_subscriptions=1, auth_method="session_auth"
        )

        active_subscriptions = Subscription.objects.filter(
            status="active",
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        )
        prev_invoices_len = Invoice.objects.all().count()
        assert len(active_subscriptions) == 1

        params = {
            "bill_usage": True,
            "customer_id": setup_dict["customer"].customer_id,
            "flat_fee_behavior": FLAT_FEE_BEHAVIOR.CHARGE_FULL,
        }
        response = setup_dict["client"].delete(
            reverse("subscription-plans") + "?" + urllib.parse.urlencode(params),
            content_type="application/json",
        )

        after_active_subscriptions = Subscription.objects.filter(
            status=SUBSCRIPTION_STATUS.ACTIVE,
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        )
        after_canceled_subscriptions = Subscription.objects.filter(
            status=SUBSCRIPTION_STATUS.ENDED,
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        )
        new_invoices_len = Invoice.objects.all().count()
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert len(after_active_subscriptions) + 1 == len(active_subscriptions)
        assert len(after_canceled_subscriptions) == 1
        assert new_invoices_len == prev_invoices_len + 1

    # def test_end_subscription_dont_generate_invoice(
    #     self, subscription_test_common_setup
    # ):
    #     setup_dict = subscription_test_common_setup(
    #         num_subscriptions=1, auth_method="session_auth"
    #     )

    #     active_subscriptions = Subscription.objects.filter(
    #         status="active",
    #         organization=setup_dict["org"],
    #         customer=setup_dict["customer"],
    #     )
    #     prev_invoices_len = Invoice.objects.all().count()
    #     assert len(active_subscriptions) == 1

    #     payload = {
    #         "status": SUBSCRIPTION_STATUS.ENDED,
    #         "replace_immediately_type": REPLACE_IMMEDIATELY_TYPE.END_CURRENT_SUBSCRIPTION_DONT_BILL,
    #     }
    #     response = setup_dict["client"].patch(
    #         reverse(
    #             "subscription-detail",
    #             kwargs={"subscription_id": active_subscriptions[0].subscription_id},
    #         ),
    #         data=json.dumps(payload, cls=DjangoJSONEncoder),
    #         content_type="application/json",
    #     )

    #     after_active_subscriptions = Subscription.objects.filter(
    #         status=SUBSCRIPTION_STATUS.ACTIVE,
    #         organization=setup_dict["org"],
    #         customer=setup_dict["customer"],
    #     )
    #     after_canceled_subscriptions = Subscription.objects.filter(
    #         status=SUBSCRIPTION_STATUS.ENDED,
    #         organization=setup_dict["org"],
    #         customer=setup_dict["customer"],
    #     )
    #     new_invoices_len = Invoice.objects.all().count()
    #     assert response.status_code == status.HTTP_200_OK
    #     assert len(after_active_subscriptions) + 1 == len(active_subscriptions)
    #     assert len(after_canceled_subscriptions) == 1
    #     assert new_invoices_len == prev_invoices_len

    def test_replace_bp_halfway_through_and_prorate(
        self, subscription_test_common_setup, add_plan_to_product
    ):
        setup_dict = subscription_test_common_setup(
            num_subscriptions=1, auth_method="session_auth"
        )

        active_subscriptions = Subscription.objects.filter(
            status="active",
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        )
        prev_invoices_len = Invoice.objects.all().count()
        assert len(active_subscriptions) == 1
        plan = add_plan_to_product(setup_dict["product"])
        pv = PlanVersion.objects.create(
            organization=setup_dict["org"],
            plan=plan,
            version=1,
            description="new plan",
            flat_rate=60,
        )
        plan.make_version_active(pv)

        payload = {
            "replace_plan_id": plan.plan_id,
        }
        params = {
            "customer_id": setup_dict["customer"].customer_id,
        }
        response = setup_dict["client"].patch(
            reverse(
                "subscription-plans",
            )
            + "?"
            + urllib.parse.urlencode(params),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        after_active_subscriptions = Subscription.objects.filter(
            status=SUBSCRIPTION_STATUS.ACTIVE,
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        )
        after_canceled_subscriptions = Subscription.objects.filter(
            status=SUBSCRIPTION_STATUS.ENDED,
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        )
        new_invoices_len = Invoice.objects.all().count()

        assert response.status_code == status.HTTP_200_OK
        assert len(after_active_subscriptions) == len(active_subscriptions)
        assert len(after_canceled_subscriptions) == 0
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
        params = {
            "customer_id": setup_dict["customer"].customer_id,
            "plan_id": setup_dict["plan"].plan_id,
        }
        response = setup_dict["client"].patch(
            reverse(
                "subscription-plans",
            )
            + "?"
            + urllib.parse.urlencode(params),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        after_autorenew_subscription_records = SubscriptionRecord.objects.filter(
            status=SUBSCRIPTION_STATUS.ACTIVE,
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
            auto_renew=True,
        )
        new_invoices_len = Invoice.objects.all().count()

        assert response.status_code == status.HTTP_200_OK
        assert len(after_autorenew_subscription_records) + 1 == len(
            autorenew_subscription_records
        )
        assert new_invoices_len == prev_invoices_len


@pytest.mark.django_db(transaction=True)
class TestSubscriptionAndSubscriptionRecord:
    def test_create_subscription_on_add_plan(self, subscription_test_common_setup):
        setup_dict = subscription_test_common_setup(
            num_subscriptions=0, auth_method="session_auth"
        )

        prev_subscriptions_len = Subscription.objects.all().count()
        prev_subscription_records_len = SubscriptionRecord.objects.all().count()
        assert prev_subscriptions_len == 0
        assert prev_subscription_records_len == 0

        response = setup_dict["client"].post(
            reverse("subscription-plans"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        after_subscriptions_len = Subscription.objects.all().count()
        after_subscription_records_len = SubscriptionRecord.objects.all().count()

        assert response.status_code == status.HTTP_201_CREATED
        assert after_subscriptions_len == prev_subscriptions_len + 1
        assert after_subscription_records_len == prev_subscription_records_len + 1
        sub = Subscription.objects.all().first()
        sub_record = SubscriptionRecord.objects.all().first()
        assert sub.start_date == sub_record.start_date
        assert sub.end_date == sub_record.end_date
        assert sub.billing_cadence == sub_record.billing_plan.plan.plan_duration
        assert sub.day_anchor == sub_record.start_date.day
        assert sub.month_anchor == None

    def test_dont_create_subscription_if_already_exists(
        self, subscription_test_common_setup
    ):
        setup_dict = subscription_test_common_setup(
            num_subscriptions=0, auth_method="session_auth"
        )
        cur_payload = setup_dict["payload"]
        cur_payload["subscription_filters"] = [
            {
                "property_name": "email",
                "value": "test1@test.com",
            }
        ]

        prev_subscriptions_len = Subscription.objects.all().count()
        prev_subscription_records_len = SubscriptionRecord.objects.all().count()
        assert prev_subscriptions_len == 0
        assert prev_subscription_records_len == 0

        response = setup_dict["client"].post(
            reverse("subscription-plans"),
            data=json.dumps(cur_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        after_subscriptions_len = Subscription.objects.all().count()
        after_subscription_records_len = SubscriptionRecord.objects.all().count()

        assert response.status_code == status.HTTP_201_CREATED
        assert after_subscriptions_len == prev_subscriptions_len + 1
        assert after_subscription_records_len == prev_subscription_records_len + 1
        sub = Subscription.objects.all().first()
        sub_record = SubscriptionRecord.objects.all().first()
        assert sub.start_date == sub_record.start_date
        assert sub.end_date == sub_record.end_date
        assert sub.billing_cadence == sub_record.billing_plan.plan.plan_duration
        assert sub.day_anchor == sub_record.start_date.day
        assert sub.month_anchor == None
        prev_subscriptions_len = after_subscriptions_len
        prev_subscription_records_len = after_subscription_records_len

        cur_payload = setup_dict["payload"]
        cur_payload["subscription_filters"] = [
            {
                "property_name": "email",
                "value": "test2@test.com",
            }
        ]
        cur_payload["start_date"] = cur_payload["start_date"] + timedelta(days=7)

        response = setup_dict["client"].post(
            reverse("subscription-plans"),
            data=json.dumps(cur_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        after_subscriptions_len = Subscription.objects.all().count()
        after_subscription_records_len = SubscriptionRecord.objects.all().count()

        assert response.status_code == status.HTTP_201_CREATED
        assert after_subscriptions_len == prev_subscriptions_len
        assert after_subscription_records_len == prev_subscription_records_len + 1
        sub = Subscription.objects.all().first()
        new_sub_record = (
            SubscriptionRecord.objects.all().order_by("-start_date").first()
        )
        old_sub_record = SubscriptionRecord.objects.all().order_by("start_date").first()
        assert sub.start_date != new_sub_record.start_date
        assert sub.end_date == new_sub_record.end_date
        assert sub.end_date == old_sub_record.end_date
        assert sub.billing_cadence == new_sub_record.billing_plan.plan.plan_duration
        assert (new_sub_record.end_date + relativedelta(day=sub.day_anchor)).day == (
            new_sub_record.end_date + relativedelta(days=1)
        ).day
        assert sub.month_anchor == None

    def test_month_anchor_is_none_after_adding_monthly_plan_not_none_after_adding_yearly_plan(
        self, subscription_test_common_setup, add_plan_to_product
    ):
        setup_dict = subscription_test_common_setup(
            num_subscriptions=0, auth_method="session_auth"
        )
        cur_payload = setup_dict["payload"]
        new_plan = Plan.objects.create(
            organization=setup_dict["org"],
            plan_name="yearly plan",
            plan_duration=PLAN_DURATION.YEARLY,
            display_version=setup_dict["billing_plan"],
            status=PLAN_STATUS.ACTIVE,
            plan_id="yearly-plan",
        )

        billing_plan = baker.make(
            PlanVersion,
            organization=setup_dict["org"],
            description="test_plan for testing",
            flat_rate=30.0,
            plan=new_plan,
            usage_billing_frequency=USAGE_BILLING_FREQUENCY.MONTHLY,
        )
        new_plan.display_version = billing_plan
        new_plan.save()

        prev_subscriptions_len = Subscription.objects.all().count()
        prev_subscription_records_len = SubscriptionRecord.objects.all().count()
        assert prev_subscriptions_len == 0
        assert prev_subscription_records_len == 0

        response = setup_dict["client"].post(
            reverse("subscription-plans"),
            data=json.dumps(cur_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        after_subscriptions_len = Subscription.objects.all().count()
        after_subscription_records_len = SubscriptionRecord.objects.all().count()

        assert response.status_code == status.HTTP_201_CREATED
        assert after_subscriptions_len == prev_subscriptions_len + 1
        assert after_subscription_records_len == prev_subscription_records_len + 1
        sub = Subscription.objects.all().first()
        sub_record = SubscriptionRecord.objects.all().first()
        assert sub.start_date == sub_record.start_date
        assert sub.end_date == sub_record.end_date
        assert sub.billing_cadence == sub_record.billing_plan.plan.plan_duration
        assert sub.day_anchor == sub_record.start_date.day
        assert sub.month_anchor == None
        prev_subscriptions_len = after_subscriptions_len
        prev_subscription_records_len = after_subscription_records_len

        cur_payload = setup_dict["payload"].copy()
        cur_payload["plan_id"] = new_plan.plan_id
        cur_payload["start_date"] = cur_payload["start_date"] + timedelta(days=7)
        print("new payload", cur_payload)
        print("old payload", setup_dict["payload"])

        response = setup_dict["client"].post(
            reverse("subscription-plans"),
            data=json.dumps(cur_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        after_subscriptions_len = Subscription.objects.all().count()
        after_subscription_records_len = SubscriptionRecord.objects.all().count()

        assert response.status_code == status.HTTP_201_CREATED
        assert after_subscriptions_len == prev_subscriptions_len
        assert after_subscription_records_len == prev_subscription_records_len + 1
        sub = Subscription.objects.all().first()
        new_sub_record = (
            SubscriptionRecord.objects.all().order_by("-start_date").first()
        )
        old_sub_record = SubscriptionRecord.objects.all().order_by("start_date").first()
        assert sub.start_date != new_sub_record.start_date
        assert sub.end_date == new_sub_record.next_billing_date
        assert sub.end_date == old_sub_record.end_date
        print(
            "new sub record plan",
            new_sub_record.billing_plan.plan.plan_id,
            new_sub_record.billing_plan.plan.plan_duration,
        )
        print(
            "old sub record plan",
            old_sub_record.billing_plan.plan.plan_id,
            old_sub_record.billing_plan.plan.plan_duration,
        )
        assert sub.billing_cadence != new_sub_record.billing_plan.plan.plan_duration
        assert sub.billing_cadence == old_sub_record.billing_plan.plan.plan_duration
        assert (new_sub_record.end_date + relativedelta(day=sub.day_anchor)).day == (
            new_sub_record.end_date + relativedelta(days=1)
        ).day
        assert sub.month_anchor is not None

    # def test_canceling_all_subscription_records_individually_also_cancels_subscription(
    #     self, subscription_test_common_setup
    # ):

    # def test_adding_yearly_plan_makes_monthly_plan_conform_to_day_anchor(
    #     self, subscription_test_common_setup
    # ):

    # def test_change_invoicing_cadence_if_all_monthly_plans_removed(
    #     self, subscription_test_common_setup
    # ):

    # def test_change_invoicing_cadence_if_monthly_plan_gets_added(
    #     self, subscription_test_common_setup
    # ):
