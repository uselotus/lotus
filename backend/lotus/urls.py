"""lotus URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls import include
from django.contrib import admin
from django.urls import path, re_path
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from metering_billing.payment_providers import StripeConnector
from metering_billing.views import auth_views, track, organization_views
from metering_billing.views.model_views import (
    BacktestViewSet,
    BillableMetricViewSet,
    BillingPlanViewSet,
    CustomerViewSet,
    FeatureViewSet,
    InvoiceViewSet,
    SubscriptionViewSet,
    UserViewSet,
    WebhookViewSet,
)
from metering_billing.views.views import (
    APIKeyCreate,
    CancelSubscriptionView,
    CustomerDetailView,
    CustomersSummaryView,
    CustomersWithRevenueView,
    DraftInvoiceView,
    EventPreviewView,
    ExperimentalToActiveView,
    GetCustomerAccessView,
    MergeCustomersView,
    PeriodMetricRevenueView,
    PeriodMetricUsageView,
    PeriodSubscriptionsView,
    SyncCustomersView,
    UpdateBillingPlanView,
    UpdateSubscriptionBillingPlanView,
)
from rest_framework import routers

DEBUG = settings.DEBUG
ON_HEROKU = settings.ON_HEROKU
PROFILER_ENABLED = settings.PROFILER_ENABLED

router = routers.DefaultRouter()
router.register(r"users", UserViewSet, basename="user")
router.register(r"customers", CustomerViewSet, basename="customer")
router.register(r"metrics", BillableMetricViewSet, basename="metric")
router.register(r"plans", BillingPlanViewSet, basename="plan")
router.register(r"subscriptions", SubscriptionViewSet, basename="subscription")
router.register(r"invoices", InvoiceViewSet, basename="invoice")
router.register(r"features", FeatureViewSet, basename="feature")
router.register(r"webhooks", WebhookViewSet, basename="webhook")
router.register(r"backtests", BacktestViewSet, basename="backtest")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api/track/", csrf_exempt(track.track_event), name="track_event"),
    path(
        "api/customer_summary/",
        CustomersSummaryView.as_view(),
        name="customer_summary",
    ),
    path(
        "api/customer_detail/",
        CustomerDetailView.as_view(),
        name="customer_detail",
    ),
    path(
        "api/customer_totals/",
        CustomersWithRevenueView.as_view(),
        name="customer_totals",
    ),
    path(
        "api/period_metric_usage/",
        PeriodMetricUsageView.as_view(),
        name="period_metric_usage",
    ),
    path(
        "api/period_metric_revenue/",
        PeriodMetricRevenueView.as_view(),
        name="period_metric_revenue",
    ),
    path(
        "api/period_subscriptions/",
        PeriodSubscriptionsView.as_view(),
        name="period_subscriptions",
    ),
    path("api/new_api_key/", APIKeyCreate.as_view(), name="new_api_key"),
    path("api/event_preview/", EventPreviewView.as_view(), name="event_preview"),
    path("api/draft_invoice/", DraftInvoiceView.as_view(), name="draft_invoice"),
    path(
        "api/cancel_subscription/",
        CancelSubscriptionView.as_view(),
        name="cancel_subscription",
    ),
    path(
        "api/update_billing_plan/",
        UpdateBillingPlanView.as_view(),
        name="update_billing_plan",
    ),
    path(
        "api/update_subscription/",
        UpdateSubscriptionBillingPlanView.as_view(),
        name="update_subscription",
    ),
    path(
        "api/customer_access/",
        GetCustomerAccessView.as_view(),
        name="customer_access",
    ),
    path(
        "api/merge_customers/",
        MergeCustomersView.as_view(),
        name="merge_customers",
    ),
    path(
        "api/sync_customers/",
        SyncCustomersView.as_view(),
        name="sync_customers",
    ),
    path("api/stripe/", StripeConnector.as_view(), name="stripe_initialize"),
    path(
        "api/experimental_to_active/",
        ExperimentalToActiveView.as_view(),
        name="expertimental-to-active",
    ),
    path("api/login/", auth_views.LoginView.as_view(), name="api-login"),
    path("api/logout/", auth_views.LogoutView.as_view(), name="api-logout"),
    path("api/session/", auth_views.SessionView.as_view(), name="api-session"),
    # path("api/whoami/", auth_views.whoami_view, name="api-whoami"),
    path("api/register/", auth_views.RegisterView.as_view(), name="register"),
    # path("csrf/", csrf_exempt(auth_views.csrf), name="csrf"),
    path(
        "api/user/password/reset/init/",
        auth_views.InitResetPasswordView.as_view(),
        name="reset-password",
    ),
    path(
        "api/user/password/reset/",
        auth_views.ResetPasswordView.as_view(),
        name="set-new-password",
    ),
    path(
        "api/organization/invite",
        organization_views.InviteView.as_view(),
        name="invite-to-organization"
    ),
    path(
        "api/organization",
        organization_views.OrganizationView.as_view(),
        name="organization"
    )
]

if PROFILER_ENABLED:
    urlpatterns += [path("silk/", include("silk.urls", namespace="silk"))]

if DEBUG:
    urlpatterns += [re_path(".*", TemplateView.as_view(template_name="index.html"))]
