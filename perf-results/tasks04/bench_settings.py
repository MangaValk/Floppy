"""Disposable settings shared by the driver and the TASKS-04 worker processes."""

# ruff: noqa: F403, INP001 -- standalone experiment

import os

from config.test_settings import *

_socket = os.environ["TASKS04_REDIS_SOCKET"]
_broker = f"redis+socket://{_socket}?virtual_host=1"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ["TASKS04_DB"],
        "OPTIONS": {"timeout": 5},
    }
}
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"unix://{_socket}?db=3",
        "TIMEOUT": 86400,
    }
}
CELERY_TASK_ALWAYS_EAGER = False
CELERY_RESULT_BACKEND = f"redis+socket://{_socket}?virtual_host=2"
CELERY_BROKER_URL = _broker
