from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from rest_framework_api_key.admin import APIKeyModelAdmin
from rest_framework_api_key.models import APIKey
from simple_history.admin import SimpleHistoryAdmin

from .models import (  # Subscription,
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
    Plan,
    PlanComponent,
    PlanVersion,
    Subscription,
    SubscriptionRecord,
    TeamInviteToken,
    User,
    WebhookEndpoint,
)


class CustomAdmin(UserAdmin, SimpleHistoryAdmin):
    pass


# Register your models here.
admin.site.register(Organization, SimpleHistoryAdmin)
admin.site.register(WebhookEndpoint)
admin.site.register(User, CustomAdmin)
admin.site.register(Customer, SimpleHistoryAdmin)
admin.site.register(Event)
admin.site.register(Subscription)
admin.site.register(SubscriptionRecord)
admin.site.register(Plan, SimpleHistoryAdmin)
admin.site.register(Backtest)
admin.site.register(Metric, SimpleHistoryAdmin)
admin.site.register(PlanComponent)
admin.site.register(Feature, SimpleHistoryAdmin)
admin.site.register(PlanVersion, SimpleHistoryAdmin)
admin.site.register(Invoice, SimpleHistoryAdmin)
admin.site.register(TeamInviteToken)
admin.site.unregister(APIKey)
admin.site.register(BacktestSubstitution)


@admin.register(APIToken)
class UserAPIKeyModelAdmin(APIKeyModelAdmin):
    pass
