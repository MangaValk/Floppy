# Deterministic benchmark fixtures (BENCH-01)

From the repository root, with locked development dependencies installed:

```bash
uv sync --locked
uv run --no-sync python scripts/benchmark_fixtures.py --output /tmp/floppy-bench01 --profile
```

The output directory must not already exist. This runs **two fresh processes for
each of 1,000, 10,000 and 50,000 tracking rows**, with seed `1729`, one warm-up and
five measured probes per workload. Use an otherwise idle machine. No Redis,
Celery worker, provider credentials, local database copy or running server is
needed. The harness overrides the configured database, cache and broker before
Django starts, installs the existing offline network guard, and creates its own
SQLite database. It never seeds, flushes or migrates the application database.

For a quick check or a larger dataset:

```bash
uv run --no-sync python scripts/benchmark_fixtures.py --sizes 1000 --output /tmp/floppy-bench-small
uv run --no-sync python scripts/benchmark_fixtures.py --sizes 100000 --seed 1729 --repeats 2 --runs 5 --output /tmp/floppy-bench-large
```

Sizes must be multiples of ten. `--keep-database` retains each disposable
`dataset.sqlite3`; otherwise it is deleted after export. Deleting the output
directory disposes of the run. Fixtures contain known synthetic integration
tokens and unusable passwords: **never load them into a production database**.
No real titles, accounts, emails, provider identifiers, secrets or history are
copied. Machine receipts omit hostname and environment values; review your
chosen output path in the recorded command before sharing the report.

## Data contract

Size means the total number of user tracking rows, excluding supporting items,
episode plays, audit history and collection rows. Each ten-row block contains a
TV tracker, its season, two movies, a book, game, music track, podcast episode,
anime and manga. Blocks rotate across three users; all five statuses are used.
All dates derive from `2025-01-01T00:00:00Z`. A local seeded PRNG supplies ratings
and activity dates; no clock or global random state supplies fixture content.

Each show has twelve episode items and two completed plays per episode. Every
tracking row and episode play has two audit revisions. Music links to an artist,
album and track; podcasts link to a show and episode catalogue. Half the trackers
link to completed synthetic import runs with consistent created counts. Four
collection copies per block reference the owning user's select custom field.

At 50k this means 50k trackers, 110k items, 120k episode plays, 340k audit
revisions and 20k collection copies. These are **persisted import outcomes**,
created through bulk writes that bypass save hooks, providers and task dispatch;
they do not measure importer parsing, provider matching, replays or scheduling.
Audit revisions deliberately include an initial in-progress state. TV/season
activity derives from child episodes, including when the parent has a held
status. This is a synthetic workload, not a model of every real library.

## Output and interpretation

- `report.json`: schema version, Git SHA, generator/lockfile SHA-256 hashes,
  runtime versions, machine limits, comparisons and all raw samples.
- `report.md`: readable checksum and timing/variance tables with limitations.
- `<size>-<repeat>/fixture.json.gz`: deterministic, dependency-ordered Django
  JSON fixture; gzip header has no timestamp or filename.
- `<size>-<repeat>/sample.json`: counts, fixture checksum/bytes, schema creation,
  generation/export costs, raw workload samples and instrumentation overhead.

Checksums must agree between repeat processes; disagreement fails the command.
Expect exact compressed bytes for the same seed, size, source, Python, Django,
SQLite and zlib versions. Schema/runtime changes may change checksums. There is
no timing pass/fail threshold: the report includes min/max and population CV
(standard deviation / mean). Two process repetitions establish repeatability,
not statistical confidence; increase `--repeats` for performance experiments.

Probes reuse the production library-query engine for movie, TV, music and podcast
pages (24 items), plus direct episode-audit and collection queries. They are warm,
in-process data probes, **not HTTP surface measurements**. Continue using
`benchmark_perf`, `scripts/bench.sh` and constrained/container benchmarks for
their existing purposes. This fixture work does not replace those harnesses.

Wall time and process CPU are collected without SQL capture or tracemalloc in
normal trials. Before/after RSS/USS/PSS snapshots are outside the operation timer;
null means unavailable. macOS usually has no PSS and may deny USS. `psutil` is
optional; without it all three snapshots are null. Lifetime peak RSS comes from
`getrusage`, not a phase peak; snapshots can miss transient allocation spikes.
Memory covers only the worker process, not a database server or descendants.
Schema, generation and export are separate phases; Django startup is excluded.

`--profile` adds one separate SQL-capture/tracemalloc trial per workload and
reports its wall-time ratio to the normal median. It can be materially slower;
the ratio is a noisy single-sample cost estimate. A 50-call memory-probe
calibration records collection cost separately. No profiler is installed in any
production request path. Instrumentation alone establishes no production speedup.
Host CPU/RAM, cgroup-v2 limits (where available), and CPU/address-space rlimits
are reported; null is unavailable and `-1` is unlimited. No resource caps are
imposed by the harness. macOS may represent unlimited rlimits with a large
`RLIM_INFINITY` sentinel instead of `-1`. Record external/container restrictions
separately.

## Portable restore

The fixture is standard Django `loaddata` JSON, with explicit primary keys and
foreign keys. Restore only into an **empty disposable database at the same model
schema**. It includes all synthetic dependencies, but not site configuration,
credentials, auth permissions or statistics snapshots from another instance.

For SQLite, retain the generated database with `--keep-database`, or exercise
`loaddata` using an explicitly isolated settings module. For example:

```bash
mkdir /tmp/floppy-bench-restore
cat > /tmp/floppy-bench-restore/bench_restore_settings.py <<'PY'
from config.test_settings import *
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "/tmp/floppy-bench-restore/db.sqlite3"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CELERY_TASK_ALWAYS_EAGER = False
CELERY_BROKER_URL = "memory://"
PY
SECRET=test-only PYTHONPATH=src:/tmp/floppy-bench-restore uv run --no-sync python src/manage.py migrate --settings=bench_restore_settings
SECRET=test-only PYTHONPATH=src:/tmp/floppy-bench-restore uv run --no-sync python src/manage.py loaddata /tmp/floppy-bench01/1000-1/fixture.json.gz --settings=bench_restore_settings
```

For PostgreSQL, create a new disposable database and change **only the explicit
`DATABASES` assignment in that temporary module**, for example:

```python
DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "floppy_bench01_disposable", "HOST": "127.0.0.1", "PORT": "5432", "USER": "benchmark", "PASSWORD": ""}}
```

Use that database's own credentials, then run the same migrate/loaddata commands.
Do not use the application's default database or load into a populated database:
explicit PKs and custom-field keys assume an empty target. Django resets sequences
on fixture load. A backend restore should preserve the field data/counts; a
compressed-byte checksum across different backends is not promised. SQLite
export/reload is covered by tests. A 1k fixture was also restored to PostgreSQL
16.13 with matching counts, all serialized fields, re-export checksum and verified
sequence reset (current-model schema, not migration replay). Larger PostgreSQL
restores remain unmeasured. Generation itself deliberately stays SQLite-only.

## Validation

```bash
SECRET=test-only FLOPPY_TEST_FAST_DB=1 scripts/test.sh app.tests.test_benchmark_fixtures --parallel 1
SECRET=test-only FLOPPY_TEST_FAST_DB=1 LIBRARY_BENCHMARK_OUTPUT=/tmp/library-baseline.json scripts/test.sh app.tests.test_library_scaling_benchmark --tag slow --parallel 1
uv run --no-sync ruff check src
uv run --no-sync ruff check scripts/benchmark_fixtures.py
```

`FLOPPY_TEST_FAST_DB=1` builds schema from models and skips migration replay. This
work changes no models or migrations. Tests check sizes and relationships,
status/import/collection coverage, no provider/task dispatch, export/reload byte
equality, existing-data refusal and memory-access-denied behavior. The default
six fresh-process runs provide the independent repeat-generation check. Keep
machine-specific receipts outside the index; the command never commits them.
