from django.db import models
import uuid
from model_utils import Choices
from djmoney.models.fields import MoneyField
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _
from moneyed import Money
from rest_framework_api_key.models import AbstractAPIKey
from dateutil.relativedelta import relativedelta
from dateutil.parser import isoparse
from django.contrib.postgres.fields import ArrayField
from django_tenants.models import TenantMixin, DomainMixin

PAYMENT_PLANS = Choices(
    ("self_hosted_free", _("Self-Hosted Free")),
    ("cloud", _("Cloud")),
    ("self_hosted_enterprise", _("Self-Hosted Enterprise")),
)


class Tenant(TenantMixin):
    company_name = models.CharField(max_length=100, default=" ")
    stripe_api_key = models.CharField(max_length=100, default="", blank=True)
    payment_plan = models.CharField(
        max_length=40, choices=PAYMENT_PLANS, default=PAYMENT_PLANS.self_hosted_free
    )
    id = models.CharField(
        max_length=40, unique=True, default=uuid.uuid4, primary_key=True
    )
    created_on = models.DateField(auto_now_add=True)
    auto_create_schema = True


class Domain(DomainMixin):
    pass


class User(AbstractUser):

    company_name = models.CharField(max_length=200, default=" ")


class APIToken(AbstractAPIKey):

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=200, default="latest_token")

    def __str__(self):
        return str(self.name) + " " + str(self.user)

    class Meta:
        verbose_name = "API Token"
        verbose_name_plural = "API Tokens"
