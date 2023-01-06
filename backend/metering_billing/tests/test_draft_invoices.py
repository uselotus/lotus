import itertools
from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from metering_billing.invoice import generate_invoice
from metering_billing.models import (
    Event,
    Invoice,
    Metric,
    PlanComponent,
    PlanVersion,
    PriceAdjustment,
    PriceTier,
    Subscription,
)
from metering_billing.utils import now_utc
from metering_billing.utils.enums import (
    INVOICE_STATUS,
    PRICE_ADJUSTMENT_TYPE,
    PRICE_TIER_TYPE,
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
    add_product_to_org,
    add_plan_to_product,
    add_plan_version_to_plan,
    add_subscription_to_org,
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
            time_created=now_utc() - timedelta(days=1),
            properties=itertools.cycle(event_properties),
            _quantity=3,
        )
        metric_set = baker.make(
            Metric,
            organization=org,
            event_name="email_sent",
            property_name=itertools.cycle(["num_characters", "peak_bandwith", ""]),
            usage_aggregation_type=itertools.cycle(["sum", "max", "count"]),
            _quantity=3,
        )
        for metric in metric_set:
            metric.provision_materialized_views()
        setup_dict["metrics"] = metric_set
        product = add_product_to_org(org)
        plan = add_plan_to_product(product)
        plan_version = add_plan_version_to_plan(plan)
        for i, (fmu, cpb, mupb) in enumerate(
            zip([50, 0, 1], [5, 0.05, 2], [100, 1, 1])
        ):
            pc = PlanComponent.objects.create(
                plan_version=plan_version,
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
        setup_dict["billing_plan"] = plan_version
        subscription, subscription_record = add_subscription_to_org(
            org, plan_version, customer, now_utc() - timedelta(days=3)
        )
        setup_dict["subscription"] = subscription
        setup_dict["subscription_record"] = subscription_record

        return setup_dict

    return do_draft_invoice_test_common_setup


@pytest.mark.django_db(transaction=True)
class TestGenerateInvoice:
    def test_generate_invoice(self, draft_invoice_test_common_setup):
        setup_dict = draft_invoice_test_common_setup(auth_method="api_key")

        active_subscriptions = Subscription.objects.active().filter(
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        )
        assert len(active_subscriptions) == 1

        prev_invoices_len = Invoice.objects.filter(
            payment_status=INVOICE_STATUS.DRAFT
        ).count()
        payload = {"customer_id": setup_dict["customer"].customer_id}
        response = setup_dict["client"].get(reverse("draft_invoice"), payload)
        assert response.status_code == status.HTTP_200_OK
        after_active_subscriptions = Subscription.objects.active().filter(
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        )
        assert len(after_active_subscriptions) == len(active_subscriptions)
        new_invoices_len = Invoice.objects.filter(
            payment_status=INVOICE_STATUS.DRAFT
        ).count()

        assert new_invoices_len == prev_invoices_len  # don't generate from drafts

    def test_generate_invoice_with_price_adjustments(
        self, draft_invoice_test_common_setup
    ):
        setup_dict = draft_invoice_test_common_setup(auth_method="api_key")

        active_subscriptions = Subscription.objects.active().filter(
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        )
        assert len(active_subscriptions) == 1

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "include_next_period": False,
        }
        response = setup_dict["client"].get(reverse("draft_invoice"), payload)
        assert response.status_code == status.HTTP_200_OK
        before_cost = response.data["invoices"][0]["cost_due"]
        pct_price_adjustment = PriceAdjustment.objects.create(
            organization=setup_dict["org"],
            price_adjustment_name=r"1% discount",
            price_adjustment_description=r"1% discount for being a valued customer",
            price_adjustment_type=PRICE_ADJUSTMENT_TYPE.PERCENTAGE,
            price_adjustment_amount=-1,
        )
        setup_dict["billing_plan"].price_adjustment = pct_price_adjustment
        setup_dict["billing_plan"].save()

        response = setup_dict["client"].get(reverse("draft_invoice"), payload)
        assert response.status_code == status.HTTP_200_OK
        after_cost = response.data["invoices"][0]["cost_due"]
        assert (before_cost * Decimal("0.99") - after_cost) < Decimal("0.01")

        fixed_price_adjustment = PriceAdjustment.objects.create(
            organization=setup_dict["org"],
            price_adjustment_name=r"$1 discount",
            price_adjustment_description=r"$1 discount for being a valued customer",
            price_adjustment_type=PRICE_ADJUSTMENT_TYPE.FIXED,
            price_adjustment_amount=-1,
        )
        setup_dict["billing_plan"].price_adjustment = fixed_price_adjustment
        setup_dict["billing_plan"].save()

        response = setup_dict["client"].get(reverse("draft_invoice"), payload)

        assert response.status_code == status.HTTP_200_OK
        after_cost = response.data["invoices"][0]["cost_due"]
        assert before_cost - Decimal("1") == after_cost

        override_price_adjustment = PriceAdjustment.objects.create(
            organization=setup_dict["org"],
            price_adjustment_name=r"$20 negoatiated price",
            price_adjustment_description=r"$20 price negotiated with sales team",
            price_adjustment_type=PRICE_ADJUSTMENT_TYPE.PRICE_OVERRIDE,
            price_adjustment_amount=20,
        )
        setup_dict["billing_plan"].price_adjustment = override_price_adjustment
        setup_dict["billing_plan"].save()

        response = setup_dict["client"].get(reverse("draft_invoice"), payload)

        assert response.status_code == status.HTTP_200_OK
        after_cost = response.data["invoices"][0]["cost_due"]
        assert Decimal("20") == after_cost

    def test_generate_invoice_with_taxes(self, draft_invoice_test_common_setup):
        setup_dict = draft_invoice_test_common_setup(auth_method="api_key")

        active_subscriptions = Subscription.objects.active().filter(
            organization=setup_dict["org"],
            customer=setup_dict["customer"],
        )
        assert len(active_subscriptions) == 1

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "include_next_period": False,
        }
        response = setup_dict["client"].get(reverse("draft_invoice"), payload)
        assert response.status_code == status.HTTP_200_OK
        before_cost = response.data["invoices"][0]["cost_due"]

        setup_dict["org"].tax_rate = Decimal("10")
        setup_dict["org"].save()
        response = setup_dict["client"].get(reverse("draft_invoice"), payload)
        assert response.status_code == status.HTTP_200_OK
        after_cost = response.data["invoices"][0]["cost_due"]
        assert (before_cost * Decimal("1.1") - after_cost) < Decimal("0.01")

        setup_dict["customer"].tax_rate = Decimal("20")
        setup_dict["customer"].save()
        response = setup_dict["client"].get(reverse("draft_invoice"), payload)
        assert response.status_code == status.HTTP_200_OK
        after_cost = response.data["invoices"][0]["cost_due"]
        assert (before_cost * Decimal("1.2") - after_cost) < Decimal("0.01")
