import datetime
import itertools
import os
import random
import time
import uuid
from datetime import timezone

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from faker import Faker
from metering_billing.models import (
    BillableMetric,
    BillingPlan,
    Customer,
    Event,
    Organization,
    PlanComponent,
    Subscription,
    User,
)
from model_bakery import baker


class Command(BaseCommand):
    "Django command to pause execution until the database is available"

    def handle(self, *args, **options):
        try:
            Organization.objects.get(company_name="test").delete()
        except:
            print("failed to delete test organization")
