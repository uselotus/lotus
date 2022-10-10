from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from rest_framework_api_key.admin import APIKeyModelAdmin
from rest_framework_api_key.models import APIKey
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    Alert,
    APIToken,
    BillableMetric,
    BillingPlan,
    CategoricalFilter,
    Customer,
    Event,
    Feature,
    Invoice,
    NumericFilter,
    Organization,
    PlanComponent,
    Subscription,
    User,
)


class CustomAdmin(UserAdmin, SimpleHistoryAdmin):
    pass


# Register your models here.
admin.site.register(Organization, SimpleHistoryAdmin)
admin.site.register(Alert, SimpleHistoryAdmin)
admin.site.register(User, CustomAdmin)
admin.site.register(Customer, SimpleHistoryAdmin)
admin.site.register(Event)
admin.site.register(NumericFilter)
admin.site.register(CategoricalFilter)
admin.site.register(BillableMetric, SimpleHistoryAdmin)
admin.site.register(PlanComponent)
admin.site.register(Feature)
admin.site.register(BillingPlan, SimpleHistoryAdmin)
admin.site.register(Subscription, SimpleHistoryAdmin)
admin.site.register(Invoice, SimpleHistoryAdmin)
admin.site.unregister(APIKey)


@admin.register(APIToken)
class UserAPIKeyModelAdmin(APIKeyModelAdmin):
    pass
