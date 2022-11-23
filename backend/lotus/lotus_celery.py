import os
import ssl

from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lotus.settings")
ON_HEROKU = settings.ON_HEROKU

celery_kwargs = {}
if ON_HEROKU:
    # See https://devcenter.heroku.com/articles/celery-heroku#using-redis-as-a-broker
    # for more details
    # Heroku Redis requires SSL
    celery_kwargs["broker_use_ssl"] = {
        "ssl_cert_reqs": ssl.CERT_NONE,
    }
    celery_kwargs["redis_backend_use_ssl"] = {
        "ssl_cert_reqs": ssl.CERT_NONE,
    }

celery = Celery("lotus", **celery_kwargs)
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
