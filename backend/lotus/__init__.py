import time

import django.db.backends.utils
from django.db import OperationalError

from .lotus_celery import celery as celery_app

__all__ = ("celery_app",)

original = django.db.backends.utils.CursorWrapper.execute


def execute_wrapper(*args, **kwargs):
    attempts = 0
    while attempts < 3:
        try:
            return original(*args, **kwargs)
        except OperationalError as e:
            code = e.args[0]
            if attempts == 2 or code != 1213:
                raise e
            attempts += 1
            time.sleep(0.2)


django.db.backends.utils.CursorWrapper.execute = execute_wrapper
