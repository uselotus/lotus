import itertools
import json
from datetime import timedelta
from decimal import Decimal

import pytest
from dateutil import parser
from django.urls import reverse
from metering_billing.aggregation.billable_metrics import METRIC_HANDLER_MAP
from metering_billing.invoice import generate_invoice
from metering_billing.models import (
    AddOnSpecification,
    CustomerBalanceAdjustment,
    Feature,
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
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APIClient


@pytest.fixture
def addon_test_common_setup(
    generate_org_and_api_key,
    add_users_to_org,
    api_client_with_api_key_auth,
    add_subscription_record_to_org,
    add_customers_to_org,
    add_product_to_org,
    add_plan_to_product,
):
    def do_addon_test_common_setup(
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
            property_name=itertools.cycle(
                ["num_characters", "peak_bandwith", None, "recipients"]
            ),
            usage_aggregation_type=itertools.cycle(["sum", "max", "count", "sum"]),
            billable_metric_name=itertools.cycle(
                ["count_chars", "peak_bandwith", "email_sent", "sum recipients"]
            ),
            _quantity=4,
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
        RecurringCharge.objects.create(
            organization=plan.organization,
            plan_version=billing_plan,
            charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
            charge_behavior=RecurringCharge.ChargeBehaviorType.PRORATE,
            amount=30,
            pricing_unit=billing_plan.currency,
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
            end = None if i != 2 else 100
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
                range_end=end,
            )
        setup_dict["billing_plan"] = billing_plan

        (customer,) = add_customers_to_org(org, n=1)
        if num_subscriptions > 0:
            setup_dict["org_subscription"] = add_subscription_record_to_org(
                org, billing_plan, customer
            )
        # one time flat charge addon
        premium_support_feature = Feature.objects.create(
            organization=org,
            feature_name="premium_support",
            feature_description="premium support",
        )
        flat_fee_addon_spec = AddOnSpecification.objects.create(
            organization=org,
            billing_frequency=AddOnSpecification.BillingFrequency.ONE_TIME,
            flat_fee_invoicing_behavior_on_attach=AddOnSpecification.FlatFeeInvoicingBehaviorOnAttach.INVOICE_ON_ATTACH,
        )
        flat_fee_addon = Plan.addons.create(
            organization=org, plan_name="flat_fee_addon", is_addon=True
        )
        flat_fee_addon_version = PlanVersion.addon_versions.create(
            organization=org,
            plan=flat_fee_addon,
            addon_spec=flat_fee_addon_spec,
            plan_version_name="flat_fee_addon_version",
            currency=PricingUnit.objects.get(organization=org, code="USD"),
        )
        RecurringCharge.objects.create(
            organization=plan.organization,
            plan_version=flat_fee_addon_version,
            charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
            charge_behavior=RecurringCharge.ChargeBehaviorType.CHARGE_FULL,
            amount=10,
            pricing_unit=flat_fee_addon_version.currency,
        )
        flat_fee_addon_version.features.add(premium_support_feature)
        setup_dict["flat_fee_addon"] = flat_fee_addon
        setup_dict["flat_fee_addon_version"] = flat_fee_addon_version
        setup_dict["premium_support_feature"] = premium_support_feature
        setup_dict["flat_fee_addon_spec"] = flat_fee_addon_spec
        # recurring usage_based addon
        account_manager_feature = Feature.objects.create(
            organization=org,
            feature_name="account_manager_feature",
            feature_description="dedicated account manager",
        )
        recurring_addon_spec = AddOnSpecification.objects.create(
            organization=org,
            billing_frequency=AddOnSpecification.BillingFrequency.RECURRING,
            flat_fee_invoicing_behavior_on_attach=AddOnSpecification.FlatFeeInvoicingBehaviorOnAttach.INVOICE_ON_ATTACH,
        )
        recurring_addon = Plan.addons.create(
            organization=org, plan_name="recurring_addon", is_addon=True
        )
        recurring_addon_version = PlanVersion.addon_versions.create(
            organization=org,
            plan=recurring_addon,
            addon_spec=recurring_addon_spec,
            currency=PricingUnit.objects.get(organization=org, code="USD"),
        )
        RecurringCharge.objects.create(
            organization=plan.organization,
            plan_version=recurring_addon_version,
            charge_timing=RecurringCharge.ChargeTimingType.IN_ADVANCE,
            charge_behavior=RecurringCharge.ChargeBehaviorType.PRORATE,
            amount=1,
            pricing_unit=recurring_addon_version.currency,
        )
        recurring_addon_version.features.add(account_manager_feature)
        setup_dict["recurring_addon"] = recurring_addon
        setup_dict["recurring_addon_version"] = recurring_addon_version
        setup_dict["account_manager_feature"] = account_manager_feature
        setup_dict["recurring_addon_spec"] = recurring_addon_spec
        pc = PlanComponent.objects.create(
            plan_version=recurring_addon_version,
            billable_metric=metric_set[3],
        )
        PriceTier.objects.create(
            plan_component=pc,
            type=PriceTier.PriceTierType.PER_UNIT,
            range_start=0,
            cost_per_batch=0.25,
            metric_units_per_batch=mupb,
            range_end=100,
        )  # this metric is not in the other plan

        payload = {
            "name": "test_subscription",
            "start_date": now_utc() - timedelta(days=5),
            "customer_id": customer.customer_id,
            "version_id": billing_plan.version_id,
        }
        setup_dict["payload"] = payload
        setup_dict["customer"] = customer

        return setup_dict

    return do_addon_test_common_setup


@pytest.mark.django_db(transaction=True)
class TestAttachAddOn:
    def test_can_attach_flat_addon(
        self,
        addon_test_common_setup,
    ):
        num_subscriptions = 0
        setup_dict = addon_test_common_setup(
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
        data = response.json()
        start_date = data["start_date"]
        end_date = data["end_date"]
        auto_renew = data["auto_renew"]
        subscription_filters = data["subscription_filters"]
        billing_plan_id = data["billing_plan"]["plan_id"]
        fully_billed = data["fully_billed"]

        assert auto_renew is True
        assert len(subscription_filters) == 0
        assert setup_dict["billing_plan"].plan.plan_id.hex in billing_plan_id
        assert fully_billed is False

        invoice_before = len(Invoice.objects.all())
        addon_payload = {
            "addon_version_id": setup_dict["flat_fee_addon"]
            .versions.first()
            .version_id,
            "quantity": 1,
        }
        print(setup_dict["flat_fee_addon"].versions.first().version_id)
        print(PlanVersion.addon_versions.all().values())
        sub = SubscriptionRecord.objects.first()
        response = setup_dict["client"].post(
            reverse(
                "subscription-attach_addon",
                kwargs={"subscription_id": sub.subscription_record_id},
            ),
            data=json.dumps(addon_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        print(response.data)
        invoice_after = len(Invoice.objects.all())
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["start_date"] != start_date
        assert data["end_date"] == end_date
        assert invoice_before + 1 == invoice_after
        recent_inv = Invoice.objects.all().order_by("-issue_date").first()
        assert (
            recent_inv.cost_due
            == setup_dict["flat_fee_addon_version"].recurring_charges.first().amount
        )

    def test_flat_addon_invoice_later_doesnt_make_new_invoice_and_invoices(
        self,
        addon_test_common_setup,
    ):
        num_subscriptions = 0
        setup_dict = addon_test_common_setup(
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
        data = response.json()
        start_date = data["start_date"]
        end_date = data["end_date"]
        auto_renew = data["auto_renew"]
        subscription_filters = data["subscription_filters"]
        billing_plan_id = data["billing_plan"]["plan_id"]
        fully_billed = data["fully_billed"]

        assert auto_renew is True
        assert len(subscription_filters) == 0
        assert setup_dict["billing_plan"].plan.plan_id.hex in billing_plan_id
        assert fully_billed is False

        invoice_before = len(Invoice.objects.all())
        addon_payload = {
            "addon_version_id": setup_dict["flat_fee_addon"]
            .versions.first()
            .version_id,
            "quantity": 1,
        }
        setup_dict[
            "flat_fee_addon_spec"
        ].flat_fee_invoicing_behavior_on_attach = (
            AddOnSpecification.FlatFeeInvoicingBehaviorOnAttach.INVOICE_ON_SUBSCRIPTION_END
        )
        setup_dict["flat_fee_addon_spec"].save()
        sub = SubscriptionRecord.objects.first()
        response = setup_dict["client"].post(
            reverse(
                "subscription-attach_addon",
                kwargs={"subscription_id": sub.subscription_record_id},
            ),
            data=json.dumps(addon_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        invoice_after = len(Invoice.objects.all())
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["start_date"] != start_date
        assert data["end_date"] == end_date
        assert invoice_before == invoice_after
        invoices = generate_invoice(SubscriptionRecord.objects.all())
        assert Decimal("10.00") - invoices[0].cost_due < Decimal("0.01")

    def test_flat_addon_invoice_later_and_recurring_prorates_current_charge_and_charges_full_next(
        self,
        addon_test_common_setup,
    ):
        num_subscriptions = 0
        setup_dict = addon_test_common_setup(
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
        data = response.json()
        start_date = data["start_date"]
        end_date = data["end_date"]
        auto_renew = data["auto_renew"]
        subscription_filters = data["subscription_filters"]
        billing_plan_id = data["billing_plan"]["plan_id"]
        fully_billed = data["fully_billed"]

        assert auto_renew is True
        assert len(subscription_filters) == 0
        assert setup_dict["billing_plan"].plan.plan_id.hex in billing_plan_id
        assert fully_billed is False

        invoice_before = len(Invoice.objects.all())
        addon_payload = {
            "addon_version_id": setup_dict["flat_fee_addon"]
            .versions.first()
            .version_id,
            "quantity": 1,
        }
        setup_dict[
            "flat_fee_addon_spec"
        ].flat_fee_invoicing_behavior_on_attach = (
            AddOnSpecification.FlatFeeInvoicingBehaviorOnAttach.INVOICE_ON_SUBSCRIPTION_END
        )
        setup_dict[
            "flat_fee_addon_spec"
        ].billing_frequency = AddOnSpecification.BillingFrequency.RECURRING
        setup_dict["flat_fee_addon_spec"].save()
        sub = SubscriptionRecord.objects.first()
        response = setup_dict["client"].post(
            reverse(
                "subscription-attach_addon",
                kwargs={"subscription_id": sub.subscription_record_id},
            ),
            data=json.dumps(addon_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        invoice_after = len(Invoice.objects.all())
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["start_date"] != start_date
        assert data["end_date"] == end_date
        assert invoice_before == invoice_after
        invoices = generate_invoice(
            SubscriptionRecord.objects.all(),
            charge_next_plan=True,
        )
        max_value = 10 * (Decimal("31") - Decimal("5")) / Decimal("31")
        min_value = 10 * (Decimal("28") - Decimal("6")) / Decimal("28")
        # were gonna charge the 30 from the base plan, 10 for new plan, and ~8.20-8.39 for the addon
        assert invoices[0].cost_due - Decimal("40") >= min_value
        assert invoices[0].cost_due - Decimal("40") <= max_value

    def test_attaching_addon_grants_access_to_feature(
        self,
        addon_test_common_setup,
    ):
        num_subscriptions = 0
        setup_dict = addon_test_common_setup(
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
        data = response.json()
        start_date = data["start_date"]
        end_date = data["end_date"]
        auto_renew = data["auto_renew"]
        subscription_filters = data["subscription_filters"]
        billing_plan_id = data["billing_plan"]["plan_id"]
        fully_billed = data["fully_billed"]

        assert auto_renew is True
        assert len(subscription_filters) == 0
        assert setup_dict["billing_plan"].plan.plan_id.hex in billing_plan_id
        assert fully_billed is False
        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "feature_id": setup_dict["premium_support_feature"].feature_id,
        }
        response = setup_dict["client"].get(reverse("feature_access"), payload)

        assert response.status_code == status.HTTP_200_OK
        feature = response.json()
        assert (
            feature["feature"]["feature_name"]
            == setup_dict["premium_support_feature"].feature_name
        )
        assert feature["access"] is False

        invoice_before = len(Invoice.objects.all())
        addon_payload = {
            "addon_version_id": setup_dict["flat_fee_addon"]
            .versions.first()
            .version_id,
            "quantity": 1,
        }
        sub = SubscriptionRecord.objects.first()
        response = setup_dict["client"].post(
            reverse(
                "subscription-attach_addon",
                kwargs={"subscription_id": sub.subscription_record_id},
            ),
            data=json.dumps(addon_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        invoice_after = len(Invoice.objects.all())
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["start_date"] != start_date
        assert data["end_date"] == end_date
        assert invoice_before + 1 == invoice_after
        recent_inv = Invoice.objects.all().order_by("-issue_date").first()
        assert (
            recent_inv.cost_due
            == setup_dict["flat_fee_addon_version"].recurring_charges.first().amount
        )

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "feature_id": setup_dict["premium_support_feature"].feature_id,
        }
        response = setup_dict["client"].get(reverse("feature_access"), payload)

        assert response.status_code == status.HTTP_200_OK
        feature = response.json()
        assert (
            feature["feature"]["feature_name"]
            == setup_dict["premium_support_feature"].feature_name
        )
        assert feature["access"] is True

        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "feature_id": setup_dict["account_manager_feature"].feature_id,
        }
        response = setup_dict["client"].get(reverse("feature_access"), payload)

        assert response.status_code == status.HTTP_200_OK
        feature = response.json()
        assert (
            feature["feature"]["feature_name"]
            == setup_dict["account_manager_feature"].feature_name
        )
        assert feature["access"] is False

    def test_can_attach_usage_based_addon(self, addon_test_common_setup):
        num_subscriptions = 0
        setup_dict = addon_test_common_setup(
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
        data = response.json()
        start_date = data["start_date"]
        end_date = data["end_date"]
        auto_renew = data["auto_renew"]
        subscription_filters = data["subscription_filters"]
        billing_plan_id = data["billing_plan"]["plan_id"]
        fully_billed = data["fully_billed"]

        assert auto_renew is True
        assert len(subscription_filters) == 0
        assert setup_dict["billing_plan"].plan.plan_id.hex in billing_plan_id
        assert fully_billed is False

        invoice_before = len(Invoice.objects.all())
        addon_payload = {
            "addon_version_id": setup_dict["recurring_addon"]
            .versions.first()
            .version_id,
            "quantity": 1,
        }
        sub = SubscriptionRecord.objects.first()
        response = setup_dict["client"].post(
            reverse(
                "subscription-attach_addon",
                kwargs={"subscription_id": sub.subscription_record_id},
            ),
            data=json.dumps(addon_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        invoice_after = len(Invoice.objects.all())
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["start_date"] != start_date
        assert data["end_date"] == end_date
        assert invoice_before + 1 == invoice_after
        recent_inv = Invoice.objects.all().order_by("-issue_date").first()
        # prorated flat fee
        assert (
            0
            < recent_inv.cost_due
            < setup_dict["recurring_addon_version"].recurring_charges.first().amount
        )

    def test_usage_based_add_on(self, addon_test_common_setup):
        num_subscriptions = 0
        setup_dict = addon_test_common_setup(
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
        data = response.json()
        start_date = data["start_date"]
        end_date = data["end_date"]
        auto_renew = data["auto_renew"]
        subscription_filters = data["subscription_filters"]
        billing_plan_id = data["billing_plan"]["plan_id"]
        fully_billed = data["fully_billed"]

        assert auto_renew is True
        assert len(subscription_filters) == 0
        assert setup_dict["billing_plan"].plan.plan_id.hex in billing_plan_id
        assert fully_billed is False

        invoice_before = len(Invoice.objects.all())
        addon_payload = {
            "addon_version_id": setup_dict["recurring_addon"]
            .versions.first()
            .version_id,
            "quantity": 1,
        }
        sub = SubscriptionRecord.objects.first()
        response = setup_dict["client"].post(
            reverse(
                "subscription-attach_addon",
                kwargs={"subscription_id": sub.subscription_record_id},
            ),
            data=json.dumps(addon_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        invoice_after = len(Invoice.objects.all())
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["start_date"] != start_date
        assert data["end_date"] == end_date
        assert invoice_before + 1 == invoice_after
        recent_inv = Invoice.objects.all().order_by("-issue_date").first()
        # prorated flat fee
        assert (
            0
            < recent_inv.cost_due
            < setup_dict["recurring_addon_version"].recurring_charges.first().amount
        )

        # test access
        payload = {
            "customer_id": setup_dict["customer"].customer_id,
            "metric_id": setup_dict["metrics"][3].metric_id,
        }
        response = setup_dict["client"].get(reverse("metric_access"), payload)
        assert response.status_code == status.HTTP_200_OK
        response = response.json()
        assert response["metric"]["event_name"] == setup_dict["metrics"][3].event_name
        assert (
            response["access_per_subscription"][0]["metric_usage"]
            < response["access_per_subscription"][0]["metric_total_limit"]
        )
        assert response["access"] is True

    def test_multi_quantity_flat_addon_invoice_later_prorates_current_charge_charges_next(
        self,
        addon_test_common_setup,
    ):
        num_subscriptions = 0
        setup_dict = addon_test_common_setup(
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
        data = response.json()
        start_date = data["start_date"]
        end_date = data["end_date"]
        auto_renew = data["auto_renew"]
        subscription_filters = data["subscription_filters"]
        billing_plan_id = data["billing_plan"]["plan_id"]
        fully_billed = data["fully_billed"]

        assert auto_renew is True
        assert len(subscription_filters) == 0
        assert setup_dict["billing_plan"].plan.plan_id.hex in billing_plan_id
        assert fully_billed is False
        assert SubscriptionRecord.objects.all().count() == 1

        invoice_before = len(Invoice.objects.all())
        addon_payload = {
            "addon_version_id": setup_dict["flat_fee_addon"]
            .versions.first()
            .version_id,
            "quantity": 3,
        }
        setup_dict[
            "flat_fee_addon_spec"
        ].flat_fee_invoicing_behavior_on_attach = (
            AddOnSpecification.FlatFeeInvoicingBehaviorOnAttach.INVOICE_ON_SUBSCRIPTION_END
        )
        setup_dict[
            "flat_fee_addon_spec"
        ].billing_frequency = AddOnSpecification.BillingFrequency.RECURRING
        setup_dict["flat_fee_addon_spec"].save()
        sub = SubscriptionRecord.objects.first()
        response = setup_dict["client"].post(
            reverse(
                "subscription-attach_addon",
                kwargs={"subscription_id": sub.subscription_record_id},
            ),
            data=json.dumps(addon_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert SubscriptionRecord.objects.all().count() == 2
        invoice_after = len(Invoice.objects.all())
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["start_date"] != start_date
        assert data["end_date"] == end_date
        assert invoice_before == invoice_after

        invoices = generate_invoice(
            SubscriptionRecord.objects.all(),
            charge_next_plan=True,
        )
        max_value = 10 * (Decimal("31") - Decimal("5")) / Decimal("31")
        min_value = 10 * (Decimal("28") - Decimal("6")) / Decimal("28")
        # were gonna charge the 30 from the base plan, 3*10 for new plan, and 3*~8.21-8.38 for the addon
        assert invoices[0].cost_due - Decimal("60") >= 3 * min_value
        assert invoices[0].cost_due - Decimal("60") <= 3 * max_value

    def test_can_attach_flat_addon_with_full_name(
        self,
        addon_test_common_setup,
    ):
        num_subscriptions = 0
        setup_dict = addon_test_common_setup(
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
        data = response.json()
        start_date = data["start_date"]
        end_date = data["end_date"]
        auto_renew = data["auto_renew"]
        subscription_filters = data["subscription_filters"]
        billing_plan_id = data["billing_plan"]["plan_id"]
        fully_billed = data["fully_billed"]

        assert auto_renew is True
        assert len(subscription_filters) == 0
        assert setup_dict["billing_plan"].plan.plan_id.hex in billing_plan_id
        assert fully_billed is False

        invoice_before = len(Invoice.objects.all())
        addon_payload = {
            "addon_version_id": "addon_version_"
            + setup_dict["flat_fee_addon"].versions.first().version_id.hex,
            "quantity": 1,
        }
        sub = SubscriptionRecord.objects.first()
        response = setup_dict["client"].post(
            reverse(
                "subscription-attach_addon",
                kwargs={"subscription_id": sub.subscription_record_id},
            ),
            data=json.dumps(addon_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        invoice_after = len(Invoice.objects.all())
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["start_date"] != start_date
        assert data["end_date"] == end_date
        assert invoice_before + 1 == invoice_after
        recent_inv = Invoice.objects.all().order_by("-issue_date").first()
        assert (
            recent_inv.cost_due
            == setup_dict["flat_fee_addon_version"].recurring_charges.first().amount
        )


# @pytest.mark.django_db(transaction=True)
# class TestUpdateAddOn:
#     def test_update_end_date_auto_renew_works(self, addon_test_common_setup):
#         num_subscriptions = 0
#         setup_dict = addon_test_common_setup(
#             num_subscriptions=num_subscriptions,
#             auth_method="api_key",
#             user_org_and_api_key_org_different=False,
#         )

#         response = setup_dict["client"].post(
#             reverse("subscription-list"),
#             data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
#             content_type="application/json",
#         )
#         assert response.status_code == status.HTTP_201_CREATED
#         data = response.json()
#         start_date = data["start_date"]
#         end_date = data["end_date"]
#         auto_renew = data["auto_renew"]
#         subscription_filters = data["subscription_filters"]
#         billing_plan_id = data["billing_plan"]["plan_id"]
#         fully_billed = data["fully_billed"]
#         customer_id =
#         assert auto_renew is True
#         assert len(subscription_filters) == 0
#         assert setup_dict["billing_plan"].plan.plan_id.hex in billing_plan_id
#         assert fully_billed is False

#         invoice_before = len(Invoice.objects.all())
#         addon_payload = {
#             "addon_version_id": setup_dict["recurring_addon"]
#             .versions.first()
#             .version_id,
#             "quantity": 1,
#         }
#         sub = SubscriptionRecord.objects.first()
#         response = setup_dict["client"].post(
#             reverse(
#                 "subscription-attach_addon",
#                 kwargs={"subscription_id": sub.subscription_record_id},
#             ),
#             data=json.dumps(addon_payload, cls=DjangoJSONEncoder),
#             content_type="application/json",
#         )
#         invoice_after = len(Invoice.objects.all())
#         assert response.status_code == status.HTTP_201_CREATED
#         data = response.json()
#         assert data["start_date"] != start_date
#         assert data["end_date"] == end_date
#         assert invoice_before + 1 == invoice_after
#         recent_inv = Invoice.objects.all().order_by("-issue_date").first()
#         # prorated flat fee
#         assert (
#             0
#             < recent_inv.cost_due
#             < setup_dict["recurring_addon_version"].recurring_charges.first().amount
#         )
#         assert data["auto_renew"] is True

#         # update the addon
#         update_addon_query_params = {
#             "addon_version_id": setup_dict["recurring_addon"]
#             .versions.first()
#             .version_id,
#             "attached_customer_id": customer_id,
#             "attached_plan_id": billing_plan_id,
#         }
#         end = now_utc() + timedelta(days=5)
#         update_addon_payload = {
#             "end_date": end,
#             "turn_off_auto_renew": True,
#         }
#         response = setup_dict["client"].post(
#             reverse("subscription-list_addon")
#             + "?"
#             + urllib.parse.urlencode(update_addon_query_params),
#             data=json.dumps(update_addon_payload, cls=DjangoJSONEncoder),
#             content_type="application/json",
#         )
#         assert response.status_code == status.HTTP_200_OK
#         data = response.json()[0]
#         assert parser.parse(data["end_date"]) == end
#         assert data["auto_renew"] is False

#     def test_update_quantity_on_invoice_later(
#         self,
#         addon_test_common_setup,
#     ):
#         num_subscriptions = 0
#         setup_dict = addon_test_common_setup(
#             num_subscriptions=num_subscriptions,
#             auth_method="api_key",
#             user_org_and_api_key_org_different=False,
#         )

#         response = setup_dict["client"].post(
#             reverse("subscription-list"),
#             data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
#             content_type="application/json",
#         )
#         assert response.status_code == status.HTTP_201_CREATED
#         data = response.json()
#         start_date = data["start_date"]
#         end_date = data["end_date"]
#         auto_renew = data["auto_renew"]
#         subscription_filters = data["subscription_filters"]
#         billing_plan_id = data["billing_plan"]["plan_id"]
#         fully_billed = data["fully_billed"]
#         customer_id =
#         assert auto_renew is True
#         assert len(subscription_filters) == 0
#         assert setup_dict["billing_plan"].plan.plan_id.hex in billing_plan_id
#         assert fully_billed is False

#         invoice_before = len(Invoice.objects.all())
#         addon_payload = {
#             "addon_version_id": setup_dict["flat_fee_addon"]
#             .versions.first()
#             .version_id,
#             "quantity": 1,
#         }
#         setup_dict[
#             "flat_fee_addon_spec"
#         ].flat_fee_invoicing_behavior_on_attach = (
#             AddOnSpecification.FlatFeeInvoicingBehaviorOnAttach.INVOICE_ON_SUBSCRIPTION_END
#         )
#         setup_dict["flat_fee_addon_spec"].save()
#         sub = SubscriptionRecord.objects.first()
#         response = setup_dict["client"].post(
#             reverse(
#                 "subscription-attach_addon",
#                 kwargs={"subscription_id": sub.subscription_record_id},
#             ),
#             data=json.dumps(addon_payload, cls=DjangoJSONEncoder),
#             content_type="application/json",
#         )
#         invoice_after = len(Invoice.objects.all())
#         assert response.status_code == status.HTTP_201_CREATED
#         data = response.json()
#         assert data["start_date"] != start_date
#         assert data["end_date"] == end_date
#         assert invoice_before == invoice_after

#         # update the addon - add 1 to quantity but not invoiced before so chill
#         update_addon_query_params = {
#             "addon_version_id": setup_dict["recurring_addon"]
#             .versions.first()
#             .version_id,
#             "attached_customer_id": customer_id,
#             "attached_plan_id": billing_plan_id,
#         }
#         update_addon_payload = {
#             "quantity": 2,
#             "invoicing_behavior": "add_to_next_invoice",
#         }
#         response = setup_dict["client"].post(
#             reverse("subscription-list_addon")
#             + "?"
#             + urllib.parse.urlencode(update_addon_query_params),
#             data=json.dumps(update_addon_payload, cls=DjangoJSONEncoder),
#             content_type="application/json",
#         )
#         assert response.status_code == status.HTTP_200_OK
#         data = response.json()[0]

#         invoices = generate_invoice(SubscriptionRecord.objects.all())
#         assert Decimal("20.00") - invoices[0].cost_due < Decimal("0.01")

#     def test_update_quantity_on_invoice_invoice_now(
#         self,
#         addon_test_common_setup,
#     ):
#         num_subscriptions = 0
#         setup_dict = addon_test_common_setup(
#             num_subscriptions=num_subscriptions,
#             auth_method="api_key",
#             user_org_and_api_key_org_different=False,
#         )

#         response = setup_dict["client"].post(
#             reverse("subscription-list"),
#             data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
#             content_type="application/json",
#         )
#         assert response.status_code == status.HTTP_201_CREATED
#         data = response.json()
#         start_date = data["start_date"]
#         end_date = data["end_date"]
#         auto_renew = data["auto_renew"]
#         subscription_filters = data["subscription_filters"]
#         billing_plan_id = data["billing_plan"]["plan_id"]
#         fully_billed = data["fully_billed"]
#         customer_id =
#         assert auto_renew is True
#         assert len(subscription_filters) == 0
#         assert setup_dict["billing_plan"].plan.plan_id.hex in billing_plan_id
#         assert fully_billed is False

#         invoice_before = len(Invoice.objects.all())
#         addon_payload = {
#             "addon_version_id": setup_dict["flat_fee_addon"]
#             .versions.first()
#             .version_id,
#             "quantity": 1,
#         }
#         setup_dict[
#             "flat_fee_addon_spec"
#         ].flat_fee_invoicing_behavior_on_attach = (
#             AddOnSpecification.FlatFeeInvoicingBehaviorOnAttach.INVOICE_ON_SUBSCRIPTION_END
#         )
#         setup_dict["flat_fee_addon_spec"].save()
#         sub = SubscriptionRecord.objects.first()
#         response = setup_dict["client"].post(
#             reverse(
#                 "subscription-attach_addon",
#                 kwargs={"subscription_id": sub.subscription_record_id},
#             ),
#             data=json.dumps(addon_payload, cls=DjangoJSONEncoder),
#             content_type="application/json",
#         )
#         invoice_after = len(Invoice.objects.all())
#         assert response.status_code == status.HTTP_201_CREATED
#         data = response.json()
#         assert data["start_date"] != start_date
#         assert data["end_date"] == end_date
#         assert invoice_before == invoice_after

#         # update the addon - add 1 to quantity but not invoiced before so chill
#         update_addon_query_params = {
#             "addon_version_id": setup_dict["recurring_addon"]
#             .versions.first()
#             .version_id,
#             "attached_customer_id": customer_id,
#             "attached_plan_id": billing_plan_id,
#         }
#         update_addon_payload = {
#             "quantity": 2,
#             "invoicing_behavior": "add_to_next_invoice",
#         }
#         response = setup_dict["client"].post(
#             reverse("subscription-list_addon")
#             + "?"
#             + urllib.parse.urlencode(update_addon_query_params),
#             data=json.dumps(update_addon_payload, cls=DjangoJSONEncoder),
#             content_type="application/json",
#         )
#         assert response.status_code == status.HTTP_200_OK
#         data = response.json()[0]

#         invoices = generate_invoice(SubscriptionRecord.objects.all())
#         # already charged so should be 0
#         assert Decimal("0") - invoices[0].cost_due < Decimal("0.01")

#     def test_update_quantity_on_invoice_reduce_quantity(
#         self,
#         addon_test_common_setup,
#     ):
#         num_subscriptions = 0
#         setup_dict = addon_test_common_setup(
#             num_subscriptions=num_subscriptions,
#             auth_method="api_key",
#             user_org_and_api_key_org_different=False,
#         )

#         response = setup_dict["client"].post(
#             reverse("subscription-list"),
#             data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
#             content_type="application/json",
#         )
#         assert response.status_code == status.HTTP_201_CREATED
#         data = response.json()
#         start_date = data["start_date"]
#         end_date = data["end_date"]
#         auto_renew = data["auto_renew"]
#         subscription_filters = data["subscription_filters"]
#         billing_plan_id = data["billing_plan"]["plan_id"]
#         fully_billed = data["fully_billed"]
#         customer_id =
#         assert auto_renew is True
#         assert len(subscription_filters) == 0
#         assert setup_dict["billing_plan"].plan.plan_id.hex in billing_plan_id
#         assert fully_billed is False

#         invoice_before = len(Invoice.objects.all())
#         addon_payload = {
#             "addon_version_id": setup_dict["flat_fee_addon"]
#             .versions.first()
#             .version_id,
#             "quantity": 5,
#         }
#         sub = SubscriptionRecord.objects.first()
#         response = setup_dict["client"].post(
#             reverse(
#                 "subscription-attach_addon",
#                 kwargs={"subscription_id": sub.subscription_record_id},
#             ),
#             data=json.dumps(addon_payload, cls=DjangoJSONEncoder),
#             content_type="application/json",
#         )
#         invoice_after = len(Invoice.objects.all())
#         assert response.status_code == status.HTTP_201_CREATED
#         data = response.json()
#         assert data["start_date"] != start_date
#         assert data["end_date"] == end_date
#         assert invoice_before + 1 == invoice_after

#         # update the addon - add 1 to quantity but not invoiced before so chill
#         update_addon_query_params = {
#             "addon_version_id": setup_dict["recurring_addon"]
#             .versions.first()
#             .version_id,
#             "attached_customer_id": customer_id,
#             "attached_plan_id": billing_plan_id,
#         }
#         update_addon_payload = {
#             "quantity": 2,
#             "invoicing_behavior": "invoice_now",
#         }
#         baladj_before = len(CustomerBalanceAdjustment.objects.all())
#         response = setup_dict["client"].post(
#             reverse("subscription-list_addon")
#             + "?"
#             + urllib.parse.urlencode(update_addon_query_params),
#             data=json.dumps(update_addon_payload, cls=DjangoJSONEncoder),
#             content_type="application/json",
#         )
#         baladj_after = len(CustomerBalanceAdjustment.objects.all())
#         assert response.status_code == status.HTTP_200_OK
#         data = response.json()[0]
#         assert baladj_before == baladj_after - 1
#         baladj = CustomerBalanceAdjustment.objects.all().last()
#         assert baladj.amount == Decimal("30.00")  # reduced from 5 to 2

#         invoices = generate_invoice(SubscriptionRecord.objects.all())
#         # already charged so should be 0
#         assert Decimal("0") - invoices[0].cost_due < Decimal("0.01")


@pytest.mark.django_db(transaction=True)
class TestCancelAddOn:
    def test_cancel_and_bill_now_works(self, addon_test_common_setup):
        num_subscriptions = 0
        setup_dict = addon_test_common_setup(
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
        data = response.json()
        start_date = data["start_date"]
        end_date = data["end_date"]
        auto_renew = data["auto_renew"]
        subscription_filters = data["subscription_filters"]
        billing_plan_id = data["billing_plan"]["plan_id"]
        fully_billed = data["fully_billed"]

        assert auto_renew is True
        assert len(subscription_filters) == 0
        assert setup_dict["billing_plan"].plan.plan_id.hex in billing_plan_id
        assert fully_billed is False

        invoice_before = len(Invoice.objects.all())
        addon_payload = {
            "addon_version_id": setup_dict["recurring_addon"]
            .versions.first()
            .version_id,
            "quantity": 1,
        }
        sub = SubscriptionRecord.objects.first()
        response = setup_dict["client"].post(
            reverse(
                "subscription-attach_addon",
                kwargs={"subscription_id": sub.subscription_record_id},
            ),
            data=json.dumps(addon_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        invoice_after = len(Invoice.objects.all())
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["start_date"] != start_date
        assert data["end_date"] == end_date
        assert invoice_before + 1 == invoice_after
        recent_inv = Invoice.objects.all().order_by("-issue_date").first()
        # prorated flat fee
        assert (
            0
            < recent_inv.cost_due
            < setup_dict["recurring_addon_version"].recurring_charges.first().amount
        )
        assert data["auto_renew"] is True

        # cancel the addon
        cancel_addon_payload = {
            "flat_fee_behavior": "charge_full",
            "invoicing_behavior": "invoice_now",
        }
        response = setup_dict["client"].post(
            reverse(
                "subscription-cancel_addon",
                kwargs={
                    "subscription_id": sub.subscription_record_id,
                    "addon_version_id": setup_dict["recurring_addon"]
                    .versions.first()
                    .version_id,
                },
            ),
            data=json.dumps(cancel_addon_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert parser.parse(data["end_date"]) < now_utc()
        assert data["auto_renew"] is False

        recenter_inv = Invoice.objects.all().order_by("-issue_date").first()
        # prorated flat fee
        assert (
            recenter_inv.cost_due + recent_inv.cost_due
            == setup_dict["recurring_addon_version"].recurring_charges.first().amount
        )

    def test_cancel_and_bill_later(self, addon_test_common_setup):
        num_subscriptions = 0
        setup_dict = addon_test_common_setup(
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
        data = response.json()
        start_date = data["start_date"]
        end_date = data["end_date"]
        auto_renew = data["auto_renew"]
        subscription_filters = data["subscription_filters"]
        billing_plan_id = data["billing_plan"]["plan_id"]
        fully_billed = data["fully_billed"]

        assert auto_renew is True
        assert len(subscription_filters) == 0
        assert setup_dict["billing_plan"].plan.plan_id.hex in billing_plan_id
        assert fully_billed is False

        invoice_before = len(Invoice.objects.all())
        addon_payload = {
            "addon_version_id": setup_dict["recurring_addon"]
            .versions.first()
            .version_id,
            "quantity": 1,
        }
        sub = SubscriptionRecord.objects.first()
        response = setup_dict["client"].post(
            reverse(
                "subscription-attach_addon",
                kwargs={"subscription_id": sub.subscription_record_id},
            ),
            data=json.dumps(addon_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        invoice_after = len(Invoice.objects.all())
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["start_date"] != start_date
        assert data["end_date"] == end_date
        assert invoice_before + 1 == invoice_after
        recent_inv = Invoice.objects.all().order_by("-issue_date").first()
        # prorated flat fee
        assert (
            0
            < recent_inv.cost_due
            < setup_dict["recurring_addon_version"].recurring_charges.first().amount
        )
        assert data["auto_renew"] is True

        # cancel the addon
        cancel_addon_payload = {
            "flat_fee_behavior": "refund",
            "invoicing_behavior": "add_to_next_invoice",
        }
        baladj_before = len(CustomerBalanceAdjustment.objects.all())
        sub = SubscriptionRecord.objects.first()
        response = setup_dict["client"].post(
            reverse(
                "subscription-cancel_addon",
                kwargs={
                    "subscription_id": sub.subscription_record_id,
                    "addon_version_id": setup_dict["recurring_addon"]
                    .versions.first()
                    .version_id,
                },
            ),
            data=json.dumps(cancel_addon_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert parser.parse(data["end_date"]) < now_utc()
        assert data["auto_renew"] is False
        generate_invoice(SubscriptionRecord.objects.all())
        baladj_after = len(CustomerBalanceAdjustment.objects.all())
        assert baladj_before == baladj_after - 1
