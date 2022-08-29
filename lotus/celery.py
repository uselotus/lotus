import os

from django.conf import settings

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lotus.settings")

celery = Celery("lotus")
# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
celery.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
celery.autodiscover_tasks()  # lambda: settings.INSTALLED_APPS)


@celery.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
