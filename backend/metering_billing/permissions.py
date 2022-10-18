from django.utils.translation import gettext_lazy as _
from metering_billing.models import APIToken
from rest_framework_api_key.permissions import BaseHasAPIKey


class HasUserAPIKey(BaseHasAPIKey):
    model = APIToken

    def get_key(self, request):
        try:
            return request.META.get("HTTP_X_API_KEY")
        except KeyError:
            meta_dict = {k.lower(): v for k, v in request.META}
            if "http_x_api_key".lower() in meta_dict:
                return meta_dict["http_x_api_key"]
            else:
                raise KeyError("No API key found in request")

