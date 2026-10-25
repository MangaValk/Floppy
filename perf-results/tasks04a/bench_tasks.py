"""Benchmark-only tasks loaded into the production Celery app for TASKS-04A."""

# ruff: noqa: INP001 -- standalone experiment

import gc
import os
import threading
import time

from django.conf import settings

if settings.TESTING:
    # The app registry ran with TESTING=True so startup sweeps were skipped;
    # the sync body must behave like production from here on.
    settings.TESTING = False

import psutil
from celery import shared_task
from django.db import connections

from app import statistics_sync as sync


@shared_task(name="tasks04a.memory")
def memory_task():
    """Return this prefork child's own memory accounting."""
    full = psutil.Process().memory_full_info()
    return {
        "pid": os.getpid(),
        "rss": full.rss,
        "uss": getattr(full, "uss", None),
        "pss": getattr(full, "pss", None),
        "gc_freeze_count": gc.get_freeze_count(),
        "gc_count": sum(gc.get_count()),
    }


@shared_task(name="tasks04a.sync")
def sync_task(user_id: int):
    """Run a production sync body and record its peak child memory."""
    process = psutil.Process()
    full = process.memory_full_info()
    peak = {key: getattr(full, key, None) for key in ("rss", "uss", "pss")}
    stop = threading.Event()

    def sample():
        while not stop.wait(0.02):
            full = process.memory_full_info()
            for key in ("rss", "uss", "pss"):
                value = getattr(full, key, None)
                if value is not None:
                    peak[key] = max(peak.get(key) or 0, value)

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    started = time.perf_counter()
    try:
        result = sync.sync_task_body(user_id)
    finally:
        stop.set()
        connections.close_all()
    return {
        "status": result["status"],
        "published": list(result["published"]),
        "wall_s": time.perf_counter() - started,
        "pid": os.getpid(),
        "peak_bytes": peak,
    }
