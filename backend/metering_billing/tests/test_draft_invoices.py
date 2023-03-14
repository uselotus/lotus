import itertools
import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APIClient

from metering_billing.invoice import generate_invoice
from metering_billing.models import (
    Event,
    Invoice,
    Metric,
    PlanComponent,
    PriceAdjustment,
    PriceTier,
    SubscriptionRecord,
)
from metering_billing.serializers.serializer_utils import DjangoJSONEncoder
from metering_billing.utils import now_utc
from metering_billing.utils.enums import PRICE_ADJUSTMENT_TYPE


@pytest.fixture
def draft_invoice_test_common_setup(
    generate_org_and_api_key,
    add_users_to_org,
    api_client_with_api_key_auth,
    add_customers_to_org,
    add_product_to_org,
    add_plan_to_product,
    add_plan_version_to_plan,
    add_subscription_record_to_org,
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
        baker.make(
            Event,
            organization=org,
            event_name="email_sent",
            time_created=now_utc() - timedelta(days=1),
            properties=itertools.cycle(event_properties),
            _quantity=3,
        )
        metric_set = baker.make(
            Metric,
            billable_metric_name=itertools.cycle(
                ["Email Character Count", "Peak Bandwith", "Email Count"]
            ),
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
        setup_dict["billing_plan"] = plan_version
        plan.display_version = plan_version
        plan.save()
        subscription_record = add_subscription_record_to_org(
            org, plan_version, customer, now_utc() - timedelta(days=3)
        )
        setup_dict["subscription_record"] = subscription_record

        return setup_dict

    return do_draft_invoice_test_common_setup


@pytest.mark.django_db(transaction=True)
class TestGenerateInvoice:
    def test_generate_invoice(self, draft_invoice_test_common_setup):
        setup_dict = draft_invoice_test_common_setup(auth_method="api_key")

        prev_invoices_len = Invoice.objects.filter(
            payment_status=Invoice.PaymentStatus.DRAFT
        ).count()
        payload = {"customer_id": setup_dict["customer"].customer_id}
        response = setup_dict["client"].get(reverse("draft_invoice"), payload)
        assert response.status_code == status.HTTP_200_OK
        new_invoices_len = Invoice.objects.filter(
            payment_status=Invoice.PaymentStatus.DRAFT
        ).count()

        assert new_invoices_len == prev_invoices_len  # don't generate from drafts

    def test_generate_invoice_with_price_adjustments(
        self, draft_invoice_test_common_setup
    ):
        setup_dict = draft_invoice_test_common_setup(auth_method="api_key")

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "include_next_period": False,
        }
        response = setup_dict["client"].get(reverse("draft_invoice"), payload)
        assert response.status_code == status.HTTP_200_OK
        before_cost = response.data["invoices"][0]["amount"]
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
        after_cost = response.data["invoices"][0]["amount"]
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
        after_cost = response.data["invoices"][0]["amount"]
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
        after_cost = response.data["invoices"][0]["amount"]
        assert Decimal("20") == after_cost

    def test_generate_invoice_with_taxes(self, draft_invoice_test_common_setup):
        setup_dict = draft_invoice_test_common_setup(auth_method="api_key")

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "include_next_period": False,
        }
        response = setup_dict["client"].get(reverse("draft_invoice"), payload)
        assert response.status_code == status.HTTP_200_OK
        before_cost = response.data["invoices"][0]["amount"]

        setup_dict["org"].tax_rate = Decimal("10")
        setup_dict["org"].save()
        response = setup_dict["client"].get(reverse("draft_invoice"), payload)
        assert response.status_code == status.HTTP_200_OK
        after_cost = response.data["invoices"][0]["amount"]
        assert (before_cost * Decimal("1.1") - after_cost) < Decimal("0.01")

        setup_dict["customer"].tax_rate = Decimal("20")
        setup_dict["customer"].save()
        response = setup_dict["client"].get(reverse("draft_invoice"), payload)
        assert response.status_code == status.HTTP_200_OK
        after_cost = response.data["invoices"][0]["amount"]
        assert (before_cost * Decimal("1.2") - after_cost) < Decimal("0.01")

    def test_generate_invoice_pdf(self, draft_invoice_test_common_setup):
        setup_dict = draft_invoice_test_common_setup(auth_method="api_key")
        SubscriptionRecord.objects.all().delete()
        Event.objects.all().delete()
        setup_dict["org"].update_subscription_filter_settings(["email"])
        payload = {
            "start_date": now_utc() - timedelta(days=5),
            "customer_id": setup_dict["customer"].customer_id,
            "plan_id": setup_dict["billing_plan"].plan.plan_id,
        }
        for i in range(5):
            payload["subscription_filters"] = [
                {"property_name": "email", "value": f"{i}"}
            ]

            response = setup_dict["client"].post(
                reverse("subscription-add"),
                data=json.dumps(payload, cls=DjangoJSONEncoder),
                content_type="application/json",
            )
            assert response.status_code == status.HTTP_201_CREATED

            event_properties = (
                {"num_characters": 350, "peak_bandwith": 65, "email": f"{i}"},
                {"num_characters": 125, "peak_bandwith": 148, "email": f"{i}"},
                {"num_characters": 543, "peak_bandwith": 16, "email": f"{i}"},
            )
            baker.make(
                Event,
                organization=setup_dict["org"],
                event_name="email_sent",
                time_created=now_utc() - timedelta(days=1),
                properties=itertools.cycle(event_properties),
                cust_id=setup_dict["customer"].customer_id,
                _quantity=3,
            )

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "include_next_period": False,
        }
        result_invoices = generate_invoice(
            SubscriptionRecord.objects.all(),
            draft=False,
        )

        assert len(result_invoices) == 1

        assert result_invoices[0].invoice_pdf != ""
