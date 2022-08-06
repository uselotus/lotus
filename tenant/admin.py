from django.contrib import admin
from django_tenants.admin import TenantAdminMixin

from tenant.models import Tenant, User, Domain, APIToken


from rest_framework_api_key.admin import APIKeyModelAdmin


@admin.register(APIToken)
class UserAPIKeyModelAdmin(APIKeyModelAdmin):
    pass


admin.register(Domain)


@admin.register(Tenant)
class TenantAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("company_name", "id")


admin.site.register(
    User,
)
