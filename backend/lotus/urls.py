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
from metering_billing.views import auth_views, organization_views, track
from metering_billing.views.model_views import (
    BacktestViewSet,
    BillableMetricViewSet,
    CustomerViewSet,
    EventViewSet,
    FeatureViewSet,
    InvoiceViewSet,
    PlanVersionViewSet,
    PlanViewSet,
    ProductViewSet,
    SubscriptionViewSet,
    UserViewSet,
    WebhookViewSet,
)
from metering_billing.views.payment_provider_views import PaymentProviderView
from metering_billing.views.views import (  # MergeCustomersView,
    APIKeyCreate,
    CustomerDetailView,
    CustomersSummaryView,
    CustomersWithRevenueView,
    DraftInvoiceView,
    ExperimentalToActiveView,
    GetCustomerAccessView,
    PeriodMetricRevenueView,
    PeriodMetricUsageView,
    PeriodSubscriptionsView,
    PlansByNumCustomersView,
    SyncCustomersView,
)
from rest_framework import routers

DEBUG = settings.DEBUG
ON_HEROKU = settings.ON_HEROKU
PROFILER_ENABLED = settings.PROFILER_ENABLED

router = routers.DefaultRouter()
router.register(r"users", UserViewSet, basename="user")
router.register(r"customers", CustomerViewSet, basename="customer")
router.register(r"metrics", BillableMetricViewSet, basename="metric")
router.register(r"subscriptions", SubscriptionViewSet, basename="subscription")
router.register(r"invoices", InvoiceViewSet, basename="invoice")
router.register(r"features", FeatureViewSet, basename="feature")
router.register(r"webhooks", WebhookViewSet, basename="webhook")
router.register(r"backtests", BacktestViewSet, basename="backtest")
router.register(r"products", ProductViewSet, basename="product")
router.register(r"plans", PlanViewSet, basename="plan")
router.register(r"plan_versions", PlanVersionViewSet, basename="plan_version")
router.register(r"events", EventViewSet, basename="event")


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
        "api/plans_by_customer/",
        PlansByNumCustomersView.as_view(),
        name="plans_by_customer",
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
        name="pexwriod_subscriptions",
    ),
    path("api/new_api_key/", APIKeyCreate.as_view(), name="new_api_key"),
    path("api/draft_invoice/", DraftInvoiceView.as_view(), name="draft_invoice"),
    path(
        "api/customer_access/",
        GetCustomerAccessView.as_view(),
        name="customer_access",
    ),
    # path(
    #     "api/merge_customers/",
    #     MergeCustomersView.as_view(),
    #     name="merge_customers",
    # ),
    path(
        "api/sync_customers/",
        SyncCustomersView.as_view(),
        name="sync_customers",
    ),
    path(
        "api/payment_providers/",
        PaymentProviderView.as_view(),
        name="payment_providers",
    ),
    path(
        "api/experimental_to_active/",
        ExperimentalToActiveView.as_view(),
        name="expertimental-to-active",
    ),
    path("api/login/", auth_views.LoginView.as_view(), name="api-login"),
    path("api/logout/", auth_views.LogoutView.as_view(), name="api-logout"),
    path("api/session/", auth_views.SessionView.as_view(), name="api-session"),
    path("api/register/", auth_views.RegisterView.as_view(), name="register"),
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
        name="invite-to-organization",
    ),
    path(
        "api/organization",
        organization_views.OrganizationView.as_view(),
        name="organization",
    ),
]

if PROFILER_ENABLED:
    urlpatterns += [path("silk/", include("silk.urls", namespace="silk"))]

if DEBUG:
    urlpatterns += [re_path(".*", TemplateView.as_view(template_name="index.html"))]
