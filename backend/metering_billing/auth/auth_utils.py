import jwt
from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponseBadRequest
from django.utils import timezone
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
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, get_authorization_header


class OIDCAuthentication(BaseAuthentication):
    """
    // This example was originally taken from the Zitadel docs at https://zitadel.com/docs/examples/secure-api/go
    //

    //
    // Backends need to protect their APIs by checking the headers of HTTP requests.
    // Some application architectures perform these checks at the boundaries (ie,
    // within nginx, Kong etc), but doing so provides less defense; it's much better to check
    // at the application level - indeed, at every level - which also happens to give you the
    // option of enabling *public* (non-protected) APIs from different microservices, which
    // turns out to be pretty useful.
    //
    // **Great care must be taken with backend APIs to ensure that the endpoints are protected**.
    // Typically, we would avoid problems by using prebuilt templates and patterns with default good
    // behaviours to build new microservices, and any deviation from these patterns would require strict
    // code review.
    //
    // All HTTP requests from clients to protected URLs need to contain an Authroization header which
    // contains the access token. The access token must be validated by your code before you provide access to an API.
    //
    // Access tokens can be in one of two different formats: "opaque" or JWT. The format of the access token
    // is defined by the server, but note that this version of the backend assumes JWTs only. (The original
    // opaque token code has been commented out to provide clarity about how it works, while retaining a
    // record of how to do it).
    //
    // # OPAQUE ACCESS TOKENS
    //
    // Opaque tokens are identifiers that can't be decoded by the
    // client. To validate an opaque access token requires a round-trip call to
    // Zitadel, which adds latency, and is potentially less reliable. On the other
    // hand, opaque tokens reveal nothing at all to the client, and are relatively
    // compact.
    //
    // # JWT ACCESS TOKENS
    //
    // JWT tokens, on the other hand, are **self-contained** - they are signed by
    // the auth server - and therefore can be validated without an additional API round
    // trip. JWT tokens contain signed information about the user and (optionally) the
    // roles provided to the user, which we can use for authorization and auditing.
    //
    // The fact that JWTs are signed by the auth server means that they can be used
    // securely, with much less latency, despite being provided by a client over
    // which we have no control.
    //
    // For these reasons, we prefer JWT tokens, even though they are less compact.
    //
    // BACKEND APIS
    //
    // This server provides a single protected API, /backend/jwt, which uses offline validation to validate
    // the token.
    //
    // It also includes a commented-out route called /backend/protected, which uses the Zitadel API call
    // to validate the token.
    //
    // Both APIs will work with JWT tokens, but only the first will work for opaque tokens.
    // You can see the token settings in Zitadel -> Projects -> [My Project] -> [Frontend Client] -> Token Settings
    //
    // NOTES:
    // * Access Tokens can have a long lifetime; offline checking does not provide a means to cancel a
    //   token. This means that some other method may be needed to cancel a token. This requires more consideration.
    // * JWTs can become quite large if you try to fit too many claims (user parameters) and roles into them.
    //   Care will need to be taken when extending the contents of a JWT.
    //
    // Auth0 has some more information on the different token formats; see
    // https://auth0.com/docs/secure/tokens/access-tokens#management-api-access-tokens
    """

    def authenticate(self, request):
        auth = get_authorization_header(request).split()
        prefix = "BEARER"

        if not auth:
            return None
        if auth[0].lower() != prefix.lower():
            # Authorization header is possibly for another backend
            return None
        if len(auth) == 1:
            msg = _("Invalid token header. No credentials provided.")
            raise exceptions.AuthenticationFailed(msg)
        elif len(auth) > 2:
            msg = _("Invalid token header. " "Token string should not contain spaces.")
            raise exceptions.AuthenticationFailed(msg)

        user, auth_token = self.authenticate_credentials(auth[1])
        return (user, auth_token)

    def authenticate_credentials(self, token):
        """
        Due to the random nature of hashing a value, this must inspect
        each auth_token individually to find the correct one.
        Tokens that have expired will be deleted and skipped
        """
        msg = _("Invalid token.")
        token = token.decode("utf-8")
        secret = settings.SECRET_KEY
        jwt.decode(token, "secret", algorithms=["HS256"])
        try:
            return self.validate_user(auth_token)
        except:
            raise exceptions.AuthenticationFailed(msg)

    def renew_token(self, auth_token):
        current_expiry = auth_token.expiry
        new_expiry = timezone.now() + knox_settings.TOKEN_TTL
        auth_token.expiry = new_expiry
        # Throttle refreshing of token to avoid db writes
        delta = (new_expiry - current_expiry).total_seconds()
        if delta > knox_settings.MIN_REFRESH_INTERVAL:
            auth_token.save(update_fields=("expiry",))

    def validate_user(self, auth_token):
        if not auth_token.user.is_active:
            raise exceptions.AuthenticationFailed(_("User inactive or deleted."))
        return (auth_token.user, auth_token)


# AUTH METHODS
def get_organization_from_key(key):
    try:
        api_key = APIToken.objects.get_from_key(key)
    except:
        raise NoMatchingAPIKey("API Key starting with {} not known".format(key[:5]))
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
        except:
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
