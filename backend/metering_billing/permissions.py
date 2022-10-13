from django.utils.translation import gettext_lazy as _
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from knox.auth import TokenAuthentication
from knox.models import AuthToken
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


# class KnoxTokenScheme(TokenAuthentication, OpenApiAuthenticationExtension):
#     # target_class = 'knox.auth.TokenAuthentication'
#     # name = 'knoxTokenAuth'
#     # match_subclasses = True
#     # priority = 1

#     def get_security_definition(self, auto_schema):
#         return {
#             'type': 'apiKey',
#             'in': 'header',
#             'name': 'Authorization',
#             'description': _(
#                 'Token-based authentication with required prefix "%s"'
#             ) % "Token"
#         }
