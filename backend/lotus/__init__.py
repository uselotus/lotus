from __future__ import absolute_import, unicode_literals

import sys

from .lotus_celery import celery as celery_app

__all__ = ("celery_app",)
