import json

from metering_billing.models import Customer, Event, Invoice, Subscription
from metering_billing.views import get_subscription_usage


def generate_invoice(subscription):
    """
    Generate an invoice for a subscription.
    """

    usage_dict = get_subscription_usage(subscription)
    
    # Get the customer
    customer = subscription.customer
    billing_plan = subscription.billing_plan
    print("LINE ITEMS", usage_dict["plan_components_summary"])
    # Create the invoice
    invoice = Invoice.objects.create(
        cost_due=usage_dict["current_amount_due"],
        currency=billing_plan.currency,
        issue_date=subscription.end_date,
        organization=subscription.organization,
        customer_name=customer.name,
        customer=customer,
        customer_billing_id=customer.billing_id,
        subscription=subscription,
    )

    return invoice
