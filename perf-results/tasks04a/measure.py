"""Disposable TASKS-04A prefork worker memory experiment.

Starts real prefork Celery workers in separate processes on a disposable SQLite
database and Redis socket, measures each child's own USS/PSS/RSS at idle and
after a full Statistics sweep, and records the summed process footprint of the
separate and merged topologies.
"""

# ruff: noqa: INP001 -- standalone experiment

import argparse
import contextlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PERF = ROOT / "perf-results" / "tasks04"
BENCH = ROOT / "perf-results" / "tasks04a"
sys.path[:0] = [str(PERF), str(BENCH), str(ROOT), str(ROOT / "src")]
from scripts.benchmark_celery import disposable_redis  # noqa: E402


def main():
    """Measure prefork child memory for one worker topology."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--topology", choices=("separate", "merged"), default="separate")
    parser.add_argument("--samples", type=int, default=5)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "samples": [],
        "limitations": [
            "PSS is unavailable on native macOS; null is not zero.",
            "Child USS/PSS are read by the task inside that child, not from the parent process.",
            "Child USS/PSS are reported by the task running inside that child.",
            "Native host, no container CPU or memory quota.",
        ],
    }

    def save():
        args.output.write_text(json.dumps(report, indent=2, default=str) + "\n")

    with (
        tempfile.TemporaryDirectory(prefix="tasks04a-", dir="/tmp") as scratch,
        disposable_redis() as socket,
        contextlib.ExitStack() as stack,
    ):
        env = os.environ.copy()
        env.update(
            SECRET="disposable-benchmark",  # noqa: S106 -- disposable fixture
            DJANGO_SETTINGS_MODULE="bench_settings",
            TASKS04_DB=f"{scratch}/bench.sqlite3",
            TASKS04_REDIS_SOCKET=str(socket),
            LOG_DIR=scratch,
            FLOPPY_TEST_FAST_DB="1",
            DB_HOST="",
            FLOPPY_DB_PATH=f"{scratch}/unused.sqlite3",
            PYTHONPATH=os.pathsep.join(
                [str(PERF), str(BENCH), str(ROOT), str(ROOT / "src")]
            ),
            FLOPPY_PROCESS_ROLE="interactive",
        )
        os.environ.update(env)

        import django
        from django.conf import settings

        django.setup()
        settings.TESTING = False
        import bench_tasks
        import psutil
        from django.contrib.auth import get_user_model
        from django.core.cache import cache
        from django.core.management import call_command
        from django.db import connection
        from django.utils import timezone

        from app import statistics_sync as sync
        from app.models import Item, Movie, StatisticsSyncState
        from config.celery import app

        call_command("migrate", run_syncdb=True, verbosity=0)
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA journal_mode=WAL")
        memory_task = bench_tasks.memory_task
        sync_task = bench_tasks.sync_task

        if args.topology == "merged":
            lane_specs = [("interactive,celery", "combined")]
        else:
            lane_specs = [("interactive", "interactive"), ("celery", "background")]

        workers = []
        handles = []
        for queues, name in lane_specs:
            log_path = Path(scratch) / f"{name}.log"
            handle = log_path.open("w")
            handles.append((handle, log_path))
            command = [
                sys.executable,
                "-m",
                "celery",
                "-A",
                "config",
                "worker",
                "--include",
                "bench_tasks",
                "--loglevel=WARNING",
                "--pool=prefork",
                "--concurrency=1",
                "--prefetch-multiplier=1",
                "--queues",
                queues,
                "--hostname",
                f"{name}@%h",
                "--without-mingle",
                "--without-gossip",
            ]
            workers.append(
                subprocess.Popen(  # noqa: S603 -- fixed argv, disposable worker
                    command,
                    cwd=str(PERF),
                    env=env,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                )
            )
        stack.callback(lambda: [worker.kill() for worker in workers])
        stack.callback(lambda: [handle.close() for handle, _ in handles])

        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            with contextlib.suppress(Exception):
                if len(app.control.ping(timeout=1) or []) >= len(workers):
                    break
            time.sleep(0.5)
        else:
            message = "Celery workers did not start"
            raise RuntimeError(message)

        now = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)
        user = get_user_model()(
            username="tasks04a-10000",
            password="!",  # noqa: S106 -- unusable fixture password
            token="a" * 32,
            is_test_account=True,
        )
        get_user_model().objects.bulk_create([user])
        items = [
            Item(
                media_id=f"tasks04a-{index}",
                source="manual",
                media_type="movie",
                title=f"Synthetic movie {index}",
                runtime_minutes=100,
                genres=[{"id": 1, "name": "Synthetic"}],
            )
            for index in range(10000)
        ]
        Item.objects.bulk_create(items, batch_size=500)
        Movie.objects.bulk_create(
            [
                Movie(
                    user=user,
                    item=item,
                    status="Completed",
                    progress=1,
                    score=7,
                    end_date=now - timedelta(days=index % 3650),
                )
                for index, item in enumerate(items)
            ],
            batch_size=500,
        )

        def worker_stats():
            return app.control.inspect(timeout=2).stats() or {}

        def process_memory(pid):
            process = psutil.Process(pid)
            row = {"rss": process.memory_info().rss, "uss": None, "pss": None}
            with contextlib.suppress(psutil.Error):
                full = process.memory_full_info()
                row.update(
                    uss=getattr(full, "uss", None),
                    pss=getattr(full, "pss", None),
                )
            return row

        def footprint():
            stats = worker_stats()
            rows = {}
            for host, entry in stats.items():
                parent = process_memory(entry["pid"])
                rows[host] = {"parent": parent, "child": None}
            return rows

        def sample(label):
            stats = worker_stats()
            observations = []
            for queues, _ in lane_specs:
                queue = queues.split(",")[0]
                for iteration in range(args.samples + 1):
                    result = memory_task.apply_async(queue=queue).get(timeout=120)
                    observations.append(
                        {
                            "label": label,
                            "queue": queue,
                            "iteration": iteration,
                            "warmup": iteration == 0,
                            **result,
                        }
                    )
            report["samples"].extend(observations)
            report.setdefault(label, {})["worker_stats"] = stats
            report[label]["footprint"] = footprint()
            save()

        sample("idle")

        with contextlib.suppress(Exception):
            sync.mark_aggregate(
                user.id, full_sweep=True, reason="tasks04a_full_sweep"
            )
        sync_result = sync_task.apply_async(
            args=[user.id], queue="celery", priority=1
        ).get(timeout=900)
        report["load_result"] = sync_result
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            state = StatisticsSyncState.objects.get(user_id=user.id)
            if (
                state.hot_synced_generation >= state.generation
                and state.lease_expires_at is None
            ):
                break
            time.sleep(0.2)
        cell = {
            "records": 10000,
            "cold": True,
            "loaded": True,
            "topology": args.topology,
        }
        report["load"] = cell
        sample("loaded")
        cache.clear()
        for worker in workers:
            worker.terminate()
        for handle, _ in handles:
            handle.flush()
        report["environment"] = {
            "sha": subprocess.check_output(
                ["git", "rev-parse", "HEAD"],  # noqa: S607 -- fixed read-only command
                cwd=ROOT,
                text=True,
            ).strip(),
            "os": platform.platform(),
            "python": sys.version,
            "topology": args.topology,
            "workers": [spec[0] for spec in lane_specs],
            "pool": "prefork concurrency=1, prefetch=1",
            "fixture": {"records": 10000, "days": 3650, "types": ["movie"]},
            "resource_limits": "native host; no container CPU/memory quota",
        }
        save()
        # Celery's result consumer threads keep retrying a disappeared
        # disposable broker after the context closes.
        os._exit(0)


if __name__ == "__main__":
    main()
