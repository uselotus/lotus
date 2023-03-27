from __future__ import unicode_literals

import logging

import django
from django.core import signals
from django.core.cache.backends.base import BaseCache

logging.basicConfig()
logger = logging.getLogger(__name__)


def get_cache(backend, **kwargs):
    from django.core import cache as dj_cache

    if django.VERSION <= (1, 6):
        cache = dj_cache.get_cache(backend, **kwargs)
    elif django.VERSION >= (3, 2):
        cache = dj_cache.caches.create_connection(backend)
    else:  # Django 1.7 to 3.1
        cache = dj_cache._create_cache(backend, **kwargs)

    # Some caches -- python-memcached in particular -- need to do a cleanup at the
    # end of a request cycle. If not implemented in a particular backend
    # cache.close is a no-op. Not available in Django 1.5
    if hasattr(cache, "close"):
        signals.request_finished.connect(cache.close)
    return cache


class FallbackCache(BaseCache):
    _cache = None
    _cache_fallback = None

    def __init__(self, params=None, *args, **kwargs):
        BaseCache.__init__(self, *args, **kwargs)
        self._cache = get_cache("main_cache")
        self._cache_fallback = get_cache("fallback_cache")

    def add(self, key, value, timeout=None, version=None):
        return self._call_with_fallback(
            "add", key, value, timeout=timeout, version=version
        )

    def get(self, key, default=None, version=None):
        return self._call_with_fallback("get", key, default=default, version=version)

    def set(self, key, value, timeout=None, version=None, client=None):
        return self._call_with_fallback(
            "set", key, value, timeout=timeout, version=version
        )

    def delete_pattern(self, pattern, version=None):
        return self._call_with_fallback(
            "delete_pattern", pattern, version=version, raise_err=False
        )

    def delete(self, key, version=None):
        return self._call_with_fallback("delete", key, version=version)

    def clear(self):
        return self._call_with_fallback("clear")

    def keys(self, pattern="*"):
        return self._call_with_fallback("keys", pattern)

    def delete_many(self, keys, version=None):
        return self._call_with_fallback("delete_many", keys, version=version)

    def _call_with_fallback(self, method, *args, **kwargs):
        raise_err = kwargs.pop("raise_err", True)
        try:
            return self._call_main_cache(args, kwargs, method)
        except Exception as e:
            logger.warning("Switch to fallback cache")
            logger.exception(e)
            if raise_err:
                return self._call_fallback_cache(args, kwargs, method)
            else:
                try:
                    return self._call_fallback_cache(args, kwargs, method)
                except Exception as e:
                    logger.warning("Fallback cache failed")
                    logger.exception(e)
                    return None

    def _call_main_cache(self, args, kwargs, method):
        return getattr(self._cache, method)(*args, **kwargs)

    def _call_fallback_cache(self, args, kwargs, method):
        return getattr(self._cache_fallback, method)(*args, **kwargs)
