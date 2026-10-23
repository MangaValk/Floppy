# TASKS-05 — Statistics reconciler enqueue pile-up

Verdict: **IMPROVED**. Checklist item can be closed for the measured backlog
behaviour. Machine-readable results: [`perf-results/tasks05/summary.json`](../../perf-results/tasks05/summary.json).
Full raw data and commands: [`perf-results/tasks05/README.md`](../../perf-results/tasks05/README.md).

## Problem: confirmed, with a corrected mechanism

The 60-second reconciler really does queue one Statistics sync per candidate user
per tick while the interactive worker is busy. The enqueue gate is **not** the
mechanism by itself: `STATISTICS_SYNC_ENQUEUE_GATE_SECONDS` defaults to 5 seconds,
so a 60-second tick would pass it even without `bypass_gate`. The missing piece is
a marker that spans a message's time waiting in the queue. `users_needing_sync()`
only excludes a user whose **lease is held**; a queued message has no lease until
it starts, so every tick sees the same unfinished work and publishes again.

Confirmed at `c875777edbc51d56984486100fe83e77566f1c5f`:

- `reconcile()` called `ensure_sync(..., bypass_gate=True)` at
  `src/app/statistics_sync.py:1466` (before the change).
- `ensure_sync()` skipped `cache.add(_gate_key(...))` for that path at
  `src/app/statistics_sync.py:375-417` (before the change).
- The self-follow-up used the same bypass at `src/app/statistics_sync.py:1381`.
- The 5-second gate at `src/app/statistics_sync.py:176-180` cannot bridge the
  60-second Beat tick.
- `_bootstrap_states()` still runs a cheap active-user query every tick. It is
  unchanged and was not a material cost in the idle window.

Observed behaviour: with a 125-second blocker and reconciliation at 0/60/120 s,
two candidate users produced **6** queued sync messages, **10** task executions,
and **4** executions that published no range. The duplicates were `done` rather
than `busy` in this concurrency-one harness because each ran after the blocker and
took the then-free lease; they still paid task wake-up, lease/state queries, Redis
commands and writes. With a genuinely concurrent delivery, the same duplicates
surface as `status=busy`.

## Change

`src/app/statistics_sync.py` now separates delivery tracking from the interactive
gate:

- `_pending_key(user_id)` (`:182`) marks a successfully published message.
- `ensure_sync(..., scheduled=True)` (`:375`) uses `cache.add` on that marker with
  the lease window, so the reconciler and self-follow-up publish once while a
  message waits. Ordinary marks keep the 5-second gate.
- `sync_task_body()` (`:1394`) deletes the marker when the task starts.
- The marker is refreshed after every successful publication; a broker failure
  deletes it, so the next tick retries.
- A lost-before-delivery message is still recovered when the marker expires after
  `STATISTICS_SYNC_LEASE_SECONDS` (default 300 s). This is the trade-off: recovery
  after a genuinely lost message can now take one lease window instead of one
  tick. Durable dirty state is unchanged either way.
- `docs/architecture/statistics-sync.md` documents the pending marker and the
  recovery window.

No schema, API, permission or provider changes. `cache.add`/`cache.set` are
backend-neutral, so SQLite and PostgreSQL both remain compatible; PostgreSQL
runtime performance was not measured.

## Dataset, environment and commands

- Host: Apple M1 Pro, 16 GiB, Darwin arm64; Linux Docker VM 10 CPUs.
- App container: 2 CPUs, 2 GiB, 256 pids, 4096 nofile.
- Python 3.12.15, Django 5.2.17, SQLite 3.53.4, Redis 8.10.1.
- Two users: 100 and 12,000 completed movies; 12,100 items/tracking/history rows.
- One real prefork interactive worker, concurrency/prefetch 1.
- Quiet and playback trials, warm/cold day cache, five measured runs after warmup.
- 125-second blocker with reconcile at 0/60/120 s, then five burst replays.
- Quiet 30-minute reconciler window, failure/retry, duplicate-delivery idempotency.
- Baseline and after source were the same `git archive HEAD`; only the patched
  `statistics_sync.py` differs.

```sh
python3 perf-results/tasks05/run.py baseline 1800
docker rm tasks05-baseline
python3 perf-results/tasks05/run.py after 1800
python3 perf-results/tasks05/analyse.py
```

The first baseline run was contaminated by two other Floppy benchmark containers
on the shared host and is kept under `perf-results/tasks05/contended-baseline/`.
The clean rerun is `baseline/`. The after phase ran with the same host containers
present (idle PostgreSQL and test Redis only). Raw host and container provenance
is in `*-launch.json` / `*-environment.json`.

## Baseline vs after

Lower is better. All values below are raw or medians of the retained readings.

| Metric | Baseline | After | Absolute | Change |
|---|---:|---:|---:|---:|
| 125 s blocker: sync messages | 6 | 2 | -4 | -66.7% |
| 125 s blocker: task executions | 10 | 6 | -4 | -40.0% |
| 125 s blocker: unproductive syncs | 4 | 0 | -4 | -100% |
| 125 s blocker: peak queue depth | 4 | 2 | -2 | -50.0% |
| 125 s blocker: enqueues/hour extrapolated | 164.9 | 55.0 | -109.9 | -66.7% |
| 125 s blocker: queue wait p50 | 5.352 s | 2.709 s | -2.643 s | -49.4% |
| 125 s blocker: DB write statements | 84 | 64 | -20 | -23.8% |
| 125 s blocker: Redis commands | 507 | 421 | -86 | -17.0% |
| Catch-up burst median: sync messages | 3 | 1 | -2 | -66.7% |
| Catch-up burst median: executions | 7 | 5 | -2 | -28.6% |
| Catch-up burst median: unproductive syncs | 2 | 0 | -2 | -100% |
| Catch-up burst median: DB writes | 54 | 44 | -10 | -18.5% |
| Catch-up burst median: Redis commands | 325 | 282 | -43 | -13.2% |
| Catch-up burst median: queue wait p95 | 5.087 s | 0.982 s | -4.104 s | -80.7% |
| Idle 30 min: sync messages / executions | 0 / 30 | 0 / 30 | 0 | unchanged |
| Idle 30 min: DB queries | 151 | 151 | 0 | unchanged |
| Backlog peak PSS | 385.3 MB | 385.5 MB | +0.2 MB | +0.05% |
| Backlog peak USS | 325.6 MB | 325.6 MB | ~0 | -0.01% |

Ordinary warm/cold quiet and playback trials report only 1 sync enqueue and the
same DB write count before and after; the change adds two Redis commands per
successful publication (set and delete the marker). Their wall/CPU/latency deltas
moved by tens of percent in both directions across identical-work baseline runs,
so they are **not** attributed to this change; the shared-host drift is documented
in `comparison.md`.

No regression was observed in user-facing latency or memory. Webhook delay in
the loaded trials did not increase; its measurements are retained in
`measurements.json` but are also subject to the same host drift.

## Correctness and tests

```sh
REDIS_URL=redis://127.0.0.1:6389/0 SECRET=test-only \
  scripts/test.sh app.tests.test_statistics_sync
```

- 65 tests passed on the changed source (`perf-results/tasks05/after-tests.log`).
- The baseline 62-test run passed before the new cases were added.
- New regression tests:
  - `test_reconcile_queues_once_while_a_message_waits_behind_the_worker`
  - `test_starting_the_task_clears_the_pending_marker`
  - `test_reconcile_retries_after_the_pending_window_expires`
- The existing dropped-message test now models the pending window expiring before
  the reconciler retries, rather than assuming an immediate bypass.
- Harness final checks passed in both clean phases: no dirty days, current/hot/
  heavy generations equal, All Time completion totals correct, duplicate
  deliveries publish no ranges, retry recovers, SQLite `quick_check` and
  `foreign_key_check` clean.

## Files changed

- `src/app/statistics_sync.py` — pending marker, scheduled enqueue path, cleanup.
- `src/app/tests/test_statistics_sync.py` — three regressions and updated
  dropped-message expectation.
- `docs/architecture/statistics-sync.md` — reconciler contract.
- `perf-results/tasks05/` — raw runs, analysis, summary and report.
- This document and the master-backlog checklist.

## Rollback

Revert the `statistics_sync.py` change (or set the pending marker path aside) and
delete the pending keys; the 60-second reconciler needs no data migration. The
only durable state is the existing `StatisticsSyncState` and dirty days, which are
unchanged. Redeploying the previous image restores the old over-enqueue behaviour
without cleanup.

## Follow-ups (separately scoped)

- `_bootstrap_states()` still runs every tick. It cost about five queries per idle
  tick in this fixture and did not affect the measured outcome; caching it for a
  few minutes would be a different, smaller change.
- If a lost-before-delivery message must be recovered faster than one lease
  window, expose the pending TTL as a setting or add a broker-aware liveness
  check. Do not shorten it below the queue-wait tail without re-measuring.
