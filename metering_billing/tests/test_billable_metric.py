import json

import pytest
from dateutil import parser
from dateutil.relativedelta import relativedelta
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from lotus.urls import router
from metering_billing.models import (
    BillableMetric,
    BillingPlan,
    Customer,
    Event,
    PlanComponent,
)
from metering_billing.utils import calculate_sub_pc_usage_revenue, get_metric_usage
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APIClient


@pytest.fixture
def billable_metric_test_common_setup(
    generate_org_and_api_key,
    add_billable_metrics_to_org,
    add_users_to_org,
    api_client_with_api_key_auth,
):
    def do_billable_metric_test_common_setup(
        *, num_billable_metrics, auth_method, user_org_and_api_key_org_different
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

        # set up billable_metrics
        if num_billable_metrics > 0:
            setup_dict["org_billable_metrics"] = add_billable_metrics_to_org(
                org, n=num_billable_metrics
            )
            setup_dict["org2_billable_metrics"] = add_billable_metrics_to_org(
                org2, n=num_billable_metrics
            )
        print("noooo")

        return setup_dict

    return do_billable_metric_test_common_setup


@pytest.fixture
def insert_billable_metric_payload():
    payload = {
        "event_name": "test_event",
        "property_name": "test_property",
        "aggregation_type": "sum",
    }
    return payload


@pytest.mark.django_db(transaction=True)
class TestInsertBillableMetric:
    """Testing the POST of BillableMetrics endpoint:
    POST: Return list of billable_metrics associated with the organization with API key / user.
    partitions:
        auth_method: api_key, session_auth, both
        num_billable_metric_before_insert: 0, >0
        user_org_and_api_key_org_different: true, false
        billable_metric_id
    """

    def test_api_key_can_create_billable_metric_empty_before(
        self,
        billable_metric_test_common_setup,
        insert_billable_metric_payload,
        get_billable_metrics_in_org,
    ):
        # covers num_billable_metrics_before_insert = 0, has_org_api_key=true, user_in_org=true, user_org_and_api_key_org_different=false
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )

        response = setup_dict["client"].post(
            reverse("metric-list"),
            data=json.dumps(insert_billable_metric_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0  # check that the response is not empty
        assert len(get_billable_metrics_in_org(setup_dict["org"])) == 1

    def test_session_auth_can_create_billable_metric_nonempty_before(
        self,
        billable_metric_test_common_setup,
        insert_billable_metric_payload,
        get_billable_metrics_in_org,
    ):
        # covers num_billable_metrics_before_insert = 0, has_org_api_key=true, user_in_org=true, user_org_and_api_key_org_different=false, authenticated=true
        num_billable_metrics = 5
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="session_auth",
            user_org_and_api_key_org_different=False,
        )

        response = setup_dict["client"].post(
            reverse("metric-list"),
            data=json.dumps(insert_billable_metric_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) > 0
        assert (
            len(get_billable_metrics_in_org(setup_dict["org"]))
            == num_billable_metrics + 1
        )

    def test_user_org_and_api_key_different_reject_creation(
        self,
        billable_metric_test_common_setup,
        insert_billable_metric_payload,
        get_billable_metrics_in_org,
    ):
        # covers user_org_and_api_key_org_different = True
        num_billable_metrics = 3
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="both",
            user_org_and_api_key_org_different=True,
        )

        response = setup_dict["client"].post(
            reverse("metric-list"),
            data=json.dumps(insert_billable_metric_payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_406_NOT_ACCEPTABLE
        assert (
            len(get_billable_metrics_in_org(setup_dict["org"])) == num_billable_metrics
        )
        assert (
            len(get_billable_metrics_in_org(setup_dict["org2"])) == num_billable_metrics
        )

    def test_billable_metric_exists_with_null_property_reject_creation(
        self,
        billable_metric_test_common_setup,
        insert_billable_metric_payload,
        get_billable_metrics_in_org,
    ):
        num_billable_metrics = 3
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )

        payload = insert_billable_metric_payload
        payload["property_name"] = None
        BillableMetric.objects.create(**{**payload, "organization": setup_dict["org"]})
        response = setup_dict["client"].post(
            reverse("metric-list"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        print(response.data)
        assert response.status_code == status.HTTP_409_CONFLICT
        assert (
            len(get_billable_metrics_in_org(setup_dict["org"]))
            == num_billable_metrics + 1
        )
        assert (
            len(get_billable_metrics_in_org(setup_dict["org2"])) == num_billable_metrics
        )


@pytest.mark.django_db(transaction=True)
class TestCalculateBillableMetric:
    def test_count_unique(self, billable_metric_test_common_setup):
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )
        billable_metric = BillableMetric.objects.create(
            organization=setup_dict["org"],
            property_name="test_property",
            event_name="test_event",
            aggregation_type="unique",
        )
        time_created = parser.parse("2021-01-01T06:00:00Z")
        customer = baker.make(Customer, organization=setup_dict["org"])
        baker.make(
            Event,
            event_name="test_event",
            properties={"test_property": "foo"},
            organization=setup_dict["org"],
            time_created=time_created,
            customer=customer,
            _quantity=5,
        )
        baker.make(
            Event,
            event_name="test_event",
            properties={"test_property": "bar"},
            organization=setup_dict["org"],
            time_created=time_created,
            customer=customer,
            _quantity=5,
        )
        metric_usage_qs = get_metric_usage(
            billable_metric,
            query_start_date="2021-01-01",
            query_end_date="2021-01-01",
            customer=customer,
        )
        metric_usage = sum(metric_usage_qs.values_list("usage_qty", flat=True))

        assert metric_usage == 2

    def test_stateful(self, billable_metric_test_common_setup):
        num_billable_metrics = 0
        setup_dict = billable_metric_test_common_setup(
            num_billable_metrics=num_billable_metrics,
            auth_method="api_key",
            user_org_and_api_key_org_different=False,
        )
        billable_metric = BillableMetric.objects.create(
            organization=setup_dict["org"],
            event_name="number_of_users",
            property_name="number",
            aggregation_type="max",
            event_type="stateful",
            carries_over=True,
        )
        time_created = parser.parse("2021-01-01T06:00:00Z")
        customer = baker.make(Customer, organization=setup_dict["org"])
        event_times = [time_created] + [
            time_created + relativedelta(days=i) for i in range(19)
        ]
        properties = (
            3 * [{"number": 1}]
            + 3 * [{"number": 2}]
            + 3 * [{"number": 3}]
            + 3 * [{"number": 4}]
            + 3 * [{"number": 5}]
            + 3 * [{"number": 6}]
            + [{"number": 3}]
        )
        baker.make(
            Event,
            event_name="number_of_users",
            properties=iter(properties),
            organization=setup_dict["org"],
            time_created=iter(event_times),
            customer=customer,
            _quantity=19,
        )
        plan_component = PlanComponent.objects.create(
            billable_metric=billable_metric,
            free_metric_quantity=3,
            cost_per_metric=100,
            metric_amount_per_cost=1,
        )
        billing_plan = BillingPlan.objects.create(
            organization=setup_dict["org"],
            interval="month",
            flat_rate=0,
            pay_in_advance=True,
            name="test_plan",
        )
        billing_plan.components.add(plan_component)
        billing_plan.save()

        usage_revenue_dict = calculate_sub_pc_usage_revenue(
            plan_component,
            customer=customer,
            plan_start_date="2021-01-01",
            plan_end_date="2021-01-30",
            time_period_agg="date",
        )
        metric_usage = sum(d["usage_qty"] for _, d in usage_revenue_dict.items())
        metric_revenue = sum(d["revenue"] for _, d in usage_revenue_dict.items())

        assert metric_usage == 101
        assert metric_revenue == 1800
