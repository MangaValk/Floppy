# ruff: noqa: INP001, T201, PLR2004 -- standalone benchmark with explicit dimensions
"""Generate isolated BENCH-01 datasets and JSON/Markdown measurement receipts."""

import argparse
import gzip
import hashlib
import importlib.metadata
import io
import json
import os
import platform
import resource
import sqlite3
import statistics
import subprocess
import sys
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def memory():
    """Return process bytes, explicitly identifying unsupported metrics."""
    result = {"rss": None, "uss": None, "pss": None}
    try:
        import psutil
    except ImportError:
        return result
    process = psutil.Process()
    try:
        result["rss"] = process.memory_info().rss
        info = process.memory_full_info()
        result.update({key: getattr(info, key, None) for key in result})
    except (psutil.Error, OSError):
        pass  # Preserve RSS when the OS refuses USS/PSS access.
    return result


def measure(operation):
    """Measure process CPU and wall time; snapshots sit outside timed work."""
    before = memory()
    cpu, wall = time.process_time(), time.perf_counter()
    value = operation()
    elapsed = {"wall_s": time.perf_counter() - wall, "cpu_s": time.process_time() - cpu}
    elapsed.update(memory_before_bytes=before, memory_after_bytes=memory())
    return value, elapsed


def export_fixture(models, target):
    """Stream dependency-ordered Django JSON; gzip header excludes date/path."""
    from django.core import serializers

    def rows():
        for model in models:
            yield from model.objects.order_by("pk").iterator(chunk_size=500)

    with (
        target.open("wb") as raw,
        gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw,
            mtime=0,
        ) as compressed,
        io.TextIOWrapper(compressed, encoding="utf-8") as stream,
    ):
        serializers.serialize("json", rows(), stream=stream, ensure_ascii=True)
    digest = hashlib.sha256()
    with target.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def worker(options):
    """Use a fresh SQLite file, never the configured application database."""
    directory = options.output
    directory.mkdir(parents=True, exist_ok=False)
    database = directory / "dataset.sqlite3"
    # Set these before importing any application settings. Override .env values
    # via Django settings as well; no live database/cache/broker is opened.
    os.environ.update(
        SECRET="bench-only-disabled",  # noqa: S106 -- synthetic benchmark key
        DJANGO_SETTINGS_MODULE="config.test_settings",
        FLOPPY_DB_PATH=str(database),
        FLOPPY_TEST_ALLOW_NETWORK="0",
    )
    sys.path.insert(0, str(ROOT / "src"))
    import django
    from django.conf import settings

    settings.DATABASES = {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(database)}
    }
    settings.DEBUG = False
    settings.CELERY_TASK_ALWAYS_EAGER = False
    settings.CELERY_BROKER_URL = "memory://"
    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }
    django.setup()
    from django.apps import apps
    from django.core.management import call_command
    from django.db import connection

    from app.benchmark_data import TRACKERS, build_dataset
    from app.library_query import LibraryQuery, LibraryQueryExecutor
    from app.models import CollectionEntry, Episode
    from users.models import User

    # Schema-only setup, not an upgrade test. No seed/data migration side effects.
    settings.MIGRATION_MODULES = dict.fromkeys(
        app.label for app in apps.get_app_configs()
    )
    _, schema = measure(lambda: call_command("migrate", run_syncdb=True, verbosity=0))
    models, generation = measure(lambda: build_dataset(options.size, options.seed))
    checksum, export = measure(
        lambda: export_fixture(models, directory / "fixture.json.gz")
    )
    user = User.objects.get(username="bench-user-1")
    workloads = {
        media_type: lambda media_type=media_type: LibraryQueryExecutor(
            user,
            LibraryQuery(media_types=(media_type,)),
        ).page(0, 24)
        for media_type in ("movie", "tv", "music", "podcast")
    }
    workloads["episode_history"] = lambda: list(
        Episode.history.filter(history_user=user).order_by(
            "-history_date", "-history_id"
        )[:24],
    )
    workloads["collection"] = lambda: list(
        CollectionEntry.objects.filter(user=user)
        .select_related("item")
        .order_by("pk")[:24],
    )
    samples = {}
    for name, operation in workloads.items():
        operation()  # unmeasured warm-up; no HTTP/provider calls
        samples[name] = [measure(operation)[1] for _ in range(options.runs)]
    profile = {}
    if options.profile:
        import tracemalloc

        from django.test.utils import CaptureQueriesContext

        for name, operation in workloads.items():
            with CaptureQueriesContext(connection) as queries:
                tracemalloc.start()
                try:
                    _, timing = measure(operation)
                    _, peak = tracemalloc.get_traced_memory()
                finally:
                    tracemalloc.stop()
            normal = statistics.median(row["wall_s"] for row in samples[name])
            profile[name] = {
                **timing,
                "queries": len(queries),
                "python_peak_bytes": peak,
                "wall_ratio_to_unprofiled_median": timing["wall_s"] / normal,
            }
    cpu, wall = time.process_time(), time.perf_counter()
    for _ in range(50):
        memory()
    probe = {
        "calls": 50,
        "wall_s": time.perf_counter() - wall,
        "cpu_s": time.process_time() - cpu,
    }
    counts = {model._meta.label_lower: model.objects.count() for model in models}
    tracked = sum(counts[model._meta.label_lower] for model in dict.fromkeys(TRACKERS))
    if tracked != options.size:
        msg = f"Expected {options.size} tracking rows, got {tracked}"
        raise RuntimeError(msg)
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    receipt = {
        "schema_version": 1,
        "seed": options.seed,
        "size": options.size,
        "fixture_sha256": checksum,
        "counts": counts,
        "schema": schema,
        "generation": generation,
        "export": export,
        "samples": samples,
        "profile": profile,
        "memory_probe_overhead": probe,
        "process_peak_rss_bytes": peak * (1 if sys.platform == "darwin" else 1024),
        "fixture_bytes": (directory / "fixture.json.gz").stat().st_size,
        "sqlite_bytes": database.stat().st_size,
    }
    connection.close()
    if not options.keep_database:
        database.unlink()
    (directory / "sample.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    )


def machine():
    """Record limits without usernames, hostnames, paths or environment secrets."""
    limits = {}
    for name in ("cpu.max", "memory.max", "cpuset.cpus.effective"):
        path = Path("/sys/fs/cgroup") / name
        limits[name] = path.read_text().strip() if path.exists() else None
    try:
        import psutil

        ram = psutil.virtual_memory().total
    except ImportError:
        ram = None
    return {
        "os": platform.system(),
        "release": platform.release(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "django": importlib.metadata.version("django"),
        "sqlite": sqlite3.sqlite_version,
        "zlib": zlib.ZLIB_RUNTIME_VERSION,
        "logical_cpus": os.cpu_count(),
        "ram_bytes": ram,
        "cgroup_v2": limits,
        "rlimit_cpu": resource.getrlimit(resource.RLIMIT_CPU),
        "rlimit_address_space": resource.getrlimit(resource.RLIMIT_AS),
    }


def report(options, receipts):
    """Write raw samples plus a readable comparison with explicit variance."""
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],  # noqa: S607 -- fixed local Git invocation
        cwd=ROOT,
        text=True,
    ).strip()
    notes = [
        "Synthetic persisted import outcomes; no real user data, provider calls or importer throughput.",
        "Warm in-process library/history/collection probes, not HTTP, Celery, Redis or deployment benchmarks.",
        "CPU is this Python process only. Memory is before/after snapshots, not sampled peaks; RSS peak is process lifetime.",
        "Null PSS/USS/RSS means unavailable (OS support, psutil absent or access denied). PSS is normally unavailable on macOS.",
        "Schema built from current models, not migrations. Portable fixture requires the same model schema; load only into an empty disposable DB.",
        "Determinism applies to fixture bytes within the same Python/Django/zlib versions; timings and memory vary with machine/cache/load.",
        "Memory probe collection is outside operation timers; profile ratios include SQL capture and tracemalloc overhead and are noisy single samples.",
        "No production instrumentation or speedup. Unprofiled samples are the instrumentation baseline; profiling is opt-in.",
        "cgroup null means unavailable; rlimit -1 means unlimited. Host RAM/CPU can exceed container allocation.",
    ]
    comparisons, lines = (
        [],
        [
            "# BENCH-01 deterministic fixtures",
            "",
            f"Commit: `{commit}`",
            "",
            "| Size | SHA-256 equal | Generation wall s (min-max) |",
            "| --- | --- | --- |",
        ],
    )
    for size in options.sizes:
        group = [row for row in receipts if row["size"] == size]
        equal = len({row["fixture_sha256"] for row in group}) == 1
        if not equal:
            msg = f"Fixture checksum mismatch for size {size}"
            raise RuntimeError(msg)
        walls = [row["generation"]["wall_s"] for row in group]
        comparison = {
            "size": size,
            "checksums_equal": equal,
            "generation_wall_min_s": min(walls),
            "generation_wall_max_s": max(walls),
            "generation_wall_cv_percent": statistics.pstdev(walls)
            / statistics.mean(walls)
            * 100,
            "workloads": {},
        }
        lines.append(f"| {size} | {equal} | {min(walls):.3f}-{max(walls):.3f} |")
        for name in group[0]["samples"]:
            values = [
                sample["wall_s"] for row in group for sample in row["samples"][name]
            ]
            comparison["workloads"][name] = {
                "n": len(values),
                "median_wall_s": statistics.median(values),
                "min_wall_s": min(values),
                "max_wall_s": max(values),
                "cv_percent": statistics.pstdev(values) / statistics.mean(values) * 100,
            }
        comparisons.append(comparison)
    payload = {
        "schema_version": 1,
        "commit": commit,
        "source_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "scripts/benchmark_fixtures.py",
                "src/app/benchmark_data.py",
                "uv.lock",
            )
        },
        "machine": machine(),
        "command": ["python", "scripts/benchmark_fixtures.py", *sys.argv[1:]],
        "notes": notes,
        "comparisons": comparisons,
        "executions": receipts,
    }
    (options.output / "report.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    lines += [
        "",
        "| Size / workload | Samples | Median wall ms | Min-max ms | CV % |",
        "| --- | --- | --- | --- | --- |",
    ]
    for comparison in comparisons:
        for name, values in comparison["workloads"].items():
            lines.append(
                f"| {comparison['size']} / {name} | {values['n']} | "
                f"{values['median_wall_s'] * 1000:.3f} | "
                f"{values['min_wall_s'] * 1000:.3f}-{values['max_wall_s'] * 1000:.3f} | "
                f"{values['cv_percent']:.1f} |"
            )
    lines += [
        "",
        "Machine and limits: `" + json.dumps(payload["machine"], sort_keys=True) + "`",
        "",
    ]
    lines += [f"- {note}" for note in notes]
    lines += [
        "",
        "Raw CPU/wall/memory samples, counts, checksums and overhead: `report.json` and each `sample.json`.",
    ]
    (options.output / "report.md").write_text("\n".join(lines) + "\n")


def main():
    """Run every size twice in fresh processes and refuse existing output paths."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sizes", type=int, nargs="+", default=[1000, 10000, 50000])
    parser.add_argument("--seed", type=int, default=1729)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--keep-database", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--size", type=int, help=argparse.SUPPRESS)
    options = parser.parse_args()
    options.output = options.output.resolve()
    if (
        options.repeats < 2
        or options.runs < 2
        or any(size < 10 or size % 10 for size in options.sizes)
    ):
        parser.error("Use repeats/runs >= 2 and sizes >= 10 divisible by 10")
    if options.worker:
        worker(options)
        return
    options.output.mkdir(parents=True, exist_ok=False)
    receipts = []
    for size in options.sizes:
        for repeat in range(options.repeats):
            directory = options.output / f"{size}-{repeat + 1}"
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--worker",
                "--size",
                str(size),
                "--seed",
                str(options.seed),
                "--runs",
                str(options.runs),
                "--output",
                str(directory),
            ]
            command += [
                flag
                for flag, enabled in (
                    ("--profile", options.profile),
                    ("--keep-database", options.keep_database),
                )
                if enabled
            ]
            subprocess.run(command, cwd=ROOT, check=True)  # noqa: S603
            receipts.append(json.loads((directory / "sample.json").read_text()))
            print(f"Finished size={size} repeat={repeat + 1}", flush=True)
    report(options, receipts)
    print(f"Reports: {options.output / 'report.json'} and report.md")


if __name__ == "__main__":
    main()
