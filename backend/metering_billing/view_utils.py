from metering_billing.payment_providers import PAYMENT_PROVIDER_MAP


def sync_payment_provider_customers(organization):
    """
    For every payment provider an organization has, sync all customers
    """
    ret = []
    for pp_name, connector in PAYMENT_PROVIDER_MAP.items():
        if connector.organization_connected(organization):
            connector.import_customers(organization)
            ret.append(pp_name)
    return ret
