from django.conf import settings
from django.db import connection
from django_tenants.middleware.main import TenantMainMiddleware

from .models import Tenant
from .urls import generate_tenant_url_module


class TenantMiddleware(TenantMainMiddleware):
    @staticmethod
    def tenant_id_from_request(request):
        if request.path.startswith("/t/"):
            tenant_id = request.path.lstrip("/t/").split("/")[0]
            return tenant_id
        return ""

    def process_request(self, request):
        connection.set_schema_to_public()
        tenant_id = self.tenant_id_from_request(request)
        if not tenant_id:
            return

        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            raise self.TENANT_NOT_FOUND_EXCEPTION(
                'No tenant for tenant ID"%s"' % tenant_id
            )
        request.tenant = tenant
        connection.set_tenant(request.tenant)
        request.urlconf = generate_tenant_url_module(tenant)
