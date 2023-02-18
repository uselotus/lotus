import logging
from decimal import Decimal
from typing import Dict, Tuple

import taxjar
from django.conf import settings
from django.core.cache import cache
from metering_billing.models import SubscriptionRecord

TAXJAR_API_KEY = settings.TAXJAR_API_KEY
logger = logging.getLogger("django.server")


def get_lotus_tax_rates(customer, organization) -> Tuple[Decimal, bool]:
    # Check customer tax rate first
    customer_tax_rate = customer.tax_rate
    if customer_tax_rate:
        return customer_tax_rate, True

    # Otherwise, check organization tax rate
    organization_tax_rate = organization.tax_rate
    if organization_tax_rate:
        return organization_tax_rate, True

    # If no tax rate found, return unsuccessful
    return 0, False


def get_taxjar_tax_rates(
    customer, organization, plan, draft=True, amount=100
) -> Tuple[Dict[SubscriptionRecord, Decimal], bool]:
    try:
        client = taxjar.Client(api_key=settings.TAXJAR_API_KEY)
    except Exception:
        return 0, False
    from_address = organization.get_address()
    if not from_address:
        return 0, False
    to_address = customer.get_shipping_address()
    if not to_address:
        return 0, False

    # Build cache key from addresses
    from_cache_key = (
        f"{from_address.line1 or 'None'}:"
        f"{from_address.line2 or 'None'}:{from_address.city or 'None'}:"
        f"{from_address.state or 'None'}:{from_address.postal_code or 'None'}:"
        f"{from_address.country or 'None'}"
    )
    to_cache_key = (
        f"{to_address.line1 or 'None'}:"
        f"{to_address.line2 or 'None'}:{to_address.city or 'None'}:"
        f"{to_address.state or 'None'}:{to_address.postal_code or 'None'}:"
        f"{to_address.country or 'None'}"
    )
    cache_key = f"{from_cache_key}:{to_cache_key}"
    taxjar_code = plan.taxjar_code or "30070"

    # Check if tax rate is already in cache
    plan_cache_key = f"{cache_key}:{taxjar_code}"
    tax_rate = cache.get(plan_cache_key)
    if tax_rate == "ERROR" and draft:
        return 0, False
    if tax_rate is not None and draft:
        return tax_rate, True
    # Query taxjar for tax rate
    try:
        response = client.tax_for_order(
            {
                "amount": amount,
                "from_country": from_address.country,
                "from_zip": from_address.postal_code,
                "from_state": from_address.state,
                "from_city": from_address.city,
                "from_street": from_address.line1,
                "to_street": to_address.line1,
                "to_city": to_address.city,
                "to_state": to_address.state,
                "to_country": to_address.country,
                "to_zip": to_address.postal_code,
                "shipping": 0,
            }
        )
    except taxjar.exceptions.TaxJarConnectionError as e:
        logger.error(f"TaxJarConnectionError: {e.__dict__}")
        cache.set(plan_cache_key, "ERROR", 24 * 60 * 60)
        return 0, False
    except taxjar.exceptions.TaxJarResponseError as e:
        logger.error(f"TaxJarResponseError: {e.__dict__}")
        cache.set(plan_cache_key, "ERROR", 24 * 60 * 60)
        return 0, False
    except Exception as e:
        logger.error(f"Unknown TaxJarException: {e.__dict__}")
        cache.set(plan_cache_key, "ERROR", 24 * 60 * 60)
        return 0, False

    tax_rate = Decimal(response.rate * 100)  # to keep in line with lotus tax rates
    cache.set(plan_cache_key, tax_rate, 30 * 24 * 60 * 60)

    return tax_rate, True
