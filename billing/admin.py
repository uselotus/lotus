from django.contrib import admin
from .models import (
    BillingPlan,
    Customer,
    Event,
    Subscription,
    User,
    APIToken,
    BillableMetric,
    Invoice,
)
from rest_framework_api_key.admin import APIKeyModelAdmin


# Register your models here.
admin.site.register(Customer)
admin.site.register(Event)
admin.site.register(BillingPlan)
admin.site.register(Subscription)
admin.site.register(Invoice)
admin.site.register(BillableMetric)
admin.site.register(
    User,
)


@admin.register(APIToken)
class UserAPIKeyModelAdmin(APIKeyModelAdmin):
    pass
