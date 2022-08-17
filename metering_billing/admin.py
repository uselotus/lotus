from django.contrib import admin
from rest_framework_api_key.admin import APIKeyModelAdmin
from rest_framework_api_key.models import APIKey

from .models import (APIToken, BillableMetric, BillingPlan, Customer, Event,
                     Invoice, Organization, PlanComponent, Subscription, User)

# Register your models here.
admin.site.register(Customer)
admin.site.register(Event)
admin.site.register(BillingPlan)
admin.site.register(Subscription)
admin.site.register(Invoice)
admin.site.register(BillableMetric)
admin.site.register(PlanComponent)
admin.site.register(User)
admin.site.register(Organization)

admin.site.unregister(APIKey)


@admin.register(APIToken)
class UserAPIKeyModelAdmin(APIKeyModelAdmin):
    pass
