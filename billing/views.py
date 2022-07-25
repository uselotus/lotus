from django.shortcuts import render
from django.forms.models import model_to_dict
from .models import Customer, Event, Subscription
from .serializers import EventSerializer, SubscriptionSerializer
from rest_framework import viewsets

# Create your views here.


class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer


class SubscriptionViewSet(viewsets.ModelViewSet):
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
