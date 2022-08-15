from metering_billing.models import Event, Customer, Subscription, Invoice


def generate_invoice(subscription):
    """
    Generate an invoice for a subscription.
    """
    # Get the customer
    customer_obj = subscription.customer

    # Get the billing plan
    billing_plan = subscription.billing_plan

    billable_metric = billing_plan.billable_metric
    aggregation_type = billable_metric.get_aggregation_type()

    # Get the events for the subscription
    events = Event.objects.all().filter(event_name=billable_metric.event_name)

    if aggregation_type == "count":
        # Get the total number of events
        num_events = len(events)
        usage_cost = billing_plan.get_usage_cost_count_aggregation(num_events)

    else:
        usage_cost = 0.0

    # Get the total cost of the subscription
    total_cost = billing_plan.flat_rate + usage_cost

    # Create the invoice
    invoice = Invoice(
        cost_due=total_cost,
        currency=billing_plan.currency,
        issue_date=subscription.end_date,
        subscription=subscription,
        customer_name=customer_obj.name,
        customer_billing_id=customer_obj.billing_id,
    )
    invoice.save()

    # Create the events for the invoice
    return invoice
