from django.core.management.base import BaseCommand
from metering_billing.models import (
    Customer,
    CustomerBalanceAdjustment,
    Invoice,
    Organization,
    Plan,
)
from metering_billing.serializers.model_serializers import APITokenSerializer


class Command(BaseCommand):
    "Django command to execute calculate invoice"

    def handle(self, *args, **options):
        org = Organization.objects.create(
            organization_name="test",
        )
        cust = Customer.objects.create(
            organization=org,
            customer_name="test",
        )

        # API key
        _, key = APITokenSerializer().create(
            {
                "name": "test",
                "organization": org,
            }
        )
        print(f"KEY={key}")

        # plan
        plan = Plan.objects.create(
            organization=org,
            name="test",
        )
        print(f"PLAN_ID={plan.plan_id.hex}")

        # invoice
        invoice = Invoice.objects.create(
            organization=org,
            invoice_number="1",
        )
        print(f"INVOICE_ID={invoice.invoice_id.hex}")

        # credit
        credit = CustomerBalanceAdjustment.objects.create(
            organization=org,
            customer=cust,
            amount=100,
        )
        print(f"CREDIT_ID={credit.credit_id.hex}")
