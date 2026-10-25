# TASKS-04 — Statistics sync lane isolation

Status: **IMPROVED**. Ordinary Statistics syncs moved from the interactive
worker to the background `celery` worker; urgent manual/first-build requests keep
the interactive lane. See
[`docs/plans/TASKS-04-statistics-lane-isolation.md`](../../docs/plans/TASKS-04-statistics-lane-isolation.md)
for the decision record.

## Files

| File | Contents |
| --- | --- |
| `measure.py` | Rerunnable two-process lane harness (fixture, workload, idle window). |
| `bench_app.py` | Benchmark task registry and worker-side instrumentation. |
| `bench_settings.py` | Disposable SQLite/Redis settings shared by driver and workers. |
| `baseline-lanes.json` | Before samples, before the routing change (`e096793aa`). |
| `after-lanes.json` | After samples, same workload (`e096793aa` + routing). |
| `after-merged.json` | After routing on one combined worker (minimal tier). |
| `comparison.json` | Machine-readable before/after deltas. |
| `comparison.md` | Readable before/after table. |
| `analyse.py` | Produces `comparison.json` / `comparison.md`. |
| `baseline.json`, `REPORT.md`, `validation.txt` | Earlier single-worker baseline retained for provenance. |

## Environment

Apple M1 Pro, 10 logical CPUs, 16 GiB RAM; macOS 27.2 arm64, Python 3.12.15,
SQLite 3.53.4 WAL, Redis 8.8.0. Native host, no container CPU/memory quota. PSS
and container peak memory are unavailable; null is not zero.

Two real Celery worker processes, threads pool, concurrency and prefetch 1. The
separate topology runs `interactive` and `celery`; the merged topology runs one
worker consuming `celery,interactive`.

Fixture: users with 100 and 10,000 completed, scored movies, one synthetic item
per movie, 100-minute runtime, dates across 3,650 days, no credits/people. A
disposable SQLite schema is built from current models (`syncdb`, not a migration
replay) and a socket-only Redis is used. No production database, broker, user or
provider endpoint is touched.

Protocol: each cell requests a full sweep. Cold flushes the application cache;
warm retains it. Loaded replays a priority-0 database write that changes today's
score and marks today dirty once the sync task has started. Five measured runs
after one warmup. A separate 1,800-second quiet window calls the reconciler every
60 seconds.

## Commands

```sh
SECRET=test-only uv run --no-sync python perf-results/tasks04/measure.py \
  --output perf-results/tasks04/baseline-lanes.json --runs 5 --idle-seconds 1800
SECRET=test-only uv run --no-sync python perf-results/tasks04/measure.py \
  --output perf-results/tasks04/after-lanes.json --runs 5 --idle-seconds 1800
SECRET=test-only uv run --no-sync python perf-results/tasks04/measure.py \
  --output perf-results/tasks04/after-merged.json --runs 3 --idle-seconds 0 --lanes merged
python3 perf-results/tasks04/analyse.py \
  --baseline perf-results/tasks04/baseline-lanes.json \
  --after perf-results/tasks04/after-lanes.json \
  --markdown perf-results/tasks04/comparison.md \
  --json perf-results/tasks04/comparison.json
```

Workers are launched as separate processes by `measure.py`; no external worker
needs to be running. Each run uses a fresh temporary directory and Redis socket.

## Headline raw measurements

Webhook-priority probe queue wait p95 (5 samples per cell, warmup excluded):

| Cell | Baseline | After | Delta |
| --- | ---: | ---: | ---: |
| 100 cold loaded | 2.0015 s | 0.0032 s | −99.84% |
| 100 warm loaded | 1.9974 s | 0.0016 s | −99.92% |
| 10,000 cold loaded | 1.8610 s | 0.0030 s | −99.84% |
| 10,000 warm loaded | 4.5075 s | 0.0026 s | −99.94% |

Merged topology after routing, 10,000 plays loaded: p95 1.797 s (cold) and
0.684 s (warm), i.e. the original blocking remains when one worker consumes both
queues. This is the evidence for keeping the interactive worker separate on
constrained/standard hosts.

Operation wall time (mean, includes polling and worker control):

| Cell | Baseline | After | Delta |
| --- | ---: | ---: | ---: |
| 100 cold loaded | 4.78 s | 1.93 s | −59.7% |
| 100 warm loaded | 4.81 s | 1.99 s | −58.6% |
| 10,000 cold loaded | 9.59 s | 6.68 s | −30.3% |
| 10,000 warm loaded | 8.20 s | 6.07 s | −26.0% |

Sync task CPU totals and writes moved slightly because the probe now lands while
the bulk sync is running and can invalidate it once:

| Cell | Sync CPU total | DB write statements | Redis commands |
| --- | ---: | ---: | ---: |
| 10,000 cold loaded | 27.47 → 28.32 s (+3.1%) | 2,495 → 2,575 (+3.2%) | 59,120 → 59,613 (+0.8%) |
| 10,000 warm loaded | 25.45 → 25.60 s (+0.6%) | 2,512 → 2,575 (+2.5%) | 59,043 → 59,479 (+0.7%) |
| 10,000 cold idle | 27.55 → 26.45 s (−4.0%) | 2,460 → 2,460 (0%) | 58,856 → 58,838 (−0.03%) |
| 10,000 warm idle | 25.20 → 24.04 s (−4.6%) | 2,460 → 2,460 (0%) | 58,723 → 58,705 (−0.03%) |

Idle: before and after both settle to zero sync executions and zero enqueues per
hour after the trailing settle window. The after run recorded two trailing
executions in its first three minutes (already-marked heavy ranges from the last
loaded operation); the last 24 minutes had none.

Peak task RSS ranged 92–131 MB and USS 73–106 MB in both runs, with no systematic
change. Correctness: every sample preserved the exact All Time play count, zero
dirty days and 11 snapshots. Five snapshots intentionally trailed a simultaneous
mark in loaded cells until the settle window; unloaded cells had zero stale
snapshots.

## Interpretation and limitations

- The measurement isolates lane ownership. It does not claim fewer range
  aggregate CPU-seconds; it removes that work from the webhook lane.
- The loaded probe is deliberately synchronized to the start of the sync, so the
  after run exercises the real case where a webhook lands during a sync. That is
  why the after run does one extra hot-range continuation in some cells.
- Native threads-pool workers, not production prefork children or a constrained
  container. PostgreSQL, container PSS and real provider webhooks were not
  measured.
- The 10,000-play All Time aggregate costs ~1–2.5 s here; on a much larger library
  the absolute queue-wait saving grows with the aggregate, while the percentage
  improvement stays bounded by the current wait.
