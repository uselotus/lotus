import base64
import itertools
import json
from datetime import datetime, timedelta

import pytest
import stripe
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from metering_billing.models import (
    BillableMetric,
    BillingPlan,
    Customer,
    Event,
    Invoice,
    PlanComponent,
    Subscription,
)
from metering_billing.tasks import calculate_invoice, update_invoice_status
from metering_billing.utils.enums import INVOICE_STATUS
from model_bakery import baker
from rest_framework.test import APIClient


@pytest.fixture
def task_test_common_setup(
    generate_org_and_api_key, add_customers_to_org, add_users_to_org
):
    def do_task_test_common_setup():
        setup_dict = {}
        org, _ = generate_org_and_api_key()
        setup_dict["org"] = org
        (customer,) = add_customers_to_org(org, n=1)
        stripe_cust = stripe.Customer.create(
            email="jenny.rosen@example.com",
            payment_method="pm_card_visa",
            invoice_settings={"default_payment_method": "pm_card_visa"},
        )
        customer.payment_providers["stripe"] = {"id": stripe_cust.id}
        customer.sources = ["stripe", "lotus"]
        customer.email = "jenny.rosen@example.com"
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
            start_date=datetime.now().date() - timedelta(days=35),
            end_date=datetime.now().date() - timedelta(days=5),
            status="active",
        )
        setup_dict["subscription"] = subscription

        client = APIClient()
        (user,) = add_users_to_org(org, n=1)
        client.force_authenticate(user=user)
        setup_dict["user"] = user
        setup_dict["client"] = client

        return setup_dict

    return do_task_test_common_setup


@pytest.mark.django_db(transaction=True)
class TestGenerateInvoiceSynchrous:
    def test_generate_invoice(self, task_test_common_setup):
        setup_dict = task_test_common_setup()

        ending_subscriptions = Subscription.objects.filter(
            status="active", end_date__lt=datetime.now().date()
        )
        assert len(ending_subscriptions) == 1

        prev_invoices = len(Invoice.objects.all())

        calculate_invoice()

        ending_subscriptions = Subscription.objects.filter(
            status="active", end_date__lt=datetime.now().date()
        )
        assert len(ending_subscriptions) == 0
        invoice_set = Invoice.objects.all()

        assert len(invoice_set) == prev_invoices + 1


@pytest.mark.django_db
class TestUpdateInvoiceStatusStripe:
    def test_update_invoice_status_stripe(self, task_test_common_setup):
        setup_dict = task_test_common_setup()

        c_id = setup_dict["customer"].payment_providers["stripe"]["id"]
        payment_intent = stripe.PaymentIntent.create(
            amount=5000,
            currency="usd",
            payment_method_types=["card"],
            payment_method="pm_card_visa",
            confirm=True,
            customer=c_id,
            off_session=True,
        )

        # Create the invoice
        invoice = baker.make(
            Invoice,
            issue_date=setup_dict["subscription"].end_date,
            payment_status=INVOICE_STATUS.UNPAID,
            external_payment_obj_id=payment_intent.id,
            organization={"company_name": "bogus"},
        )

        assert invoice.payment_status != INVOICE_STATUS.PAID

        update_invoice_status()

        invoice = Invoice.objects.filter(id=invoice.id).first()
        assert invoice.payment_status == INVOICE_STATUS.PAID


@pytest.mark.django_db(transaction=True)
class TestSyncCustomersStripe:
    def test_add_customers_update_existing(self, task_test_common_setup):
        setup_dict = task_test_common_setup()
        setup_dict["customer"].payment_providers["stripe"] = {"id": "bogus"}
        setup_dict["customer"].save()
        customers_before = Customer.objects.all().count()

        payload = {}
        response = setup_dict["client"].post(
            reverse("sync_customers"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        customers_after = Customer.objects.all().count()
        assert response.status_code == 201
        assert customers_after == customers_before
        customer = Customer.objects.get(organization=setup_dict["org"])
        cust_d = customer.payment_providers["stripe"]
        assert "id" in cust_d
        assert cust_d["id"] != "bogus"
        assert "email" in cust_d
        assert "metadata" in cust_d
        assert "name" in cust_d
        assert "currency" in cust_d
        sources = customer.sources
        assert "stripe" in sources
        assert "lotus" in sources

    def test_add_customers_create_new(self, task_test_common_setup):
        setup_dict = task_test_common_setup()
        setup_dict["customer"].delete()
        customers_before = Customer.objects.all().count()

        payload = {}
        response = setup_dict["client"].post(
            reverse("sync_customers"),
            data=json.dumps(payload, cls=DjangoJSONEncoder),
            content_type="application/json",
        )

        customers_after = Customer.objects.all().count()
        assert response.status_code == 201
        assert customers_after == customers_before + 1
        customer = Customer.objects.get(organization=setup_dict["org"])
        cust_d = customer.payment_providers["stripe"]
        assert "id" in cust_d
        assert "email" in cust_d
        assert "metadata" in cust_d
        assert "name" in cust_d
        assert "currency" in cust_d
        sources = customer.sources
        assert "stripe" in sources
        assert "lotus" not in sources
