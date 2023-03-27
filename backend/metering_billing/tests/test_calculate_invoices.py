import itertools
import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from metering_billing.models import (
    BillingRecord,
    Event,
    Invoice,
    Metric,
    PlanComponent,
    PriceAdjustment,
    PriceTier,
    SubscriptionRecord,
)
from metering_billing.serializers.serializer_utils import DjangoJSONEncoder
from metering_billing.utils import now_utc
from metering_billing.utils.enums import PRICE_ADJUSTMENT_TYPE
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APIClient
