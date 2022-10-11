import datetime
import itertools
import json

import pytest
from dateutil.relativedelta import relativedelta
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from metering_billing.models import (
    BillableMetric,
    BillingPlan,
    Event,
    Invoice,
    PlanComponent,
    Subscription,
)
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APIClient


@pytest.fixture
def draft_invoice_test_common_setup(
    generate_org_and_api_key,
    add_users_to_org,
    api_client_with_api_key_auth,
    add_customers_to_org,
):
    def do_draft_invoice_test_common_setup(*, auth_method):
        setup_dict = {}
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
            (user,) = add_users_to_org(org, n=1)
            client.force_authenticate(user=user)
            setup_dict["user"] = user
        setup_dict["client"] = client
        (customer,) = add_customers_to_org(org, n=1)
        customer.payment_provider_ids["stripe"] = ""
        customer.save()
        setup_dict["customer"] = customer
        event_properties = (
            {"num_characters": 350, "peak_bandwith": 65},
            {"num_characters": 125, "peak_bandwith": 148},
            {"num_characters": 543, "peak_bandwith": 16},
        )
        event_set = baker.make(
            Event,
            organization=org,
            customer=customer,
            event_name="email_sent",
            time_created=datetime.datetime.now().date() - relativedelta(days=1),
            properties=itertools.cycle(event_properties),
            _quantity=3,
        )
        metric_set = baker.make(
            BillableMetric,
            organization=org,
            event_name="email_sent",
            property_name=itertools.cycle(["num_characters", "peak_bandwith", ""]),
            aggregation_type=itertools.cycle(["sum", "max", "count"]),
            _quantity=3,
        )
        setup_dict["metrics"] = metric_set
        billing_plan = baker.make(
            BillingPlan,
            organization=org,
            interval="month",
            name="test_plan",
            description="test_plan for testing",
            flat_rate=30.0,
            pay_in_advance=False,
        )
        plan_component_set = baker.make(
            PlanComponent,
            billable_metric=itertools.cycle(metric_set),
            free_metric_units=itertools.cycle([50, 0, 1]),
            cost_per_batch=itertools.cycle([5, 0.05, 2]),
            metric_units_per_batch=itertools.cycle([100, 1, 1]),
            _quantity=3,
        )
        setup_dict["plan_components"] = plan_component_set
        billing_plan.components.add(*plan_component_set)
        billing_plan.save()
        setup_dict["billing_plan"] = billing_plan
        subscription = baker.make(
            Subscription,
            organization=org,
            customer=customer,
            billing_plan=billing_plan,
            start_date=datetime.datetime.now().date() - relativedelta(days=3),
            status="active",
        )
        ns_subscription = baker.make(
            Subscription,
            organization=org,
            customer=customer,
            billing_plan=billing_plan,
            start_date=datetime.datetime.now().date() + relativedelta(days=3),
            status="not_started",
        )
        ended_subscription = baker.make(
            Subscription,
            organization=org,
            customer=customer,
            billing_plan=billing_plan,
            start_date=datetime.datetime.now().date() - relativedelta(months=3),
            status="ended",
        )
        setup_dict["subscription"] = subscription
        setup_dict["ns_subscription"] = ns_subscription
        setup_dict["ended_subscription"] = ended_subscription

        return setup_dict

    return do_draft_invoice_test_common_setup


@pytest.mark.django_db(transaction=True)
class TestCancelSub:
    def test_cancel_revoke_and_generate_invoice(self, draft_invoice_test_common_setup):
        setup_dict = draft_invoice_test_common_setup(auth_method="session_auth")

        active_subscriptions = Subscription.objects.filter(
            status="active",
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        )
        prev_invoices_len = Invoice.objects.all().count()
        assert len(active_subscriptions) == 1

        payload = {
            "subscription_id": setup_dict["subscription"].subscription_id,
            "bill_now": True,
            "revoke_access": True,
        }
        response = setup_dict["client"].post(
            reverse("cancel_subscription"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        after_active_subscriptions = Subscription.objects.filter(
            status="active",
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        )
        after_canceled_subscriptions = Subscription.objects.filter(
            status="canceled",
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        )
        new_invoices_len = Invoice.objects.all().count()
        assert response.status_code == status.HTTP_200_OK
        assert len(after_active_subscriptions) + 1 == len(active_subscriptions)
        assert len(after_canceled_subscriptions) == 1
        assert new_invoices_len == prev_invoices_len + 1

    def test_cancel_hadnt_started(self, draft_invoice_test_common_setup):
        setup_dict = draft_invoice_test_common_setup(auth_method="session_auth")

        num_prev_subs = Subscription.objects.filter(
            status="not_started",
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        ).count()
        prev_invoices_len = Invoice.objects.all().count()

        payload = {
            "subscription_id": setup_dict["ns_subscription"].subscription_id,
            "bill_now": True,
        }
        response = setup_dict["client"].post(
            reverse("cancel_subscription"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        num_after_subs = Subscription.objects.filter(
            status="not_started",
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        ).count()
        new_invoices_len = Invoice.objects.all().count()
        assert response.status_code == status.HTTP_200_OK
        assert num_after_subs + 1 == num_prev_subs
        assert new_invoices_len == prev_invoices_len

    def test_cancel_revoke_and_dont_generate_invoice(
        self, draft_invoice_test_common_setup
    ):
        setup_dict = draft_invoice_test_common_setup(auth_method="session_auth")

        active_subscriptions = Subscription.objects.filter(
            status="active",
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        )
        prev_invoices_len = Invoice.objects.all().count()
        assert len(active_subscriptions) == 1

        payload = {
            "subscription_id": setup_dict["subscription"].subscription_id,
            "bill_now": False,
            "revoke_access": True,
        }
        response = setup_dict["client"].post(
            reverse("cancel_subscription"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        after_active_subscriptions = Subscription.objects.filter(
            status="active",
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        )
        after_canceled_subscriptions = Subscription.objects.filter(
            status="canceled",
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        )
        new_invoices_len = Invoice.objects.all().count()
        assert response.status_code == status.HTTP_200_OK
        assert len(after_active_subscriptions) + 1 == len(active_subscriptions)
        assert len(after_canceled_subscriptions) == 1
        assert new_invoices_len == prev_invoices_len

    def test_cancel_already_ended(self, draft_invoice_test_common_setup):
        setup_dict = draft_invoice_test_common_setup(auth_method="session_auth")

        ended_subs = Subscription.objects.filter(
            status="ended",
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        )
        prev_invoices_len = Invoice.objects.all().count()

        payload = {
            "subscription_id": setup_dict["ended_subscription"].subscription_id,
            "bill_now": False,
        }
        response = setup_dict["client"].post(
            reverse("cancel_subscription"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        after_ended_subs = Subscription.objects.filter(
            status="ended",
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        )
        new_invoices_len = Invoice.objects.all().count()
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert len(ended_subs) == len(after_ended_subs)
        assert new_invoices_len == prev_invoices_len

    def test_cancel_dont_revoke(self, draft_invoice_test_common_setup):
        setup_dict = draft_invoice_test_common_setup(auth_method="session_auth")

        active_subscriptions = Subscription.objects.filter(
            status="active",
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        )
        auto_renewing_subscriptions = active_subscriptions.filter(auto_renew=True)
        prev_invoices_len = Invoice.objects.all().count()
        assert len(active_subscriptions) == 1
        assert len(auto_renewing_subscriptions) == 1

        payload = {
            "subscription_id": setup_dict["subscription"].subscription_id,
            "revoke_access": False,
        }
        response = setup_dict["client"].post(
            reverse("cancel_subscription"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        after_active_subscriptions = Subscription.objects.filter(
            status="active",
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        )
        after_auto_renewing_subscriptions = active_subscriptions.filter(auto_renew=True)
        after_canceled_subscriptions = Subscription.objects.filter(
            status="canceled",
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        )
        new_invoices_len = Invoice.objects.all().count()
        assert response.status_code == status.HTTP_200_OK
        assert len(after_active_subscriptions) == len(active_subscriptions)
        assert (
            len(auto_renewing_subscriptions)
            == len(after_auto_renewing_subscriptions) + 1
        )
        assert len(after_canceled_subscriptions) == 0
        assert new_invoices_len == prev_invoices_len
