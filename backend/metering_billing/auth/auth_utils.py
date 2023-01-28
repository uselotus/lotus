import base64
import hashlib
import logging

from django.core.cache import cache
from django.http import HttpResponseBadRequest
from django.utils.encoding import force_bytes, smart_str
from django.utils.translation import gettext_lazy as _
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from metering_billing.exceptions import (
    NoMatchingAPIKey,
    OrganizationMismatch,
    UserNoOrganization,
)
from metering_billing.models import APIToken
from metering_billing.permissions import HasUserAPIKey
from metering_billing.utils import now_utc

LOGGER = logging.getLogger(__name__)


def default_username_algo(email):
    """Generate username for the Django user.

    :arg str/unicode email: the email address to use to generate a username

    :returns: str/unicode

    """
    # bluntly stolen from django-browserid
    # store the username as a base64 encoded sha224 of the email address
    # this protects against data leakage because usernames are often
    # treated as public identifiers (so we can't use the email address).
    username = base64.urlsafe_b64encode(
        hashlib.sha1(force_bytes(email)).digest()
    ).rstrip(b"=")

    return smart_str(username)


# AUTH METHODS
def get_organization_from_key(key):
    try:
        api_key = APIToken.objects.get_from_key(key)
    except Exception:
        raise NoMatchingAPIKey(f"API Key starting with {key[:5]} not known")
    organization = api_key.organization
    return organization


def get_user_org_or_raise_no_org(request):
    organization_user = request.user.organization
    if organization_user is None:
        raise UserNoOrganization(
            "User does not have an organization. This is unexpected behavior, please contact support."
        )
    return organization_user


def parse_organization(request):
    is_authenticated = request.user.is_authenticated
    api_key = HasUserAPIKey().get_key(request)
    if api_key is not None and is_authenticated:
        organization_api_token = get_organization_from_key(api_key)
        organization_user = get_user_org_or_raise_no_org(request)
        if organization_user.pk != organization_api_token.pk:
            raise OrganizationMismatch(
                "Organization for API key and session did not match"
            )
        return organization_api_token
    elif api_key is not None:
        return get_organization_from_key(api_key)
    elif is_authenticated:
        return get_user_org_or_raise_no_org(request)


class KnoxTokenScheme(OpenApiAuthenticationExtension):
    target_class = "knox.auth.TokenAuthentication"
    name = "knoxTokenAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": _('Token-based authentication with required prefix "%s"')
            % "Token",
        }


def fast_api_key_validation_and_cache(request):
    try:
        key = request.META["HTTP_X_API_KEY"]
    except KeyError:
        meta_dict = {k.lower(): v for k, v in request.META.items()}
        if "http_x_api_key".lower() in meta_dict:
            key = meta_dict["http_x_api_key"]
        else:
            return HttpResponseBadRequest("No API key found in request"), False
    prefix, _, _ = key.partition(".")
    organization_pk = cache.get(prefix)
    if not organization_pk:
        try:
            api_key = APIToken.objects.get_from_key(key)
        except Exception:
            return HttpResponseBadRequest("Invalid API key"), False
        organization_pk = api_key.organization.pk
        expiry_date = api_key.expiry_date
        timeout = (
            60 * 60 * 24
            if expiry_date is None
            else (expiry_date - now_utc()).total_seconds()
        )
        cache.set(prefix, organization_pk, timeout)
    return organization_pk, True
