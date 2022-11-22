from django.apps import AppConfig


class MeteringBillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "metering_billing"

    def ready(self):
        from actstream import registry

        registry.register(self.get_model("User"))
        registry.register(self.get_model("PlanVersion"))
        registry.register(self.get_model("Customer"))
        registry.register(self.get_model("Plan"))
        registry.register(self.get_model("Subscription"))
        registry.register(self.get_model("Metric"))
