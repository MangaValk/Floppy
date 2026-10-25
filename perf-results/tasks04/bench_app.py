"""Disposable Celery app for the TASKS-04 lane experiment.

Workers run as separate processes so the interactive and background lanes can
be observed independently. Only the task bodies are production code.
"""

# ruff: noqa: INP001, E402 -- standalone experiment

import gc
import json
import os
import threading
import time
from collections import Counter

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.test_settings")

import django
from django.conf import settings

django.setup()
# The app registry ran with TESTING=True so startup sweeps were skipped; the
# sync body itself must behave like production.
settings.TESTING = False

import psutil
import redis
from celery import Celery
from django.db import connection, connections
from django.utils import timezone

from app import statistics_sync as sync
from app.models import Movie

EVENTS_KEY = "tasks04:events"
STARTED_KEY = "tasks04:sync_started"

app = Celery(
    "tasks04bench",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
app.conf.update(
    task_default_queue="interactive",
    task_always_eager=False,
    worker_prefetch_multiplier=1,
    broker_transport_options={
        "queue_order_strategy": "priority",
        "priority_steps": list(range(10)),
        "sep": ":",
    },
    worker_hijack_root_logger=False,
    worker_redirect_stdouts=False,
)
client = redis.Redis(unix_socket_path=os.environ["TASKS04_REDIS_SOCKET"], db=3)


def _memory():
    full = psutil.Process().memory_full_info()
    return {
        "rss": full.rss,
        "uss": getattr(full, "uss", None),
        "pss": getattr(full, "pss", None),
    }


def _observed(kind, uid, sent, operation):
    started, cpu = time.perf_counter(), time.thread_time()
    if kind == "sync":
        client.set(STARTED_KEY, time.time(), ex=120)
    redis_before = client.info("stats")["total_commands_processed"]
    counts = Counter()
    row = {
        "kind": kind,
        "user": uid,
        "queue_wait_s": started - sent,
        "pid": os.getpid(),
        "peak_bytes": _memory(),
    }
    stop = threading.Event()

    def sample():
        while not stop.wait(0.02):
            for key, value in _memory().items():
                if value is not None:
                    row["peak_bytes"][key] = max(
                        row["peak_bytes"].get(key) or 0, value
                    )

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()

    def query(execute, sql, params, many, context):
        counts[sql.split()[0].upper()] += 1
        return execute(sql, params, many, context)

    try:
        with connection.execute_wrapper(query):
            result = operation()
    finally:
        stop.set()
        row.update(
            result=result,
            wall_s=time.perf_counter() - started,
            cpu_s=time.thread_time() - cpu,
            sql=dict(counts),
            db_write_statements=sum(
                counts[k] for k in ("INSERT", "UPDATE", "DELETE")
            ),
            redis_commands=client.info("stats")["total_commands_processed"]
            - redis_before,
        )
        client.rpush(EVENTS_KEY, json.dumps(row))
        connections.close_all()
    return result


@app.task(name="tasks04.sync")
def sync_task(uid, sent=None):
    """Run the production sync body inside this worker lane."""
    sent = time.perf_counter() if sent is None else sent

    def operation():
        result = sync.sync_task_body(uid)
        return {"status": result["status"], "published": list(result["published"])}

    return _observed("sync", uid, sent, operation)


@app.task(name="tasks04.memory")
def memory_task():
    """Return this worker child's own memory accounting."""
    full = psutil.Process().memory_full_info()
    return {
        "pid": os.getpid(),
        "rss": full.rss,
        "uss": getattr(full, "uss", None),
        "pss": getattr(full, "pss", None),
        "gc_freeze_count": gc.get_freeze_count(),
        "gc_count": sum(gc.get_count()),
    }


@app.task(name="tasks04.playback")
def playback(uid, sent):
    """Mutate one play and mark today, like a webhook acknowledgement."""

    def operation():
        movie = Movie.objects.filter(user_id=uid).order_by("id").first()
        Movie.objects.filter(pk=movie.pk).update(score=6 if movie.score != 6 else 9)  # noqa: PLR2004
        sync.mark_days(uid, [timezone.localdate()], reason="tasks04_playback_probe")
        return "marked"

    return _observed("playback_probe", uid, sent, operation)


def _dispatch(*args, **options):
    return sync_task.apply_async(*args, **options)





def install_dispatch():
    """Send every production Statistics publication to the benchmark task."""
    from app import tasks_interactive

    tasks_interactive.statistics_sync_task.apply_async = _dispatch


install_dispatch()
