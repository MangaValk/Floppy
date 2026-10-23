# TASKS-05 — Statistics reconciler pending-enqueue dedupe

Status: **IMPROVED**. The reconciler now publishes at most one pending sync per
user instead of one per 60-second tick while the interactive worker is busy.

Source: `c875777edbc51d56984486100fe83e77566f1c5f`. The measured change is
`src/app/statistics_sync.py` only. The baseline source is `git archive HEAD`
without that change; the after source is the same archive with the patch.
No production users, databases, Redis instances or external providers are used.
No issues or commits are created.

The first baseline run, taken while two other Floppy benchmark containers were
competing for the host, is retained under `contended-baseline/` and excluded from
the comparison. The `baseline/` files here are the clean rerun on the same host
state as `after/` (idle `tasks01-pg` and test Redis only).

## Reproduction

Commands were invoked through `rtk proxy`. Docker requires sandbox escalation.
Exact Docker arguments, image identity, host details, other containers and source
diffs are retained in `baseline-launch.json` and `after-launch.json`.

```sh
mkdir -p /tmp/floppy-tasks05-source /tmp/floppy-tasks05-after
git archive HEAD | tar -x -C /tmp/floppy-tasks05-source
git archive HEAD | tar -x -C /tmp/floppy-tasks05-after
cp src/app/statistics_sync.py /tmp/floppy-tasks05-after/src/app/statistics_sync.py
docker network create --internal tasks05-net
docker run -d --name tasks05-redis --network tasks05-net redis:8-alpine redis-server --save '' --appendonly no
python3 perf-results/tasks05/run.py baseline 1800
docker rm tasks05-baseline
python3 perf-results/tasks05/run.py after 1800
python3 perf-results/tasks05/analyse.py
```

The launcher flushes only the dedicated `tasks05-redis` instance between phases.
Do not launch phases concurrently. The containers have no published ports and
their network is internal. Other benchmark/application containers on the host
are untouched. This is a shared host, not an isolated idle machine.

## Environment and workload

Host: Apple M1 Pro, 16 GiB RAM, Darwin arm64. Linux Docker VM has 10 CPUs.
Application container: 2 CPUs, 2 GiB memory without additional swap allowance,
256 processes, 4096 file descriptors. Python 3.12.15, Django 5.2.17,
SQLite 3.53.4, Redis 8.10.1. See environment JSON for actual readings.
The existing `floppy:start01-baseline` image has the exact source SHA and locked
production dependencies; source is overridden read-only with the archive.

The disposable SQLite schema is built from current models (`MIGRATION_MODULES`
disabled for the six application/auth/contenttypes apps), with remaining normal
migrations applied. This is not an upgrade/migration benchmark. Persistent SQLite
uses WAL and a 30-second timeout with IMMEDIATE transactions. Redis starts empty.
Cache, broker, result backend and instrumentation use databases 1, 0, 2 and 3.

Two synthetic users have 100 and 12,000 completed manual movies respectively,
with one actual historical row per movie, dated over seven days. No reading,
provider or integration account is present. The library has 12,100 catalog,
tracking and history rows. Both phases seed from the same recipe.

One prefork Celery interactive worker, concurrency/prefetch one, consumes the real
task routes and priorities. Beat publications are driven by the harness; Beat
itself and the background consumer are absent. A real 125-second blocking task
holds the worker while three reconciliation messages arrive at 0, 60 and 120
seconds. Five subsequent repetitions replay the resulting three-message catch-up
burst behind a one-second blocker; these compare catch-up behavior, not five
independent two-minute steady-state observations.

For each size, warm/cold day-cache and quiet/playback combination, one warmup is
followed by five measured trials. A mark invalidates today's statistics; loaded
trials concurrently queue three priority-zero webhook tasks. Only Jellyfin parsing
and provider credits/genre backfill dispatch are mocked. The webhook task,
tracking/history writes, model signals, dirty marking, statistics sync, DB leases,
snapshot publication and broker remain real. Normal history/Discover background
publications are recorded separately and not consumed; no provider fetch occurs.
Cold means deleting seven day-cache payloads while retaining the durable sweep
epoch. It does not mean flushing the OS, all caches or restarting the worker.
The initial full sweep is a separate excluded cold warmup.

A controlled aggregate exception verifies durable failure and reconciliation
recovery. Duplicate deliveries must publish no ranges and leave snapshot
generations unchanged. After a real 91-second heavy settling interval, a real
1,800-second quiet window publishes reconciliation every 60 seconds. Final
checks require no dirty days, equal current/hot/heavy generations, expected All
Time completion totals, and SQLite quick/foreign-key checks.

## Result

`summary.json` holds the machine-readable comparison; `measurements.json`,
`*.jsonl` and `comparison.md` retain every raw reading.

| Metric | Baseline | After | Delta |
|---|---:|---:|---:|
| Sync messages queued behind the 125 s blocker (two users, three ticks) | 6 | 2 | -4 (-66.7%) |
| Task executions in that window | 10 | 6 | -4 (-40.0%) |
| Unproductive sync executions (published no range) | 4 | 0 | -4 (-100%) |
| Peak interactive queue depth | 4 | 2 | -2 |
| Enqueues per hour, extrapolated from the 131 s window | 164.9 | 55.0 | -66.7% |
| DB write statements | 84 | 64 | -20 (-23.8%) |
| Redis commands (parent + task bodies) | 507 | 421 | -86 (-17.0%) |
| Queue wait p50 | 5.352 s | 2.709 s | -2.643 s (-49.4%) |
| Catch-up burst: sync messages / executions / unproductive | 3 / 7 / 2 | 1 / 5 / 0 | -66.7% / -28.6% / -100% |
| Catch-up burst: queue wait p95 | 5.087 s | 0.982 s | -4.104 s (-80.7%) |
| Quiet 30-minute window: sync messages / executions | 0 / 30 | 0 / 30 | unchanged |
| Peak PSS / USS, backlog | 385.3 MB / 325.6 MB | 385.5 MB / 325.6 MB | +0.05% / -0.01% |

The duplicate messages were not `busy` in this harness: concurrency one lets
each run after the blocker and acquire the free lease, then publish nothing.
They still paid the task wake-up, lease/state queries, Redis commands and writes.
A real concurrent worker can also observe the `busy` status.

Wall/CPU/latency deltas on ordinary sync trials are **not attributable** to this
change. The two phases ran about an hour apart on a shared Mac; identical-work
trials moved by tens of percent between the two baseline runs. The deterministic
enqueue/execution/statement/Redis counts and the target backlog phase are the
evidence. No ordinary trial shows a higher enqueue count, DB write count or
Redis count except the two extra commands that set and delete the new pending
marker.

## Measurement definitions and limits

`*.jsonl` retains per-operation task publications/completions, task CPU/runtime,
queue waits, SQL statement counts, Redis commands, queue-priority samples and
process/cgroup memory. `*-environment.json` and `*-launch.json` retain provenance.
Celery acknowledges early: drain detection matches publication and completion
counts as well as broker state. Queue sampling uses an atomic Redis Lua script
with TYPE and LLEN/ZCARD for all ten interactive priority keys.

PSS/USS are sums of the harness, worker parent and child sampled every 200 ms,
or five seconds during idle; short peaks may be missed. Container memory.peak
is a cumulative cgroup high-water mark including file cache, not a reset per
trial. Cgroup CPU includes harness/sampler/worker; Redis server CPU is separate.
DB writes are SQL write statements, not physical storage writes. Cache eviction
and durable state behavior remain those of the implementation.

The global Redis command delta includes monitoring. Instrumented parent/task-body
commands exclude monitoring connections but do not include worker-main broker
polling; pipelines include their commands and transaction delimiters. Both raw
counts are supplied. Instrumentation adds overhead equally in both phases.
Queue wait is publication-to-prerun; webhook completion adds runtime. This is
queue responsiveness, not an HTTP latency or end-to-end player benchmark.

Per-hour rates outside the actual idle window are extrapolated throughput rates,
not claims about a continuously loaded hour. Small-sample empirical p95 values
are observations, not stable tail estimates; raw waits are retained. Shared-host
load and cgroup throttling must be considered before interpreting CPU/latency
deltas. SQLite is measured; PostgreSQL compatibility requires targeted code/test
review, and PostgreSQL performance is not measured.

`*-duplicate.prof` attributes the no-op delivery path; `*-reconcile.prof`
attributes reconciliation with publication disabled. The analysis script emits
readable top cumulative frames and numeric comparisons. The contended first run
and the pre-baseline queue-sampling race are retained under `contended-baseline/`
and `rejected-*` and are excluded from comparisons.

## Tests

`REDIS_URL=redis://127.0.0.1:6389/0 SECRET=test-only scripts/test.sh app.tests.test_statistics_sync`

65 tests passed on the changed source (`after-tests.log`). Three new regression
tests cover one enqueue while a message waits, marker cleanup at task start, and
retry after the pending window expires. The original 62-test baseline run is in
`contended-baseline/baseline-tests.log`; the same 62 plus 3 new pass after.
