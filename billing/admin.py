from django.contrib import admin
from .models import (
    BillingPlan,
    Customer,
    Event,
    Subscription,
    BillableMetric,
    Invoice,
    PlanComponent,
)

# Register your models here.
admin.site.register(Customer)
admin.site.register(Event)
admin.site.register(BillingPlan)
admin.site.register(Subscription)
admin.site.register(Invoice)
admin.site.register(BillableMetric)
admin.site.register(PlanComponent)
