import logging
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.core.cache import cache
from django.core.exceptions import SuspiciousOperation
from django.db.models import Q
from metering_billing.models import Team, User
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

LOGGER = logging.getLogger(__name__)


class OIDCAuthenticationBackend(OIDCAuthenticationBackend):
    """Override Django's authentication."""

    def get_username(self, claims):
        """Generate username based on claims."""
        return claims.get("email")

    def get_or_create_user(self, access_token, id_token, payload):
        """Returns a User instance if 1 user is found. Creates a user if not found
        and configured to do so. Returns nothing if multiple users are matched."""
        # Check if the JWT signature is already in cache
        user_id = cache.get(access_token)
        if user_id:
            user = User.objects.get(pk=user_id)
            cache.set(access_token, user_id, 600)  # reset the 10 minute cache timer
            return user
        user_info = self.get_userinfo(access_token, id_token, payload)

        claims_verified = self.verify_claims(user_info)
        if not claims_verified:
            msg = "Claims verification failed"
            raise SuspiciousOperation(msg)

        # email based filtering
        users = self.filter_users_by_claims(user_info)

        if len(users) == 1:
            cache.set(
                access_token, users[0].pk, 600
            )  # cache the JWT signature for 10 minutes
            return self.update_user(users[0], user_info)
        elif len(users) > 1:
            # In the rare case that two user accounts have the same email address,
            # bail. Randomly selecting one seems really wrong.
            msg = "Multiple users returned"
            raise SuspiciousOperation(msg)
        elif self.get_settings("OIDC_CREATE_USER", True):
            roles = user_info.get("urn:zitadel:iam:org:project:roles")
            if roles:
                team = None
                # Iterate through roles and check if a team with corresponding id exists
                for role in roles:
                    try:
                        team_id = uuid.UUID(role)
                    except ValueError:
                        continue
                    if Team.objects.filter(team_id=team_id).exists():
                        team = Team.objects.get(team_id=team_id)
                        break
                if team is None:
                    msg = "No team found for the roles in access token"
                    raise SuspiciousOperation(msg)
            user = self.create_user(user_info)
            user.team = team
            user.organization = team.organizations.first()
            user.save()
            cache.set(
                access_token, user.pk, 600
            )  # cache the JWT signature for 10 minutes
            # Check if roles key exists in access token
            return user
        else:
            LOGGER.debug(
                "Login failed: No user with %s found, and " "OIDC_CREATE_USER is False",
                self.describe_user_by_claims(user_info),
            )
            return None


class EmailOrUsernameModelBackend(ModelBackend):
    """
    Authentication backend which allows users to authenticate using either their
    username or email address

    Source: https://stackoverflow.com/a/35836674/59984
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        # n.b. Django <2.1 does not pass the `request`

        user_model = get_user_model()

        if username is None:
            username = kwargs.get(user_model.USERNAME_FIELD)

        # The `username` field is allows to contain `@` characters so
        # technically a given email address could be present in either field,
        # possibly even for different users, so we'll query for all matching
        # records and test each one.
        users = user_model._default_manager.filter(
            Q(**{user_model.USERNAME_FIELD: username}) | Q(email__iexact=username)
        )

        # Test whether any matched user has the provided password:
        for user in users:
            if user.check_password(password):
                return user
        if not users:
            # Run the default password hasher once to reduce the timing
            # difference between an existing and a non-existing user (see
            # https://code.djangoproject.com/ticket/20760)
            user_model().set_password(password)
