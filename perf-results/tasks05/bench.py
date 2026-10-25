"""TASKS-05 offline replay; run only in a disposable, network-isolated container.

python /results/bench.py baseline|after|smoke [idle_seconds=1800]
The worker subprocess uses the same settings, fixtures and instrumentation.
"""
import cProfile
import hashlib
import json
import os
import platform
import resource
import subprocess
import sys
import threading
import time
from collections import Counter
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

MODE = sys.argv[1]
WORKER = MODE == "worker"
OUT = Path("/results")
os.environ.update(SECRET="tasks05-disposable", DJANGO_SETTINGS_MODULE="config.settings",
                  FLOPPY_TEST_FAST_DB="1", FLOPPY_DB_PATH="/tmp/tasks05.sqlite3",
                  LOG_DIR="/tmp/tasks05-logs", FLOPPY_PROCESS_ROLE="interactive",
                  REDIS_URL="redis://tasks05-redis:6379/0")
sys.path.insert(0, "/source")
from django.conf import settings

settings.DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "/tmp/tasks05.sqlite3",
                                  "OPTIONS": {"timeout": 30, "transaction_mode": "IMMEDIATE"}}}
settings.CACHES = {"default": {"BACKEND": "django_redis.cache.RedisCache", "LOCATION": "redis://tasks05-redis:6379/1", "TIMEOUT": 18000}}
settings.CELERY_BROKER_URL = "redis://tasks05-redis:6379/0"
settings.CELERY_RESULT_BACKEND = "redis://tasks05-redis:6379/2"
settings.CELERY_TASK_ALWAYS_EAGER = settings.TESTING = False
settings.CELERY_TASK_STORE_EAGER_RESULT = False
settings.CELERY_WORKER_MAX_TASKS_PER_CHILD = None
settings.CELERY_WORKER_MAX_MEMORY_PER_CHILD = None
settings.MIGRATION_MODULES = dict.fromkeys(("app", "users", "lists", "integrations", "events", "auth", "contenttypes"))
settings.LOGGING = {"version": 1, "disable_existing_loggers": True}
import django
saved_argv = sys.argv
sys.argv = ["manage.py", "shell"]  # Disable unrelated web-startup maintenance timers.
try:
    django.setup()
finally:
    sys.argv = saved_argv
import psutil
import redis
from celery import signals
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.utils import timezone
from simple_history.utils import bulk_create_with_history
from app import statistics_sync as sync
from app.models import Item, Movie, StatisticsDirtyDay, StatisticsSnapshot, StatisticsSyncState, Status
from app.statistics_day_cache import _day_cache_key
from app.tasks_interactive import statistics_sync_task, reconcile_statistics_sync_task
from config.celery import app
from integrations.tasks._webhook import process_webhook

client = redis.Redis(host="tasks05-redis", db=3, decode_responses=True)
broker = redis.Redis(host="tasks05-redis", db=0)
TASKS, ENQUEUES, SYNCS, OTHER = "tasks05:tasks", "tasks05:enqueues", "tasks05:syncs", "tasks05:other"
MEASURED_TASKS = {"app.tasks.statistics_sync_task", "Reconcile statistics sync", "Process media server webhook", "tasks05.block"}
current = {}
redis_commands = 0
original_command = redis.Redis.execute_command
original_pipeline = redis.client.Pipeline.execute

def counted_command(self, *args, **kwargs):
    global redis_commands
    if self is not client and self is not broker:
        redis_commands += 1
    return original_command(self, *args, **kwargs)

def counted_pipeline(self, *args, **kwargs):
    global redis_commands
    redis_commands += len(self.command_stack) + (2 if self.transaction else 0)
    return original_pipeline(self, *args, **kwargs)

redis.Redis.execute_command = counted_command
redis.client.Pipeline.execute = counted_pipeline

def emit(key, value):
    client.rpush(key, json.dumps(value))

def cgroup():
    return {name: (Path("/sys/fs/cgroup")/name).read_text().strip()
            for name in ("cpu.stat", "cpu.max", "memory.peak", "memory.current", "memory.max", "pids.max")}

def sql_count(execute, sql, params, many, context):
    current["queries"] += 1
    if sql.lstrip().split(None, 1)[0].upper() in {"INSERT", "UPDATE", "DELETE", "REPLACE"}:
        current["writes"] += 1
    return execute(sql, params, many, context)

@signals.before_task_publish.connect(weak=False)
def sent(sender=None, headers=None, **kwargs):
    headers["tasks05_sent"] = time.time()
    emit(ENQUEUES if sender in MEASURED_TASKS else OTHER,
         {"name": sender, "id": headers["id"], "at": headers["tasks05_sent"]})

@signals.task_prerun.connect(weak=False)
def started(task_id=None, task=None, **kwargs):
    current.clear()
    current.update(id=task_id, name=task.name, at=time.time(), cpu_start=time.process_time(), queries=0, writes=0,
                   redis_start=redis_commands)
    current["queue_wait_s"] = current["at"] - (task.request.headers or {}).get("tasks05_sent", current["at"])
    current["wrapper"] = connection.execute_wrapper(sql_count)
    current["wrapper"].__enter__()

@signals.task_postrun.connect(weak=False)
def finished(state=None, **kwargs):
    current.pop("wrapper").__exit__(None, None, None)
    current["wall_s"] = time.time()-current["at"]
    current["cpu_s"] = time.process_time()-current.pop("cpu_start")
    current["state"] = state
    current["redis_commands"] = redis_commands-current.pop("redis_start")
    emit(TASKS, current)

@app.task(name="tasks05.block")
def block(seconds):
    client.set("tasks05:blocked", "1")
    time.sleep(seconds)

original_run = sync.run_sync
def tracked_run(*args, **kwargs):
    if client.delete("tasks05:profile_next"):
        profile = cProfile.Profile()
        result = profile.runcall(original_run, *args, **kwargs)
        profile.dump_stats(str(OUT/f"{client.get('tasks05:mode')}-duplicate.prof"))
    else:
        result = original_run(*args, **kwargs)
    emit(SYNCS, {"user": args[0], "status": result["status"], "published": sorted(result["published"])})
    return result

original_aggregate = sync._aggregate_range
def aggregate(*args, **kwargs):
    if client.delete("tasks05:fail_once"):
        raise RuntimeError("controlled TASKS-05 failure")
    return original_aggregate(*args, **kwargs)

def playback(processor, payload, user):
    row = Movie.objects.filter(user=user).order_by("id").first()
    row.progress += 1
    row.end_date = timezone.now()
    row.save(update_fields=["progress", "end_date"])
    processor.outcome = "persisted"

if WORKER:
    with patch.object(sync, "run_sync", tracked_run), patch.object(sync, "_aggregate_range", aggregate), \
         patch("app.tasks.enqueue_credits_backfill_items"), patch("app.tasks.enqueue_genre_backfill_items"), \
         patch("integrations.webhooks.jellyfin.JellyfinWebhookProcessor.process_payload", playback):
        app.worker_main(["worker", "--pool=prefork", "--concurrency=1", "--queues=interactive",
                         "--without-gossip", "--without-mingle", "--without-heartbeat", "--loglevel=ERROR"])
    sys.exit()

def rows(key, start=0):
    return [json.loads(value) for value in client.lrange(key, start, -1)]

def depth():
    # TYPE and length must be atomic: a new list can appear between TYPE none
    # and ZCARD, killing a sampling thread with WRONGTYPE.
    separator = settings.CELERY_BROKER_TRANSPORT_OPTIONS.get("sep", "\x06\x16")
    keys = ["interactive" + (f"{separator}{p}" if p else "") for p in range(10)]
    raw = broker.eval("""
        local result = {}
        for _, key in ipairs(KEYS) do
            local kind = redis.call('TYPE', key).ok
            table.insert(result, kind)
            table.insert(result, kind == 'list' and redis.call('LLEN', key) or 0)
            table.insert(result, kind == 'zset' and redis.call('ZCARD', key) or 0)
        end
        return result
    """, len(keys), *keys)
    return {str(p): {"type": raw[p*3].decode(), "llen": raw[p*3+1], "zcard": raw[p*3+2]} for p in range(10)}

def wait_until(predicate, timeout=300):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise TimeoutError("condition not reached")

def drained():
    return (client.llen(TASKS) == client.llen(ENQUEUES)
            and not broker.hlen("unacked")
            and not any(v["llen"] or v["zcard"] for v in depth().values()))

def wait_drain():
    wait_until(drained)
    time.sleep(0.15)
    assert drained()

def hot_done(ids):
    return not StatisticsSyncState.objects.filter(user_id__in=ids, hot_synced_generation__lt=django.db.models.F("generation")).exists()

def measure(label, operation, ids, reconcile_end=False):
    before = {key: client.llen(key) for key in (TASKS, ENQUEUES, SYNCS, OTHER)}
    redis_before = client.info("stats")["total_commands_processed"]
    redis_cpu_before = client.info("cpu")
    redis_app_before = redis_commands
    cg_before = cgroup()
    done = threading.Event()
    peaks = Counter()
    queue_samples = []
    sample_errors = []
    def sample():
        while not done.is_set():
            totals = Counter()
            for proc in [psutil.Process(), *psutil.Process().children(recursive=True)]:
                try:
                    mem = proc.memory_full_info()
                    for name in ("rss", "uss", "pss"):
                        totals[name] += getattr(mem, name, 0)
                except (psutil.Error, OSError):
                    pass
            for name, value in totals.items():
                peaks[name] = max(peaks[name], value)
            try:
                queue_samples.append({"at": time.time(), "keys": depth()})
            except Exception as exc:
                sample_errors.append(repr(exc))
                return
            done.wait(0.2 if "idle" not in label else 5)
    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    tick, cpu = time.monotonic(), time.process_time()
    parent_queries = Counter()
    def capture(execute, sql, params, many, context):
        parent_queries["queries"] += 1
        if sql.lstrip().split(None, 1)[0].upper() in {"INSERT", "UPDATE", "DELETE", "REPLACE"}:
            parent_queries["writes"] += 1
        return execute(sql, params, many, context)
    with connection.execute_wrapper(capture):
        operation()
        wait_drain()
        if reconcile_end:
            reconcile_statistics_sync_task.apply_async()
            wait_drain()
        wait_until(lambda: hot_done(ids))
    done.set()
    sampler.join()
    assert not sample_errors, sample_errors
    result = {"label": label, "wall_s": time.monotonic()-tick, "parent_cpu_s": time.process_time()-cpu,
              "redis_operations_including_instrumentation": client.info("stats")["total_commands_processed"]-redis_before,
              "parent_redis_commands": redis_commands-redis_app_before,
              "redis_cpu_before": redis_cpu_before, "redis_cpu_after": client.info("cpu"),
              "parent_sql": dict(parent_queries), "tasks": rows(TASKS, before[TASKS]),
              "enqueues": rows(ENQUEUES, before[ENQUEUES]), "syncs": rows(SYNCS, before[SYNCS]),
              "background_publications_not_consumed": rows(OTHER, before[OTHER]),
              "peak_sampled_process_bytes": dict(peaks), "cgroup_before": cg_before, "cgroup_after": cgroup(),
              "queue_samples": queue_samples}
    with (OUT/f"{MODE}.jsonl").open("a") as file:
        file.write(json.dumps(result)+"\n")
    print(json.dumps({"label": label, "wall_s": result["wall_s"], "tasks": len(result["tasks"]),
                      "syncs": result["syncs"]}), flush=True)
    return result

def seed(count):
    user = get_user_model().objects.create_user(username=f"tasks05-{count}", anime_enabled=False)
    now = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)
    items = Item.objects.bulk_create([Item(media_id=f"{count}-{i}", source="manual", media_type="movie",
        title=f"Fixture {i}", runtime_minutes=90) for i in range(count)])
    bulk_create_with_history([Movie(user=user, item=item, status=Status.COMPLETED.value, progress=1,
        start_date=now-timedelta(days=i % 7), end_date=now-timedelta(days=i % 7))
        for i, item in enumerate(items)], Movie, batch_size=500)
    return user

print("schema and controlled fixtures", flush=True)
client.set("tasks05:mode", MODE)
call_command("migrate", run_syncdb=True, verbosity=0)
users = [seed(n) for n in ((20, 100) if MODE == "smoke" else (100, 12000))]
metadata = {"source_sha": os.environ.get("TASKS05_SHA"), "platform": platform.platform(), "cpu": platform.processor(),
    "source_hash": hashlib.sha256(Path("/source/app/statistics_sync.py").read_bytes()).hexdigest(),
    "cpu_count": os.cpu_count(), "python": sys.version, "django": django.get_version(),
    "sqlite": connection.Database.sqlite_version, "redis": client.info("server")["redis_version"],
    "limits": {"nofile": resource.getrlimit(resource.RLIMIT_NOFILE), "cgroup": cgroup()},
    "counts": {"items": Item.objects.count(), "movies": Movie.objects.count(), "history": Movie.history.count()},
    "worker": {"pool": "prefork", "concurrency": 1, "prefetch": settings.CELERY_WORKER_PREFETCH_MULTIPLIER},
    "broker_transport_options": settings.CELERY_BROKER_TRANSPORT_OPTIONS,
    "gate_seconds": sync._enqueue_gate_seconds(), "cache": "empty isolated Redis at initial start; warm after cold sweep"}
(OUT/f"{MODE}-environment.json").write_text(json.dumps(metadata, indent=2))
worker_log = (OUT/f"{MODE}-worker.log").open("w")
worker = subprocess.Popen([sys.executable, __file__, "worker"], stdout=worker_log, stderr=subprocess.STDOUT)
try:
    time.sleep(4)
    assert worker.poll() is None
    ids = [u.pk for u in users]
    def cold():
        for user in users:
            sync.mark_aggregate(user.pk, full_sweep=True)
    measure("warmup-cold", cold, ids, reconcile_end=True)
    for user in users:
        for cache_state in ("warm", "cold"):
            for load in ("quiet", "playback"):
                for iteration in range(1 if MODE == "smoke" else 6):
                    if cache_state == "cold":
                        cache.delete_many([_day_cache_key(user.pk, timezone.localdate()-timedelta(days=i)) for i in range(7)])
                    cache.delete(sync._gate_key(user.pk))
                    def operation():
                        sync.mark_days(user.pk, [timezone.localdate()])
                        if load == "playback":
                            for j in range(3):
                                process_webhook.apply_async(args=["jellyfin", {"Event": "Stop"}, user.pk],
                                    kwargs={"received_at": time.time(), "event_id": f"tasks05-{iteration}-{j}"}, queue="interactive", priority=0)
                    measure(f"{user.username}-{cache_state}-{load}-{iteration}", operation, [user.pk])
    # Reproduce three one-minute Beat ticks accumulating behind a busy worker.
    for iteration in range(1 if MODE == "smoke" else 6):
        user = users[-1]
        cache.delete(sync._gate_key(user.pk))
        def backlog():
            client.delete("tasks05:blocked")
            seconds = 125 if iteration == 0 and MODE != "smoke" else 1
            block.apply_async(args=[seconds], queue="interactive", priority=0)
            wait_until(lambda: client.exists("tasks05:blocked"))
            # Durable change whose notification was lost; reconcile owns recovery.
            with patch.object(sync, "ensure_sync", return_value=False):
                sync.mark_aggregate(user.pk, full_sweep=True)
            for j in range(3):
                reconcile_statistics_sync_task.apply_async()
                if seconds > 1 and j < 2:
                    time.sleep(60)
        measure(f"reconcile-backlog-{iteration}", backlog, [user.pk])
    def failure():
        cache.delete(sync._gate_key(users[-1].pk))
        client.set("tasks05:fail_once", "1")
        sync.mark_aggregate(users[-1].pk, full_sweep=True)
        wait_drain()
        assert StatisticsSyncState.objects.get(user_id=users[-1].pk).last_error
        # Actual safety-net cadence: the enqueue gate has expired by this tick.
        time.sleep(6)
        reconcile_statistics_sync_task.apply_async()
    measure("failure-and-retry", failure, ids)
    assert not StatisticsSyncState.objects.exclude(last_error="").exists()
    before = list(StatisticsSnapshot.objects.order_by("pk").values_list("user_id", "range_name", "generation"))
    def duplicate():
        client.set("tasks05:profile_next", "1")
        for _ in range(2):
            statistics_sync_task.apply_async(args=[users[-1].pk])
    result = measure("idempotency", duplicate, ids)
    assert not any(s["published"] for s in result["syncs"])
    assert before == list(StatisticsSnapshot.objects.order_by("pk").values_list("user_id", "range_name", "generation"))
    profile = cProfile.Profile()
    with patch.object(sync, "ensure_sync", return_value=False):
        profile.runcall(sync.reconcile)
    profile.dump_stats(str(OUT/f"{MODE}-reconcile.prof"))
    # Settle outstanding heavy ranges before measuring a genuinely quiet window.
    time.sleep(91)
    measure("settle", lambda: reconcile_statistics_sync_task.apply_async(), ids)
    idle_seconds = int(sys.argv[2]) if len(sys.argv)>2 else 1800
    def idle():
        deadline = time.monotonic()+idle_seconds
        ticks = 0
        while time.monotonic() < deadline:
            reconcile_statistics_sync_task.apply_async()
            ticks += 1
            (OUT/f"{MODE}-progress.json").write_text(json.dumps({"stage": "idle", "ticks": ticks,
                "elapsed_s": idle_seconds-max(0, deadline-time.monotonic())}))
            time.sleep(min(60, max(0, deadline-time.monotonic())))
    measure(f"idle-{idle_seconds}s", idle, ids)
    assert not StatisticsDirtyDay.objects.exists()
    assert all(s.generation == s.hot_synced_generation == s.heavy_synced_generation for s in StatisticsSyncState.objects.all())
    for user in users:
        payload = sync.load_snapshot(user.pk, "All Time")
        expected = Movie.objects.filter(user=user, status=Status.COMPLETED.value).count()
        completed = payload["data"]["summary_stats_by_type"]["all"]["completed"]
        assert completed == expected, (completed, expected)
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA quick_check")
        assert cursor.fetchall() == [("ok",)]
        cursor.execute("PRAGMA foreign_key_check")
        assert cursor.fetchall() == []
    (OUT/f"{MODE}-complete.json").write_text(json.dumps({"correctness": "converged, no dirty days, retry recovered, duplicates stable, SQLite integrity OK", "cgroup": cgroup()}))
finally:
    worker.terminate()
    try:
        worker.wait(timeout=15)
    except subprocess.TimeoutExpired:
        worker.kill()
        worker.wait()
    worker_log.close()
