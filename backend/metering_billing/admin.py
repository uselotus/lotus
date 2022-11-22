from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from rest_framework_api_key.admin import APIKeyModelAdmin
from rest_framework_api_key.models import APIKey
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    Alert,
    APIToken,
    Backtest,
    BacktestSubstitution,
    CategoricalFilter,
    Customer,
    Event,
    Feature,
    Invoice,
    Metric,
    NumericFilter,
    Organization,
    OrganizationInviteToken,
    Plan,
    PlanComponent,
    PlanVersion,
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
admin.site.register(Plan, SimpleHistoryAdmin)
admin.site.register(Backtest)
admin.site.register(Metric, SimpleHistoryAdmin)
admin.site.register(PlanComponent)
admin.site.register(Feature, SimpleHistoryAdmin)
admin.site.register(PlanVersion, SimpleHistoryAdmin)
admin.site.register(Subscription, SimpleHistoryAdmin)
admin.site.register(Invoice, SimpleHistoryAdmin)
admin.site.register(OrganizationInviteToken)
admin.site.unregister(APIKey)
admin.site.register(BacktestSubstitution)


@admin.register(APIToken)
class UserAPIKeyModelAdmin(APIKeyModelAdmin):
    pass
