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
from django.conf.urls import include
from django.contrib import admin
from django.shortcuts import render
from django.urls import path
from django.views.generic import TemplateView
from rest_framework import routers

import metering_billing.auth_views as auth_views
from metering_billing import track
from metering_billing.views import (CustomerView, EventViewSet,
                                    InitializeStripeView, PlansView,
                                    SubscriptionView, SubscriptionViewSet,
                                    UsageView)

router = routers.DefaultRouter()
router.register(r"event", EventViewSet)


def index(request):
    return render(request, "index.html")


urlpatterns = [
    # path("grappelli/", include("grappelli.urls")),
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api/customers", CustomerView.as_view(), name="customer"),
    path("api/customers/", CustomerView.as_view(), name="customer"),
    path("api/subscriptions", SubscriptionView.as_view(), name="subscription"),
    path("track/", track.track_event, name="track_event"),
    path("track", track.track_event, name="track_event"),
    path("api/usage", UsageView.as_view(), name="usage"),
    path("api/stripe", InitializeStripeView.as_view(), name="stripe_initialize"),
    path("api/plans", PlansView.as_view(), name="plans"),
    path("api/login/", auth_views.login_view, name="api-login"),
    path("api/logout", auth_views.logout_view, name="api-logout"),
    path("api/session/", auth_views.session_view, name="api-session"),
    path("api/whoami", auth_views.whoami_view, name="api-whoami"),
    path("", TemplateView.as_view(template_name="index.html")),
]
