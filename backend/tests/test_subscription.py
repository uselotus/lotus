import itertools
import json
import urllib.parse
from datetime import timedelta

import pytest
from django.urls import reverse
from lotus.backend.metering_billing.aggregation.billable_metrics import METRIC_HANDLER_MAP
from lotus.backend.metering_billing.models import (
    Event,
    Invoice,
    Metric,
    Plan,
    PlanComponent,
    PlanVersion,
    PriceTier,
    SubscriptionRecord,
)
from lotus.backend.metering_billing.serializers.serializer_utils import DjangoJSONEncoder
from lotus.backend.metering_billing.utils import now_utc
from lotus.backend.metering_billing.utils.enums import (
    CHARGEABLE_ITEM_TYPE,
    FLAT_FEE_BEHAVIOR,
    INVOICING_BEHAVIOR,
    PLAN_DURATION,
    PLAN_STATUS,
    USAGE_BEHAVIOR,
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
            description="test_plan for testing",
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
            "name": "test_subscription",
            "start_date": now_utc() - timedelta(days=5),
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
            reverse("subscription-add"),
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
            reverse("subscription-add"),
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
            reverse("subscription-add"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0  # check that the response is not empty
        assert len(get_subscription_records_in_org(setup_dict["org"])) == 1

        response = setup_dict["client"].post(
            reverse("subscription-add"),
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

        params = {
            "customer_id": setup_dict["customer"].customer_id,
        }
        payload = {
            "flat_fee_behavior": FLAT_FEE_BEHAVIOR.CHARGE_FULL,
            "bill_usage": True,
        }
        response = setup_dict["client"].post(
            reverse("subscription-cancel") + "?" + urllib.parse.urlencode(params),
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

        params = {
            "customer_id": setup_dict["customer"].customer_id,
            "plan_id": setup_dict["plan"].plan_id,
        }
        payload = {
            "flat_fee_behavior": FLAT_FEE_BEHAVIOR.CHARGE_FULL,
            "invoicing_behavior": INVOICING_BEHAVIOR.ADD_TO_NEXT_INVOICE,
        }
        response = setup_dict["client"].post(
            reverse("subscription-cancel") + "?" + urllib.parse.urlencode(params),
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

    def test_replace_bp_halfway_through_and_prorate(
        self, subscription_test_common_setup, add_plan_to_product
    ):
        setup_dict = subscription_test_common_setup(
            num_subscriptions=1, auth_method="session_auth"
        )

        prev_invoices_len = Invoice.objects.all().count()
        plan = add_plan_to_product(setup_dict["product"])
        pv = PlanVersion.objects.create(
            organization=setup_dict["org"],
            plan=plan,
            version=1,
            description="new plan",
        )
        plan.make_version_active(pv)

        payload = {
            "replace_plan_id": plan.plan_id,
        }
        params = {
            "customer_id": setup_dict["customer"].customer_id,
            "plan_id": setup_dict["plan"].plan_id,
        }
        response = setup_dict["client"].post(
            reverse(
                "subscription-edit",
            )
            + "?"
            + urllib.parse.urlencode(params),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        new_invoices_len = Invoice.objects.all().count()

        assert response.status_code == status.HTTP_200_OK
        assert new_invoices_len == prev_invoices_len + 1

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
        response = setup_dict["client"].post(
            reverse(
                "subscription-edit",
            )
            + "?"
            + urllib.parse.urlencode(params),
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
            reverse("subscription-add"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        after_subscription_records_len = SubscriptionRecord.objects.all().count()

        assert response.status_code == status.HTTP_201_CREATED
        assert after_subscription_records_len == prev_subscription_records_len + 1

        baker.make(
            Event,
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
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
            display_version=setup_dict["billing_plan"],
            status=PLAN_STATUS.ACTIVE,
        )
        Invoice.objects.all().count()

        baker.make(
            PlanVersion,
            organization=setup_dict["org"],
            description="test_plan for testing",
            plan=new_plan,
            usage_billing_frequency=USAGE_BILLING_FREQUENCY.MONTHLY,
        )
        payload = {
            "replace_plan_id": new_plan.plan_id,
        }
        params = {
            "customer_id": setup_dict["customer"].customer_id,
            "plan_id": setup_dict["plan"].plan_id,
        }
        response = setup_dict["client"].post(
            reverse(
                "subscription-edit",
            )
            + "?"
            + urllib.parse.urlencode(params),
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
            reverse("subscription-add"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        after_subscription_records_len = SubscriptionRecord.objects.all().count()

        assert response.status_code == status.HTTP_201_CREATED
        assert after_subscription_records_len == prev_subscription_records_len + 1

        baker.make(
            Event,
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
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
            display_version=setup_dict["billing_plan"],
            status=PLAN_STATUS.ACTIVE,
        )
        before_invoices = Invoice.objects.all().count()

        billing_plan = baker.make(
            PlanVersion,
            organization=setup_dict["org"],
            description="test_plan for testing",
            plan=new_plan,
            usage_billing_frequency=USAGE_BILLING_FREQUENCY.END_OF_PERIOD,
        )
        new_plan.display_version = billing_plan
        new_plan.save()
        payload = {
            "replace_plan_id": new_plan.plan_id,
        }
        params = {
            "customer_id": setup_dict["customer"].customer_id,
            "plan_id": setup_dict["plan"].plan_id,
        }
        response = setup_dict["client"].post(
            reverse(
                "subscription-edit",
            )
            + "?"
            + urllib.parse.urlencode(params),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        after_invoices = Invoice.objects.all().count()
        assert before_invoices + 1 == after_invoices
        most_recent_invoice = Invoice.objects.all().order_by("-id").first()
        for li in most_recent_invoice.line_items.all():
            assert li.subtotal < 30.0
            assert li.chargeable_item_type != CHARGEABLE_ITEM_TYPE.USAGE_CHARGE
        new_sr = SubscriptionRecord.objects.all().order_by("-id").first()
        assert new_sr.billing_plan == new_plan.display_version
        assert new_sr.usage_start_date != new_sr.start_date

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
            reverse("subscription-add"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        after_subscription_records_len = SubscriptionRecord.objects.all().count()

        assert response.status_code == status.HTTP_201_CREATED
        assert after_subscription_records_len == prev_subscription_records_len + 1

        baker.make(
            Event,
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
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
            display_version=setup_dict["billing_plan"],
            status=PLAN_STATUS.ACTIVE,
        )
        before_invoices = Invoice.objects.all().count()

        billing_plan = baker.make(
            PlanVersion,
            organization=setup_dict["org"],
            description="test_plan for testing",
            plan=new_plan,
            usage_billing_frequency=USAGE_BILLING_FREQUENCY.END_OF_PERIOD,
        )
        new_plan.display_version = billing_plan
        new_plan.save()
        payload = {
            "replace_plan_id": new_plan.plan_id,
            "usage_behavior": USAGE_BEHAVIOR.KEEP_SEPARATE,
        }
        params = {
            "customer_id": setup_dict["customer"].customer_id,
            "plan_id": setup_dict["plan"].plan_id,
        }
        response = setup_dict["client"].post(
            reverse(
                "subscription-edit",
            )
            + "?"
            + urllib.parse.urlencode(params),
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
        assert new_sr.billing_plan == new_plan.display_version
        assert new_sr.usage_start_date == new_sr.start_date


@pytest.mark.django_db(transaction=True)
class TestRegressions:
    def test_list_serializer_on_subs_not_valid(self, subscription_test_common_setup):
        setup_dict = subscription_test_common_setup(
            num_subscriptions=0, auth_method="session_auth"
        )

        prev_subscription_records_len = SubscriptionRecord.objects.all().count()
        assert prev_subscription_records_len == 0

        response = setup_dict["client"].post(
            reverse("subscription-add"),
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

    def test_patch_subscription_cant_find_customer(
        self, subscription_test_common_setup
    ):
        setup_dict = subscription_test_common_setup(
            num_subscriptions=0, auth_method="session_auth"
        )

        prev_subscription_records_len = SubscriptionRecord.objects.all().count()
        assert prev_subscription_records_len == 0

        response = setup_dict["client"].post(
            reverse("subscription-add"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        after_subscription_records_len = SubscriptionRecord.objects.all().count()

        assert response.status_code == status.HTTP_201_CREATED
        assert after_subscription_records_len == prev_subscription_records_len + 1

        # assert normal customer is chilling
        payload = {}
        params = {
            "customer_id": setup_dict["customer"].customer_id,
            "plan_id": setup_dict["plan"].plan_id,
        }
        response = setup_dict["client"].post(
            reverse(
                "subscription-edit",
            )
            + "?"
            + urllib.parse.urlencode(params),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK

        # assert bad customer errors with 400
        payload = {}
        params = {
            "customer_id": "7568989ok,l;loi8uyiop0iuj",
        }
        response = setup_dict["client"].post(
            reverse(
                "subscription-edit",
            )
            + "?"
            + urllib.parse.urlencode(params),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # assert good customer with the id in the body instead of request fails
        payload = {
            "customer_id": setup_dict["customer"].customer_id,
        }
        params = {}
        response = setup_dict["client"].post(
            reverse(
                "subscription-edit",
            )
            + "?"
            + urllib.parse.urlencode(params),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_refresh_rate_metric_doesnt_fail(self, subscription_test_common_setup):
        from lotus.backend.metering_billing.utils.enums import (
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
