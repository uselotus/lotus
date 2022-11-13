import itertools
import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from djmoney.money import Money
from metering_billing.models import (
    BillableMetric,
    Invoice,
    PlanComponent,
    PlanVersion,
    PriceTier,
    Subscription,
)
from metering_billing.utils import now_utc
from metering_billing.utils.enums import (
    PRICE_TIER_TYPE,
    REPLACE_IMMEDIATELY_TYPE,
    SUBSCRIPTION_STATUS,
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
            BillableMetric,
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
            "status": "active",
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
            reverse("subscription-list"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0  # check that the response is not empty
        assert len(get_subscriptions_in_org(setup_dict["org"])) == 1

    def test_session_auth_can_create_subscription_nonempty_before(
        self, subscription_test_common_setup, get_subscriptions_in_org
    ):
        # covers num_subscriptions_before_insert = 0, has_org_api_key=true, user_in_org=true, user_org_and_api_key_org_different=false, authenticated=true
        num_subscriptions = 1
        setup_dict = subscription_test_common_setup(
            num_subscriptions=num_subscriptions,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )

        response = setup_dict["client"].post(
            reverse("subscription-list"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0
        assert len(get_subscriptions_in_org(setup_dict["org"])) == num_subscriptions + 1

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
            reverse("subscription-list"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_406_NOT_ACCEPTABLE
        assert len(get_subscriptions_in_org(setup_dict["org"])) == num_subscriptions

    def test_deny_overlapping_subscriptions(
        self, subscription_test_common_setup, get_subscriptions_in_org
    ):
        # covers user_org_and_api_key_org_different = True
        num_subscriptions = 0
        setup_dict = subscription_test_common_setup(
            num_subscriptions=num_subscriptions,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )
        Subscription.objects.create(
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
            billing_plan=setup_dict["billing_plan"],
            status="active",
            start_date=now_utc() - timedelta(days=20),
        )

        response = setup_dict["client"].post(
            reverse("subscription-list"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert len(get_subscriptions_in_org(setup_dict["org"])) == num_subscriptions + 1

    # def test_deny_customer_and_bp_different_currency(
    #     self, subscription_test_common_setup, get_subscriptions_in_org
    # ):
    #     # covers user_org_and_api_key_org_different = True
    #     num_subscriptions = 1
    #     setup_dict = subscription_test_common_setup(
    #         num_subscriptions=num_subscriptions,
    #         auth_method="api_key",
    #         user_org_and_api_key_org_different=False,
    #     )
    #     setup_dict["customer"].balance = Money(0, "GBP")
    #     setup_dict["customer"].save()

    #     response = setup_dict["client"].post(
    #         reverse("subscription-list"),
    #         data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
    #         content_type="application/json",
    #     )

    #     assert response.status_code == status.HTTP_400_BAD_REQUEST
    #     assert len(get_subscriptions_in_org(setup_dict["org"])) == num_subscriptions


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

        payload = {
            "status": SUBSCRIPTION_STATUS.ENDED,
            "replace_immediately_type": REPLACE_IMMEDIATELY_TYPE.END_CURRENT_SUBSCRIPTION_AND_BILL,
        }
        response = setup_dict["client"].patch(
            reverse(
                "subscription-detail",
                kwargs={"subscription_id": active_subscriptions[0].subscription_id},
            ),
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
        assert len(after_active_subscriptions) + 1 == len(active_subscriptions)
        assert len(after_canceled_subscriptions) == 1
        assert new_invoices_len == prev_invoices_len + 1

    def test_end_subscription_dont_generate_invoice(
        self, subscription_test_common_setup
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

        payload = {
            "status": SUBSCRIPTION_STATUS.ENDED,
            "replace_immediately_type": REPLACE_IMMEDIATELY_TYPE.END_CURRENT_SUBSCRIPTION_DONT_BILL,
        }
        response = setup_dict["client"].patch(
            reverse(
                "subscription-detail",
                kwargs={"subscription_id": active_subscriptions[0].subscription_id},
            ),
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
        assert len(after_active_subscriptions) + 1 == len(active_subscriptions)
        assert len(after_canceled_subscriptions) == 1
        assert new_invoices_len == prev_invoices_len

    def test_replace_bp_and_create_new_sub(
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
            "plan_id": plan.plan_id,
            "replace_immediately_type": REPLACE_IMMEDIATELY_TYPE.END_CURRENT_SUBSCRIPTION_AND_BILL,
        }
        response = setup_dict["client"].patch(
            reverse(
                "subscription-detail",
                kwargs={"subscription_id": active_subscriptions[0].subscription_id},
            ),
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
        assert len(after_canceled_subscriptions) == 1
        assert new_invoices_len == prev_invoices_len + 1
        assert Invoice.objects.all()[0].cost_due.amount - Decimal(30) < 0.0000001

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
            "plan_id": plan.plan_id,
            "replace_immediately_type": REPLACE_IMMEDIATELY_TYPE.CHANGE_SUBSCRIPTION_PLAN,
        }
        response = setup_dict["client"].patch(
            reverse(
                "subscription-detail",
                kwargs={"subscription_id": active_subscriptions[0].subscription_id},
            ),
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
        assert (
            sum(
                v["amount"]
                for v in Subscription.objects.all()[0].prorated_flat_costs_dict.values()
            )
            - 60
            < 0.000001
        )

    def test_cancel_auto_renew(self, subscription_test_common_setup):
        setup_dict = subscription_test_common_setup(
            num_subscriptions=1, auth_method="session_auth"
        )

        autorenew_subscriptions = Subscription.objects.filter(
            status="active",
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
            auto_renew=True,
        )
        prev_invoices_len = Invoice.objects.all().count()
        assert len(autorenew_subscriptions) == 1

        payload = {
            "auto_renew": False,
        }
        response = setup_dict["client"].patch(
            reverse(
                "subscription-detail",
                kwargs={"subscription_id": autorenew_subscriptions[0].subscription_id},
            ),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        after_autorenew_subscriptions = Subscription.objects.filter(
            status=SUBSCRIPTION_STATUS.ACTIVE,
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
            auto_renew=True,
        )
        new_invoices_len = Invoice.objects.all().count()

        assert response.status_code == status.HTTP_200_OK
        assert len(after_autorenew_subscriptions) + 1 == len(autorenew_subscriptions)
        assert new_invoices_len == prev_invoices_len
