import logging

from django.utils.translation import gettext_lazy as _
from metering_billing.exceptions import NoAPIKeyProvided
from metering_billing.models import APIToken
from rest_framework import permissions
from rest_framework_api_key.permissions import BaseHasAPIKey

logger = logging.getLogger("django.server")


class HasUserAPIKey(BaseHasAPIKey):
    model = APIToken

    def get_key(self, request):
        try:
            return request.META.get("HTTP_X_API_KEY")
        except KeyError:
            meta_dict = {k.lower(): v for k, v in request.META.items()}
            if "http_x_api_key".lower() in meta_dict:
                return meta_dict["http_x_api_key"]
            else:
                raise NoAPIKeyProvided("No API key found in request")


class ValidOrganization(permissions.BasePermission):
    """
    Make sure there's a valid organization attached
    """

    def has_permission(self, request, view):
        org = request.organization
        logger.debug("ValidOrganization: %s" % (org))
        if org is None and request.user.is_authenticated:
            org = request.user.organization
            logger.debug(f"ValidOrganization didn't have org, got from user: {org}")
            request.organization = org
        return org is not None

    def has_object_permission(self, request, view, obj):
        # Instance must have an attribute named `owner`.
        org = request.organization
        if org is None and request.user.is_authenticated:
            org = request.user.organization
        return obj.organization == org
