from django.contrib import admin
from .models import BillingPlan, Customer, Event

# Register your models here.
admin.site.register(Customer)
admin.site.register(Event)
admin.site.register(BillingPlan)
