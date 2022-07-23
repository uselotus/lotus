from django.contrib import admin
from .models import Customer, BillingPlan

# Register your models here.

admin.site.register(Customer)
admin.site.register(BillingPlan)
