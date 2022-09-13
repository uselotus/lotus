from django.core.exceptions import ObjectDoesNotExist
from metering_billing.models import Organization
from rest_framework.authentication import BaseAuthentication

from ..metering_billing.permissions import HasUserAPIKey


### NOT YET READY TO BE ADDED INTO AUTHENTICATION
class ApiKeyAuthentication(BaseAuthentication):
    """
    An authentication plugin that authenticates requests through a API key provided in a request header.

    """

    def authenticate(self, request):
        validator = HasUserAPIKey()
        key = validator.get_key(request)

        if not key:
            return None

        try:
            organization_api_key = validator.model.objects.get_from_key(key)
        except ObjectDoesNotExist:
            return None

        request_ip = request.META.get("REMOTE_ADDR")

        if request_ip != organization_api_key.ip:
            return None

        try:
            organization = Organization.objects.get(pk=organization_api_key.user_id)
        except Organization.DoesNotExist:
            return None

        return organization, None

    def authenticate_header(self, request):
        return 'Api-Key realm="api"'
