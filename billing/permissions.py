from rest_framework_api_key.permissions import BaseHasAPIKey
from tenant.models import APIToken


class HasUserAPIKey(BaseHasAPIKey):
    model = APIToken
