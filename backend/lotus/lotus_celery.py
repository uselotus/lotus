import os

import cronitor.celery
from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lotus.settings")

celery = Celery("lotus")
# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
celery.config_from_object("django.conf:settings", namespace="CELERY")


CRONITOR_API_KEY = settings.CRONITOR_API_KEY
if CRONITOR_API_KEY and CRONITOR_API_KEY != "":
    cronitor.celery.initialize(celery, api_key=os.environ.get("CRONITOR_API_KEY"))


# Load task modules from all registered Django apps.
celery.autodiscover_tasks()  # lambda: settings.INSTALLED_APPS)
