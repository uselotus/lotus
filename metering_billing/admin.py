from django.contrib import admin

from django.contrib import admin
from .models import (
    BillingPlan,
    Customer,
    Event,
    Organization,
    Subscription,
    BillableMetric,
    Invoice,
    PlanComponent,
    User,
)

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
