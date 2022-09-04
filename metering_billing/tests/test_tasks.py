import base64
import itertools
import json
from datetime import datetime, timedelta

import pytest
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from metering_billing.models import (
    BillableMetric,
    BillingPlan,
    Event,
    Invoice,
    Organization,
    PlanComponent,
    Subscription,
    User,
)
from metering_billing.tasks import calculate_invoice
from model_bakery import baker
from rest_framework import status


@pytest.mark.django_db
class TestGenerateInvoiceSynchrous:
    def test_generate_invoice(self, generate_org_and_api_key, add_customers_to_org):
        org, _ = generate_org_and_api_key()
        (customer,) = add_customers_to_org(org, n=1)
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
            time_created=datetime.now().date() - timedelta(days=14),
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
        billing_plan = baker.make(
            BillingPlan,
            organization=org,
            interval="month",
            name="test_plan",
            description="test_plan for testing",
        )
        plan_component_set = baker.make(
            PlanComponent,
            billable_metric=itertools.cycle(metric_set),
            free_metric_quantity=itertools.cycle([50, 0, 1]),
            cost_per_metric=itertools.cycle([5, 0.05, 2]),
            metric_amount_per_cost=itertools.cycle([100, 1, 1]),
            _quantity=3,
        )
        billing_plan.components.add(*plan_component_set)
        billing_plan.save()
        subscription = baker.make(
            Subscription,
            organization=org,
            customer=customer,
            billing_plan=billing_plan,
            start_date=datetime.now().date() - timedelta(days=35),
            end_date=datetime.now().date() - timedelta(days=7),
            status="active",
        )

        ending_subscriptions = Subscription.objects.filter(
            status="active", end_date__lte=datetime.now().date()
        )
        assert len(ending_subscriptions) == 1

        calculate_invoice()

        ending_subscriptions = Subscription.objects.filter(
            status="active", end_date__lte=datetime.now().date()
        )
        assert len(ending_subscriptions) == 0
        invoice_set = Invoice.objects.filter(
            organization=org,
            customer=customer,
            status="not_sent",
            subscription=subscription,
        )

        assert len(invoice_set) == 1
