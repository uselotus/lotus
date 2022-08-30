import json
import math
import os
from datetime import datetime

import dateutil.parser as parser
import stripe
from django.db import connection
from django.forms.models import model_to_dict
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
from django_q.tasks import async_task
from lotus.settings import STRIPE_SECRET_KEY
from metering_billing.models import (
    APIToken,
    BillingPlan,
    Customer,
    Event,
    Organization,
    PlanComponent,
    Subscription,
)
from metering_billing.permissions import HasUserAPIKey
from metering_billing.serializers import (
    BillingPlanSerializer,
    CustomerSerializer,
    EventSerializer,
    PlanComponentSerializer,
    SubscriptionSerializer,
)
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
