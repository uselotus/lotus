from rest_framework_api_key.permissions import BaseHasAPIKey
from .models import APIToken


class HasUserAPIKey(BaseHasAPIKey):
    model = APIToken
