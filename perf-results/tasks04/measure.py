"""Disposable TASKS-04 lane experiment. Run from the repo root.

Two separate Celery worker processes replay the constrained/standard topology:
one consumes ``interactive`` (webhooks) and one consumes ``celery`` (bulk).
``--lanes merged`` runs one worker consuming both, like the minimal tier.

No configured application database, broker, cache, or providers are used.
"""

# ruff: noqa: INP001, T201 -- standalone experiment with fixed fixture values and JSON progress output

import argparse
import contextlib
import cProfile
import hashlib
import json
import logging
import os
import platform
import pstats
import subprocess
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
PERF = Path(__file__).resolve().parent
sys.path[:0] = [str(PERF), str(ROOT), str(ROOT / "src")]
from scripts.benchmark_celery import disposable_redis  # noqa: E402


def main():
    """Replay controlled refreshes and observe both worker lanes."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--idle-seconds", type=int, default=1800)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--lanes", choices=("separate", "merged"), default="separate")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "samples": [],
        "idle": [],
        "limitations": [
            "Native macOS threads-pool Celery workers in separate processes; not a prefork/container measurement.",
            "PSS and container memory are unavailable on this native run; null is not zero.",
            "Playback is a priority-0 scheduling/write probe, not an HTTP/provider integration benchmark.",
            "DB writes count SQL statements, not physical I/O; Redis operations include instrumentation.",
        ],
    }

    def save():
        args.output.write_text(json.dumps(report, indent=2, default=str) + "\n")

    with (
        tempfile.TemporaryDirectory(prefix="tasks04-", dir="/tmp") as scratch,
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
                [str(PERF), str(ROOT), str(ROOT / "src")]
            ),
        )
        os.environ.update(env)

        import django
        from django.conf import settings

        django.setup()
        settings.TESTING = False
        logging.disable(logging.WARNING)
        import bench_app
        import psutil
        import redis
        from django.contrib.auth import get_user_model
        from django.core.management import call_command
        from django.db import connection
        from django.utils import timezone

        from app import statistics_sync as sync
        from app.models import (
            Item,
            Movie,
            StatisticsDirtyDay,
            StatisticsSnapshot,
            StatisticsSyncState,
        )

        call_command("migrate", run_syncdb=True, verbosity=0)
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA journal_mode=WAL")
        client = redis.Redis(unix_socket_path=str(socket), db=3)
        app = bench_app.app
        sync_task, playback = bench_app.sync_task, bench_app.playback
        events_key = bench_app.EVENTS_KEY
        started_key = bench_app.STARTED_KEY

        if args.lanes == "merged":
            lane_specs = [("interactive,celery", "combined")]
        else:
            lane_specs = [("interactive", "interactive"), ("celery", "background")]

        logs = []
        workers = []
        for queues, name in lane_specs:
            log_path = Path(scratch) / f"{name}.log"
            log_file = log_path.open("w")
            logs.append((log_file, log_path))
            command = [
                sys.executable,
                "-m",
                "celery",
                "-A",
                "bench_app.app",
                "worker",
                "--loglevel=WARNING",
                "--pool=threads",
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
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                )
            )
        stack.callback(lambda: [worker.kill() for worker in workers])
        stack.callback(lambda: [handle.close() for handle, _ in logs])

        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            with contextlib.suppress(Exception):
                if len(app.control.ping(timeout=1) or []) >= len(workers):
                    break
            time.sleep(0.5)
        else:
            message = "Celery workers did not start"
            raise RuntimeError(message)

        now = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)
        users = []
        for count in (100, 10000):
            user = get_user_model()(
                username=f"tasks04-{count}",
                password="!",  # noqa: S106 -- unusable fixture password
                token=f"{count:032}",
                is_test_account=True,
            )
            get_user_model().objects.bulk_create([user])
            items = [
                Item(
                    media_id=f"tasks04-{count}-{i}",
                    source="manual",
                    media_type="movie",
                    title=f"Synthetic movie {i}",
                    runtime_minutes=100,
                    genres=[{"id": 1, "name": "Synthetic"}],
                )
                for i in range(count)
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
                        end_date=now - timedelta(days=i % 3650),
                    )
                    for i, item in enumerate(items)
                ],
                batch_size=500,
            )
            users.append((count, user))

        report["environment"] = {
            "sha": subprocess.check_output(
                ["git", "rev-parse", "HEAD"],  # noqa: S607 -- fixed read-only command
                cwd=ROOT,
                text=True,
            ).strip(),
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "os": platform.platform(),
            "cpu": platform.processor(),
            "logical_cpus": os.cpu_count(),
            "python": sys.version,
            "database": "disposable SQLite WAL, current-model syncdb",
            "sqlite": connection.Database.sqlite_version,
            "redis": client.info("server")["redis_version"],
            "worker": "separate threads-pool processes, concurrency=1, prefetch=1",
            "topology": {"lanes": args.lanes, "workers": [spec[0] for spec in lane_specs]},
            "task_budget_seconds": sync._task_budget_seconds(),
            "fixture": {
                "small": 100,
                "large": 10000,
                "days": 3650,
                "types": ["movie"],
                "credits": 0,
                "genres": "complete synthetic metadata",
            },
            "container_memory_peak": None,
            "resource_limits": "native host; no container CPU/memory quota",
        }
        sync_route = settings.CELERY_TASK_ROUTES["app.tasks.statistics_sync_task"]
        save()

        def read_events(start):
            return [
                json.loads(item)
                for item in client.lrange(events_key, start, -1)
            ]

        def active_tasks():
            active = app.control.inspect(timeout=0.5).active() or {}
            return any(active.values())

        def wait_quiet(uid, timeout=600):
            deadline = time.monotonic() + timeout
            next_reconcile = time.monotonic() + 60
            while time.monotonic() < deadline:
                state = StatisticsSyncState.objects.get(user_id=uid)
                if (
                    state.hot_synced_generation >= state.generation
                    and state.lease_expires_at is None
                ):
                    return
                if time.monotonic() >= next_reconcile:
                    sync.ensure_sync(uid, scheduled=True)
                    next_reconcile += 60
                time.sleep(0.1)
            message = "Statistics failed to converge"
            raise TimeoutError(message)

        for count, user in users:
            for cold in (True, False):
                for loaded in (False, True):
                    for iteration in range(args.runs + 1):
                        if cold:
                            from django.core.cache import cache

                            cache.clear()
                        with patch.object(sync, "ensure_sync"):
                            sync.mark_aggregate(
                                user.id,
                                full_sweep=True,
                                reason="tasks04_manual_refresh",
                            )
                        client.delete(started_key)
                        event_start = client.llen(events_key)
                        enqueue = {
                            "user": user.id,
                            "queue": sync_route["queue"],
                            "priority": sync_route["priority"],
                            "time": time.perf_counter(),
                        }
                        wall, cpu = time.perf_counter(), time.process_time()
                        sync_task.apply_async(
                            args=[user.id, time.perf_counter()],
                            queue=sync_route["queue"],
                            priority=sync_route["priority"],
                        )
                        if loaded:
                            probe_deadline = time.monotonic() + 120
                            while (
                                time.monotonic() < probe_deadline
                                and client.get(started_key) is None
                            ):
                                time.sleep(0.005)
                            if client.get(started_key) is None:
                                message = "Statistics task did not start"
                                raise TimeoutError(message)
                            playback.apply_async(
                                args=[user.id, time.perf_counter()],
                                queue="interactive",
                                priority=0,
                            ).get(timeout=600)
                        wait_quiet(user.id)
                        while active_tasks():
                            time.sleep(0.05)
                        all_time = StatisticsSnapshot.objects.get(
                            user_id=user.id, range_name="All Time"
                        ).payload
                        all_time_plays = all_time["movie_consumption"]["plays"]["total"]
                        if all_time_plays != count:
                            message = f"All Time lost plays: {all_time_plays} != {count}"
                            raise AssertionError(message)
                        row = {
                            "records": count,
                            "cold": cold,
                            "loaded": loaded,
                            "iteration": iteration,
                            "warmup": iteration == 0,
                            "wall_s": time.perf_counter() - wall,
                            "cpu_s": time.process_time() - cpu,
                            "enqueue": enqueue,
                            "tasks": read_events(event_start),
                            "invariants": {
                                "all_time_movie_plays": all_time_plays,
                                "dirty_days": StatisticsDirtyDay.objects.filter(
                                    user_id=user.id
                                ).count(),
                                "snapshots": StatisticsSnapshot.objects.filter(
                                    user_id=user.id
                                ).count(),
                                "stale_snapshots": StatisticsSnapshot.objects.filter(
                                    user_id=user.id,
                                    generation__lt=StatisticsSyncState.objects.get(
                                        user_id=user.id
                                    ).generation,
                                ).count(),
                            },
                        }
                        report["samples"].append(row)
                        save()
                        print(
                            json.dumps(
                                {
                                    key: value
                                    for key, value in row.items()
                                    if key != "tasks"
                                }
                            ),
                            flush=True,
                        )

        profiler = cProfile.Profile()
        profiler.runcall(sync.run_sync, users[-1][1].id, only_ranges=["All Time"])
        stats = pstats.Stats(profiler)
        report["profile"] = [
            {
                "file": str(Path(file).name),
                "line": line,
                "function": function,
                "calls": values[1],
                "self_s": values[2],
                "cumulative_s": values[3],
            }
            for (file, line, function), values in sorted(
                stats.stats.items(), key=lambda pair: pair[1][3], reverse=True
            )[:40]
        ]
        inspect_stats = app.control.inspect(timeout=2).stats() or {}
        report["worker_stats"] = inspect_stats

        def worker_memory(pid):
            process = psutil.Process(pid)
            row = {"rss": process.memory_info().rss, "uss": None, "pss": None}
            with contextlib.suppress(psutil.Error):
                full = process.memory_full_info()
                row.update(
                    uss=getattr(full, "uss", None),
                    pss=getattr(full, "pss", None),
                )
            return row

        report["idle_workers"] = {
            host: worker_memory(entry["pid"])
            for host, entry in inspect_stats.items()
        }
        idle_start = time.perf_counter()
        idle_events = client.llen(events_key)
        idle_cpu = time.process_time()
        idle_redis = client.info("stats")["total_commands_processed"]
        while time.perf_counter() - idle_start < args.idle_seconds:
            tick = time.perf_counter()
            queued = sync.reconcile()
            report["idle"].append(
                {
                    "elapsed_s": tick - idle_start,
                    "queued": queued,
                    "executions": client.llen(events_key) - idle_events,
                    "enqueues": queued,
                    "cpu_s": time.process_time() - idle_cpu,
                    "redis_commands": client.info("stats")["total_commands_processed"]
                    - idle_redis,
                }
            )
            save()
            print(json.dumps({"idle": report["idle"][-1]}), flush=True)
            time.sleep(
                min(
                    60,
                    max(0, args.idle_seconds - (time.perf_counter() - idle_start)),
                )
            )
        report["idle_summary"] = {
            "wall_s": time.perf_counter() - idle_start,
            "cpu_s": time.process_time() - idle_cpu,
            "executions": client.llen(events_key) - idle_events,
        }
        for worker in workers:
            worker.terminate()
        for handle, _ in logs:
            handle.flush()
        save()


if __name__ == "__main__":
    main()
