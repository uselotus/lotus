from rest_framework_api_key.permissions import BaseHasAPIKey

from metering_billing.models import APIToken


class HasUserAPIKey(BaseHasAPIKey):
    model = APIToken
