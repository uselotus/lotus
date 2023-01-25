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
import api.views as api_views
from django.conf import settings
from django.conf.urls import include
from django.contrib import admin
from django.urls import path, re_path
from django.views.generic import TemplateView
from metering_billing.views import auth_views, organization_views, webhook_views
from metering_billing.views.model_views import (
    ActionViewSet,
    AddOnViewSet,
    APITokenViewSet,
    BacktestViewSet,
    CustomerBalanceAdjustmentViewSet,
    CustomerViewSet,
    EventViewSet,
    ExternalPlanLinkViewSet,
    FeatureViewSet,
    InvoiceViewSet,
    MetricViewSet,
    OrganizationSettingViewSet,
    OrganizationViewSet,
    PlanVersionViewSet,
    PlanViewSet,
    PricingUnitViewSet,
    ProductViewSet,
    SubscriptionViewSet,
    UsageAlertViewSet,
    UserViewSet,
    WebhookViewSet,
)
from metering_billing.views.payment_provider_views import PaymentProviderView
from metering_billing.views.views import (  # MergeCustomersView,; ExperimentalToActiveView,
    ChangeUserOrganizationView,
    CostAnalysisView,
    CustomersSummaryView,
    CustomersWithRevenueView,
    DraftInvoiceView,
    GetInvoicePdfURL,
    ImportCustomersView,
    ImportPaymentObjectsView,
    PeriodMetricRevenueView,
    PeriodMetricUsageView,
    PeriodSubscriptionsView,
    PlansByNumCustomersView,
    TransferSubscriptionsView,
)
from rest_framework import routers

DEBUG = settings.DEBUG
ON_HEROKU = settings.ON_HEROKU
PROFILER_ENABLED = settings.PROFILER_ENABLED

# app router
router = routers.DefaultRouter()
router.register(r"users", UserViewSet, basename="user")
router.register(r"customers", CustomerViewSet, basename="customer")
router.register(r"metrics", MetricViewSet, basename="metric")
router.register(r"subscriptions", SubscriptionViewSet, basename="subscription")
router.register(r"invoices", InvoiceViewSet, basename="invoice")
router.register(r"features", FeatureViewSet, basename="feature")
router.register(r"webhooks", WebhookViewSet, basename="webhook")
router.register(r"backtests", BacktestViewSet, basename="backtest")
router.register(r"products", ProductViewSet, basename="product")
router.register(r"plans", PlanViewSet, basename="plan")
router.register(r"plan_versions", PlanVersionViewSet, basename="plan_version")
router.register(r"events", EventViewSet, basename="event")
router.register(r"actions", ActionViewSet, basename="action")
router.register(
    r"external_plan_links", ExternalPlanLinkViewSet, basename="external_plan_link"
)
router.register(
    r"organization_settings",
    OrganizationSettingViewSet,
    basename="organization_setting",
)
router.register(r"organizations", OrganizationViewSet, basename="organization")
router.register(r"pricing_units", PricingUnitViewSet, basename="pricing_unit")
router.register(
    r"credits",
    CustomerBalanceAdjustmentViewSet,
    basename="credit",
)
router.register(r"api_tokens", APITokenViewSet, basename="api_token")
router.register(r"addons", AddOnViewSet, basename="addon")
router.register(r"usage_alerts", UsageAlertViewSet, basename="usage_alert")


# api router
api_router = routers.DefaultRouter()
api_router.register(r"customers", api_views.CustomerViewSet, basename="customer")
api_router.register(r"plans", api_views.PlanViewSet, basename="plan")
api_router.register(
    r"subscriptions", api_views.SubscriptionViewSet, basename="subscription"
)
api_router.register(r"invoices", api_views.InvoiceViewSet, basename="invoice")
api_router.register(
    r"credits",
    api_views.CustomerBalanceAdjustmentViewSet,
    basename="credit",
)

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),
    # API Views
    path("api/", include((api_router.urls, "api"), namespace="api")),
    path("api/ping/", api_views.Ping.as_view(), name="ping"),
    path("api/track/", api_views.track_event, name="track_event"),
    path("api/invoice_url/", api_views.GetInvoicePdfURL.as_view(), name="invoice_url"),
    path(
        "api/metric_access/",
        api_views.MetricAccessView.as_view(),
        name="metric_access",
    ),
    path(
        "api/feature_access/",
        api_views.FeatureAccessView.as_view(),
        name="feature_access",
    ),
    path(
        "api/customer_metric_access/",
        api_views.GetCustomerEventAccessView.as_view(),
        name="customer_metric_access",
    ),
    path(
        "api/customer_feature_access/",
        api_views.GetCustomerFeatureAccessView.as_view(),
        name="customer_feature_access",
    ),
    path(
        "api/verify_idems_received/",
        api_views.ConfirmIdemsReceivedView.as_view(),
        name="verify_idems_received",
    ),
    # App views
    path("app/", include(router.urls)),
    path("app/invoice_url/", GetInvoicePdfURL.as_view(), name="invoice_url"),
    path(
        "app/customer_summary/",
        CustomersSummaryView.as_view(),
        name="customer_summary",
    ),
    path(
        "app/cost_analysis/",
        CostAnalysisView.as_view(),
        name="cost_analysis",
    ),
    path(
        "app/switch_organization/",
        ChangeUserOrganizationView.as_view(),
        name="switch_organization",
    ),
    path(
        "app/customer_totals/",
        CustomersWithRevenueView.as_view(),
        name="customer_totals",
    ),
    path(
        "app/plans_by_customer/",
        PlansByNumCustomersView.as_view(),
        name="plans_by_customer",
    ),
    path(
        "app/period_metric_usage/",
        PeriodMetricUsageView.as_view(),
        name="period_metric_usage",
    ),
    path(
        "app/period_metric_revenue/",
        PeriodMetricRevenueView.as_view(),
        name="period_metric_revenue",
    ),
    path(
        "app/period_subscriptions/",
        PeriodSubscriptionsView.as_view(),
        name="period_subscriptions",
    ),
    path("app/draft_invoice/", DraftInvoiceView.as_view(), name="draft_invoice"),
    path(
        "app/import_customers/",
        ImportCustomersView.as_view(),
        name="import_customers",
    ),
    path(
        "app/import_payment_objects/",
        ImportPaymentObjectsView.as_view(),
        name="import_payment_objects",
    ),
    path(
        "app/transfer_subscriptions/",
        TransferSubscriptionsView.as_view(),
        name="transfer_subscriptions",
    ),
    path(
        "app/payment_providers/",
        PaymentProviderView.as_view(),
        name="payment_providers",
    ),
    # path(
    #     "app/experimental_to_active/",
    #     ExperimentalToActiveView.as_view(),
    #     name="expertimental-to-active",
    # ),
    path("app/login/", auth_views.LoginView.as_view(), name="api-login"),
    path("app/demo_login/", auth_views.DemoLoginView.as_view(), name="api-demo-login"),
    path("app/logout/", auth_views.LogoutView.as_view(), name="api-logout"),
    path("app/session/", auth_views.SessionView.as_view(), name="api-session"),
    path("app/register/", auth_views.RegisterView.as_view(), name="register"),
    path(
        "app/demo_register/",
        auth_views.DemoRegisterView.as_view(),
        name="demo_register",
    ),
    path(
        "app/user/password/reset/init/",
        auth_views.InitResetPasswordView.as_view(),
        name="reset-password",
    ),
    path(
        "app/user/password/reset/",
        auth_views.ResetPasswordView.as_view(),
        name="set-new-password",
    ),
    path(
        "app/organization/invite/",
        organization_views.InviteView.as_view(),
        name="invite-to-organization",
    ),
    # Stripe
    path(
        "stripe/webhook/", webhook_views.stripe_webhook_endpoint, name="stripe-webhook"
    ),
]

if PROFILER_ENABLED:
    urlpatterns += [path("silk/", include("silk.urls", namespace="silk"))]

if DEBUG:
    urlpatterns += [re_path(".*", TemplateView.as_view(template_name="index.html"))]
