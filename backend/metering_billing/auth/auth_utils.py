import base64
import hashlib
import json
import logging

import requests
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured, SuspiciousOperation
from django.http import HttpResponseBadRequest
from django.utils.encoding import force_bytes, smart_bytes, smart_str
from django.utils.module_loading import import_string
from django.utils.translation import gettext_lazy as _
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from josepy.b64 import b64decode
from josepy.jwk import JWK
from josepy.jws import JWS, Header
from mozilla_django_oidc.utils import import_from_settings

from metering_billing.exceptions import (
    NoMatchingAPIKey,
    OrganizationMismatch,
    UserNoOrganization,
)
from metering_billing.models import APIToken, User
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


class OIDCAuthenticationBackend(ModelBackend):
    """Override Django's authentication."""

    def __init__(self, *args, **kwargs):
        """Initialize settings."""
        self.OIDC_OP_TOKEN_ENDPOINT = self.get_settings("OIDC_OP_TOKEN_ENDPOINT")
        self.OIDC_OP_USER_ENDPOINT = self.get_settings("OIDC_OP_USER_ENDPOINT")
        self.OIDC_OP_JWKS_ENDPOINT = self.get_settings("OIDC_OP_JWKS_ENDPOINT", None)
        self.OIDC_RP_CLIENT_ID = self.get_settings("OIDC_RP_CLIENT_ID")
        self.OIDC_RP_CLIENT_SECRET = self.get_settings("OIDC_RP_CLIENT_SECRET")
        self.OIDC_RP_SIGN_ALGO = self.get_settings("OIDC_RP_SIGN_ALGO", "HS256")
        self.OIDC_RP_IDP_SIGN_KEY = self.get_settings("OIDC_RP_IDP_SIGN_KEY", None)

        if self.OIDC_RP_SIGN_ALGO.startswith("RS") and (
            self.OIDC_RP_IDP_SIGN_KEY is None and self.OIDC_OP_JWKS_ENDPOINT is None
        ):
            msg = "{} alg requires OIDC_RP_IDP_SIGN_KEY or OIDC_OP_JWKS_ENDPOINT to be configured."
            raise ImproperlyConfigured(msg.format(self.OIDC_RP_SIGN_ALGO))

        self.UserModel = get_user_model()

    @staticmethod
    def get_settings(attr, *args):
        return import_from_settings(attr, *args)

    def describe_user_by_claims(self, claims):
        email = claims.get("email")
        return "email {}".format(email)

    def filter_users_by_claims(self, claims):
        """Return all users matching the specified email."""
        email = claims.get("email")
        if not email:
            return self.UserModel.objects.none()
        return self.UserModel.objects.filter(email__iexact=email)

    def verify_claims(self, claims):
        """Verify the provided claims to decide if authentication should be allowed."""

        # Verify claims required by default configuration
        scopes = self.get_settings("OIDC_RP_SCOPES", "openid email")
        if "email" in scopes.split():
            return "email" in claims

        LOGGER.warning(
            "Custom OIDC_RP_SCOPES defined. "
            "You need to override `verify_claims` for custom claims verification."
        )

        return True

    def create_user(self, claims):
        """Return object for a newly created user account."""
        email = claims.get("email")
        username = self.get_username(claims)
        return self.UserModel.objects.create_user(username, email=email)

    def get_username(self, claims):
        """Generate username based on claims."""
        # bluntly stolen from django-browserid
        # https://github.com/mozilla/django-browserid/blob/master/django_browserid/auth.py
        username_algo = self.get_settings("OIDC_USERNAME_ALGO", None)

        if username_algo:
            if isinstance(username_algo, str):
                username_algo = import_string(username_algo)
            return username_algo(claims.get("email"))

        return default_username_algo(claims.get("email"))

    def update_user(self, user, claims):
        """Update existing user with new claims, if necessary save, and return user"""
        return user

    def _verify_jws(self, payload, key):
        """Verify the given JWS payload with the given key and return the payload"""
        jws = JWS.from_compact(payload)

        try:
            alg = jws.signature.combined.alg.name
        except KeyError:
            msg = "No alg value found in header"
            raise SuspiciousOperation(msg)

        if alg != self.OIDC_RP_SIGN_ALGO:
            msg = (
                "The provider algorithm {!r} does not match the client's "
                "OIDC_RP_SIGN_ALGO.".format(alg)
            )
            raise SuspiciousOperation(msg)

        if isinstance(key, str):
            # Use smart_bytes here since the key string comes from settings.
            jwk = JWK.load(smart_bytes(key))
        else:
            # The key is a json returned from the IDP JWKS endpoint.
            jwk = JWK.from_json(key)

        if not jws.verify(jwk):
            msg = "JWS token verification failed."
            raise SuspiciousOperation(msg)

        return jws.payload

    def retrieve_matching_jwk(self, token):
        """Get the signing key by exploring the JWKS endpoint of the OP."""
        response_jwks = requests.get(
            self.OIDC_OP_JWKS_ENDPOINT,
            verify=self.get_settings("OIDC_VERIFY_SSL", True),
            timeout=self.get_settings("OIDC_TIMEOUT", None),
            proxies=self.get_settings("OIDC_PROXY", None),
        )
        response_jwks.raise_for_status()
        jwks = response_jwks.json()

        # Compute the current header from the given token to find a match
        jws = JWS.from_compact(token)
        json_header = jws.signature.protected
        header = Header.json_loads(json_header)

        key = None
        for jwk in jwks["keys"]:
            if import_from_settings("OIDC_VERIFY_KID", True) and jwk[
                "kid"
            ] != smart_str(header.kid):
                continue
            if "alg" in jwk and jwk["alg"] != smart_str(header.alg):
                continue
            key = jwk
        if key is None:
            raise SuspiciousOperation("Could not find a valid JWKS.")
        return key

    def get_payload_data(self, token, key):
        """Helper method to get the payload of the JWT token."""
        if self.get_settings("OIDC_ALLOW_UNSECURED_JWT", False):
            header, payload_data, signature = token.split(b".")
            header = json.loads(smart_str(b64decode(header)))

            # If config allows unsecured JWTs check the header and return the decoded payload
            if "alg" in header and header["alg"] == "none":
                return b64decode(payload_data)

        # By default fallback to verify JWT signatures
        return self._verify_jws(token, key)

    def get_userinfo(self, access_token, id_token, payload):
        """Return user details dictionary. The id_token and payload are not used in
        the default implementation, but may be used when overriding this method"""

        user_response = requests.get(
            self.OIDC_OP_USER_ENDPOINT,
            headers={"Authorization": "Bearer {0}".format(access_token)},
            verify=self.get_settings("OIDC_VERIFY_SSL", True),
            timeout=self.get_settings("OIDC_TIMEOUT", None),
            proxies=self.get_settings("OIDC_PROXY", None),
        )
        user_response.raise_for_status()
        return user_response.json()

    def authenticate(self, request, **kwargs):
        """Authenticates a user based on the OIDC code flow."""

        self.request = request
        if not self.request:
            return None

        auth_header = request.headers.get("Authorization", None)
        if auth_header is None:
            return None
        parts = auth_header.split()
        if parts[0].lower() != "bearer":
            return None
        if len(parts) != 2:
            return None
        access_token = parts[1]

        # Check if the JWT signature is already in cache
        user_id = cache.get(access_token)
        if user_id:
            user = User.objects.get(pk=user_id)
            cache.set(access_token, user_id, 600)  # reset the 10 minute cache timer
            return user

        try:
            user = self.get_or_create_user(access_token)
            cache.set(
                access_token, user.pk, 600
            )  # cache the JWT signature for 10 minutes
            return user
        except SuspiciousOperation as exc:
            LOGGER.warning("failed to get or create user: %s", exc)
            return None

    def get_or_create_user(self, access_token):
        """Returns a User instance if 1 user is found. Creates a user if not found
        and configured to do so. Returns nothing if multiple users are matched."""

        user_info = self.get_userinfo(access_token)

        claims_verified = self.verify_claims(user_info)
        if not claims_verified:
            msg = "Claims verification failed"
            raise SuspiciousOperation(msg)

        # email based filtering
        users = self.filter_users_by_claims(user_info)

        if len(users) == 1:
            return self.update_user(users[0], user_info)
        elif len(users) > 1:
            # In the rare case that two user accounts have the same email address,
            # bail. Randomly selecting one seems really wrong.
            msg = "Multiple users returned"
            raise SuspiciousOperation(msg)
        elif self.get_settings("OIDC_CREATE_USER", True):
            user = self.create_user(user_info)
            return user
        else:
            LOGGER.debug(
                "Login failed: No user with %s found, and " "OIDC_CREATE_USER is False",
                self.describe_user_by_claims(user_info),
            )
            return None

    def get_user(self, user_id):
        """Return a user based on the id."""

        try:
            return self.UserModel.objects.get(pk=user_id)
        except self.UserModel.DoesNotExist:
            return None


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
