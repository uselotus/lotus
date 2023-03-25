import itertools
from datetime import timedelta
from decimal import Decimal

import pytest
from metering_billing.models import Event, Metric, PlanComponent, PriceTier
from metering_billing.utils import now_utc
from model_bakery import baker
from rest_framework.test import APIClient


@pytest.fixture
def components_test_common_setup(
    generate_org_and_api_key,
    add_users_to_org,
    api_client_with_api_key_auth,
    add_customers_to_org,
    add_product_to_org,
    add_plan_to_product,
    add_plan_version_to_plan,
    add_subscription_record_to_org,
):
    def do_components_test_common_setup(*, auth_method):
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
        org.subscription_filter_keys = ["email"]
        org.save()
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
            zip([50, 0.01, 1], [5, 0.05, 2], [100, 1, 1])
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
        subscription_record = add_subscription_record_to_org(
            org, plan_version, customer, now_utc() - timedelta(days=3)
        )
        setup_dict["subscription_record"] = subscription_record

        return setup_dict

    return do_components_test_common_setup


@pytest.mark.django_db(transaction=True)
class TestBulkPricing:
    def test_bulk_pricing(self, components_test_common_setup):
        setup_dict = components_test_common_setup(auth_method="api_key")
        metric = setup_dict["metrics"][0]
        component = setup_dict["billing_plan"].plan_components.get(
            billable_metric=metric
        )
        assert component.price_tiers.count() == 2
        assert (
            component.price_tiers.filter(type=PriceTier.PriceTierType.FREE).count() == 1
        )
        assert (
            component.price_tiers.filter(type=PriceTier.PriceTierType.PER_UNIT).count()
            == 1
        )

        revenue_no_bulk = component.tier_rating_function(100)
        # we have 50 free, then 1 cent per unit
        assert revenue_no_bulk == Decimal("0.50")

        # now we convert the component to bulk pricing
        component.bulk_pricing = True
        component.save()
        revenue_bulk = component.tier_rating_function(100)
        # everything charged at 1 cent per unit
        assert revenue_bulk == Decimal("1.00")

    def test_bulk_pricing_edge_case(self, components_test_common_setup):
        setup_dict = components_test_common_setup(auth_method="api_key")
        metric = setup_dict["metrics"][0]
        component = setup_dict["billing_plan"].plan_components.get(
            billable_metric=metric
        )
        assert component.price_tiers.count() == 2
        assert (
            component.price_tiers.filter(type=PriceTier.PriceTierType.FREE).count() == 1
        )
        assert (
            component.price_tiers.filter(type=PriceTier.PriceTierType.PER_UNIT).count()
            == 1
        )

        # first, lets add 2 more tiers to the component so we can test this edge case
        PriceTier.objects.create(
            plan_component=component,
            type=PriceTier.PriceTierType.PER_UNIT,
            range_start=100,
            range_end=200,
            cost_per_batch=0.05,
            metric_units_per_batch=1,
        )
        PriceTier.objects.create(
            plan_component=component,
            type=PriceTier.PriceTierType.PER_UNIT,
            range_start=200,
            range_end=300,
            cost_per_batch=0.10,
            metric_units_per_batch=1,
        )
        # this means 0-50 free, 50-100 1 cent per unit, 100-200 5 cents per unit, 200-300 10 cents per unit

        revenue_no_bulk = component.tier_rating_function(200)
        # we have 50 free, then 50 at 1 cent per unit, then 100 at 5 cents per unit, for a total of 5.50
        assert revenue_no_bulk == Decimal("5.50")

        # now we convert the component to bulk pricing
        component.bulk_pricing = True
        component.save()
        revenue_bulk = component.tier_rating_function(200)
        # everything charged at 10 cents per unit
        assert revenue_bulk == Decimal("20.00")
