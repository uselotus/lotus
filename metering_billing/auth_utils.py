from metering_billing.exceptions import OrganizationMismatch, UserNoOrganization
from metering_billing.models import APIToken
from metering_billing.permissions import HasUserAPIKey


# AUTH METHODS
def get_organization_from_key(request):
    validator = HasUserAPIKey()
    key = validator.get_key(request)
    api_key = APIToken.objects.get_from_key(key)
    organization = api_key.organization
    return organization


def get_user_org_or_raise_no_org(request):
    organization_user = request.user.organization
    if organization_user is None:
        raise UserNoOrganization()
    return organization_user


def parse_organization(request):
    is_authenticated = request.user.is_authenticated
    has_api_key = HasUserAPIKey().get_key(request) is not None
    if has_api_key and is_authenticated:
        organization_api_token = get_organization_from_key(request)
        organization_user = get_user_org_or_raise_no_org(request)
        if organization_user.pk != organization_api_token.pk:
            raise OrganizationMismatch()
        return organization_api_token
    elif has_api_key:
        return get_organization_from_key(request)
    elif is_authenticated:
        return get_user_org_or_raise_no_org(request)
