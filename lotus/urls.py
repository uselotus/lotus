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
from django.contrib import admin
from django.urls import path
from django.conf.urls import include
from rest_framework import routers
from django.shortcuts import render
from billing.views.views import (
    EventViewSet,
    SubscriptionViewSet,
    CustomerView,
    SubscriptionView,
    UsageView,
)
from billing import track
from billing.views.stripe_views import InitializeStripeView
from django.views.generic import TemplateView

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
    path("stripe", InitializeStripeView.as_view(), name="stripe_initialize"),
    path("", TemplateView.as_view(template_name="index.html")),
]
