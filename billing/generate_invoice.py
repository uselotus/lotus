from .models import Event, Customer, Subscription, Invoice


def generate_invoice(subscription):
    """
    Generate an invoice for a subscription.
    """
    # Get the customer
    customer_obj = subscription.customer

    # Get the billing plan
    billing_plan = subscription.billing_plan

    # Get the events for the subscription
    events = Event.objects.filter(subscription=subscription)

    # Get the total cost of the subscription
    total_cost = billing_plan.cost_per_month * subscription.months_remaining

    # Create the invoice
    invoice = Invoice(
        cost_due=total_cost,
        currency=billing_plan.currency,
        due_date=subscription.end_date,
        subscription=subscription,
    )
    invoice.save()

    # Create the events for the invoice
    for event in events:
        event.invoice = invoice
        event.save()

    return invoice
