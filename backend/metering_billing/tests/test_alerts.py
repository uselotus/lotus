import itertools
import json
from datetime import timedelta

import pytest
from django.urls import reverse
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APIClient

from metering_billing.aggregation.billable_metrics import METRIC_HANDLER_MAP
from metering_billing.models import (
    Event,
    Metric,
    PlanComponent,
    PlanVersion,
    PriceTier,
    SubscriptionRecord,
    UsageAlert,
    UsageAlertResult,
)
from metering_billing.serializers.serializer_utils import DjangoJSONEncoder
from metering_billing.tasks import refresh_alerts_inner
from metering_billing.utils import now_utc


@pytest.fixture
def alerts_test_common_setup(
    generate_org_and_api_key,
    add_users_to_org,
    api_client_with_api_key_auth,
    add_subscription_record_to_org,
    add_customers_to_org,
    add_product_to_org,
    add_plan_to_product,
):
    def do_alerts_test_common_setup(
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
        )
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
            "metric_id": "metric_" + metric_set[0].metric_id.hex,
            "plan_version_id": billing_plan.version_id.hex,
            "threshold": 50,
        }
        setup_dict["payload"] = payload
        payload = {
            "name": "test_subscription",
            "start_date": now_utc() - timedelta(days=5),
            "customer_id": customer.customer_id,
            "version_id": billing_plan.version_id,
        }
        setup_dict["payload_sr"] = payload
        setup_dict["customer"] = customer

        return setup_dict

    return do_alerts_test_common_setup


@pytest.mark.django_db(transaction=True)
class TestUsageAlerts:
    def test_create_usage_alert_works_new_sr_creates_alert_result(
        self, alerts_test_common_setup
    ):
        setup_dict = alerts_test_common_setup(
            num_subscriptions=0, auth_method="session_auth"
        )

        before_alerts = UsageAlert.objects.all().count()
        assert before_alerts is not None

        response = setup_dict["client"].post(
            reverse("usage_alert-list"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        after_alerts = UsageAlert.objects.all().count()
        assert after_alerts == before_alerts + 1

        alert_results_before = UsageAlertResult.objects.all().count()
        assert alert_results_before == 0

        subs_before = SubscriptionRecord.objects.all().count()
        response = setup_dict["client"].post(
            reverse("subscription-list"),
            data=json.dumps(setup_dict["payload_sr"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        subs_after = SubscriptionRecord.objects.all().count()
        assert subs_after == subs_before + 1

        alert_results_after = UsageAlertResult.objects.all().count()
        assert alert_results_after == alert_results_before + 1

    def test_create_usage_alert_creates_alert_result_with_existing_susbcription_record(
        self, alerts_test_common_setup
    ):
        setup_dict = alerts_test_common_setup(
            num_subscriptions=0, auth_method="session_auth"
        )

        before_alerts = UsageAlert.objects.all().count()
        assert before_alerts is not None
        subs_before = SubscriptionRecord.objects.all().count()
        response = setup_dict["client"].post(
            reverse("subscription-list"),
            data=json.dumps(setup_dict["payload_sr"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        subs_after = SubscriptionRecord.objects.all().count()
        assert subs_after == subs_before + 1
        alert_results_before = UsageAlertResult.objects.all().count()
        assert alert_results_before is not None

        response = setup_dict["client"].post(
            reverse("usage_alert-list"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        after_alerts = UsageAlert.objects.all().count()
        assert after_alerts == before_alerts + 1

        alert_results_after = UsageAlertResult.objects.all().count()
        assert alert_results_after == alert_results_before + 1

    def test_usage_alert_result_gets_triggered(self, alerts_test_common_setup):
        setup_dict = alerts_test_common_setup(
            num_subscriptions=0, auth_method="session_auth"
        )

        before_alerts = UsageAlert.objects.all().count()
        assert before_alerts is not None
        subs_before = SubscriptionRecord.objects.all().count()
        response = setup_dict["client"].post(
            reverse("subscription-list"),
            data=json.dumps(setup_dict["payload_sr"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        subs_after = SubscriptionRecord.objects.all().count()
        assert subs_after == subs_before + 1
        alert_results_before = UsageAlertResult.objects.all().count()
        assert alert_results_before is not None

        response = setup_dict["client"].post(
            reverse("usage_alert-list"),
            data=json.dumps(setup_dict["payload"], cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        after_alerts = UsageAlert.objects.all().count()
        assert after_alerts == before_alerts + 1

        alert_results_after = UsageAlertResult.objects.all().count()
        assert alert_results_after == alert_results_before + 1

        alert_result = UsageAlertResult.objects.all().first()
        assert alert_result.triggered_count == 0

        refresh_alerts_inner()

        alert_result = UsageAlertResult.objects.all().first()
        assert alert_result.triggered_count == 0

        Event.objects.create(
            organization=setup_dict["org"],
            event_name="email_sent",
            cust_id=setup_dict["customer"].customer_id,
            time_created=now_utc(),
            properties={"num_characters": 70},
        )

        refresh_alerts_inner()

        alert_result = UsageAlertResult.objects.all().first()
        assert alert_result.triggered_count == 1
        assert alert_result.triggered_count == 1
