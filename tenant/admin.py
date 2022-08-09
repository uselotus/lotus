from django.contrib import admin
from django_tenants.admin import TenantAdminMixin

from tenant.models import Tenant, User, Domain, APIToken

from  django.contrib.auth.models import Group


from rest_framework_api_key.admin import APIKeyModelAdmin
from rest_framework_api_key.models import APIKey



@admin.register(APIToken)
class UserAPIKeyModelAdmin(APIKeyModelAdmin):
    pass



admin.site.unregister(APIKey)
admin.site.unregister(Group)


admin.register(Domain)


@admin.register(Tenant)
class TenantAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("company_name", "id")


admin.site.register(
    User,
)
