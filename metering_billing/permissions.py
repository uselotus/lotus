from rest_framework_api_key.permissions import BaseHasAPIKey

from metering_billing.models import APIToken


class HasUserAPIKey(BaseHasAPIKey):
    model = APIToken

    def get_key(self, request):
        return request.META.get("HTTP_X_API_KEY")
