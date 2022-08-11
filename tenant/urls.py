import sys
from types import ModuleType

from django.contrib import admin
from django.urls import path


def generate_tenant_url_module(tenant) -> str:
    module_name = "tenant_urls_{0}".format(tenant.schema_name)
    mod = ModuleType(module_name)
    mod.urlpatterns = [path("t/{0}/admin".format(str(tenant.id)), admin.site.urls)]
    print(mod.urlpatterns)
    sys.modules[module_name] = mod

    return module_name
