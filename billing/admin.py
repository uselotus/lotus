from django.contrib import admin
from .models import BillingPlan, Customer, Event, Subscription, User, APIToken

# Register your models here.
admin.site.register(Customer)
admin.site.register(Event)
admin.site.register(BillingPlan)
admin.site.register(Subscription)
admin.site.register(
    User,
)
admin.site.register(APIToken)
