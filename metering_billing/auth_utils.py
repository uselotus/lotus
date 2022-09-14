from curses import keyname

from metering_billing.exceptions import (
    NoMatchingAPIKey,
    OrganizationMismatch,
    UserNoOrganization,
)
from metering_billing.models import APIToken
from metering_billing.permissions import HasUserAPIKey


# AUTH METHODS
def get_organization_from_key(key):
    try:
        api_key = APIToken.objects.get_from_key(key)
    except:
        raise NoMatchingAPIKey
    organization = api_key.organization
    return organization


def get_user_org_or_raise_no_org(request):
    organization_user = request.user.organization
    if organization_user is None:
        raise UserNoOrganization()
    return organization_user


def parse_organization(request):
    is_authenticated = request.user.is_authenticated
    api_key = HasUserAPIKey().get_key(request)
    if api_key is not None and is_authenticated:
        organization_api_token = get_organization_from_key(api_key)
        organization_user = get_user_org_or_raise_no_org(request)
        if organization_user.pk != organization_api_token.pk:
            raise OrganizationMismatch()
        return organization_api_token
    elif api_key is not None:
        return get_organization_from_key(api_key)
    elif is_authenticated:
        return get_user_org_or_raise_no_org(request)
