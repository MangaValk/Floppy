# TASKS-04 — Statistics aggregation on the interactive worker

Verdict: **IMPROVED**. The ordinary Statistics sync no longer occupies the
single-concurrency interactive worker. Checklist item can be closed for the
measured scheduling behaviour. Machine-readable results:
[`perf-results/tasks04/comparison.json`](../../perf-results/tasks04/comparison.json).
Raw samples, commands and the rerunnable harness:
[`perf-results/tasks04/README.md`](../../perf-results/tasks04/README.md).

## Problem: confirmed for the interactive lane, with two corrected claims

Confirmed at `27b89e56a5a91548ebd4a84eba2fc5bce119fff4` (workload baseline) and
`e096793aa1f0f5eea06c2f9e9323ed287008d109` (before this change):

- `app.tasks.statistics_sync_task` was routed to `interactive` at
  `CELERY_TASK_PRIORITY_STATISTICS_SYNC = 1`
  (`src/config/settings.py:1805-1809`).
- The interactive worker runs one task at a time (`CELERY_WORKER_CONCURRENCY = 1`,
  prefetch 1). A priority-0 webhook queued while a sync is executing cannot run
  until the current task returns.
- The sync yields between day slices and ranges
  (`_check_deadline`, `_yield_if_interactive`, `_check_range_fits` in
  `src/app/statistics_sync.py`), but `_aggregate_range` / the aggregator cannot
  stop partway. The worst case is therefore one whole range after the budget.
- The same worker also hosted the full talent-fragment rebuild
  (`Refresh statistics talent fragment`).

Two parts of the original audit were **not** reproduced:

- A cold cost cache does not make the sync rebuild every range in one task. The
  deadline is still checked between ranges, so a cold run stops at the budget.
  `_check_range_fits` only adds a pre-start estimate; it is not the only guard.
- The observed cost of one All Time aggregate in this 10,000-play fixture is
  about 1–2.5 s, not multi-minute. The scheduling defect is independent of that
  magnitude: any range runs to completion once started.

## Change

- `src/config/settings.py`: ordinary `app.tasks.statistics_sync_task` runs on the
  background `celery` queue. `Refresh statistics talent fragment` moves there
  too. Priorities are unchanged.
- `src/app/statistics_sync.py`: `ensure_sync()` sends urgent requests — a manual
  Refresh and a range that has never been built — explicitly to `interactive`,
  because the user is waiting. Ordinary and scheduled syncs stay on the bulk
  lane. The reconciler and the cheap credits marker stay on `interactive`.
- No schema, API, permission, provider or data-shape change. The task body,
  lease fencing, dirty-day tokens, snapshots and correctness rules are untouched.

The minimal tier still runs one combined worker; there the two lanes share a
process and in-queue priority remains the only separation. The constrained and
standard tiers keep the dedicated interactive worker free for webhooks.

## Measured workload

- Native Apple M1 Pro, 10 logical CPUs, 16 GiB RAM; macOS 27.2 arm64, Python
  3.12.15, SQLite 3.53.4 WAL, Redis 8.8.0. No container quota.
- Disposable database and socket-only Redis. Two real Celery worker processes,
  threads pool, concurrency/prefetch 1: `interactive` and `celery`.
- Two users with 100 and 10,000 completed, scored movie rows across 3,650 days.
- Each operation requests a full sweep. Cold clears the application cache first;
  warm retains it. A loaded replay runs a priority-0 probe that changes today's
  score and marks today dirty. Five measured runs after one warmup per cell.
- A separate 30-minute quiet window calls the reconciler every 60 s.
- Exactly the same harness and fixture ran before and after; only the routing and
  `ensure_sync` queue override differ.

Commands:

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

## Result

Webhook-priority queue wait (p95, 5 runs per cell):

| Cell | Before | After | Change |
| --- | ---: | ---: | ---: |
| 100 plays, cold, loaded | 2.001 s | 0.003 s | −99.84% |
| 100 plays, warm, loaded | 1.997 s | 0.002 s | −99.92% |
| 10,000 plays, cold, loaded | 1.861 s | 0.003 s | −99.84% |
| 10,000 plays, warm, loaded | 4.508 s | 0.003 s | −99.94% |

The same merged single-worker topology (minimal tier) still measured p95
1.797–1.897 s at 10,000 plays, confirming that the improvement comes from
process separation, not from reduced sync work.

Steady-state idle (last 24 minutes of a 30-minute window): **0** sync executions
and **0** enqueues per hour before and after. The after window recorded two
trailing executions in its first three minutes; they were the settle-delayed
heavy ranges from the last loaded operation, already marked before the window.

## Side effects

- Loaded operations process the webhook earlier. That can invalidate a running
  sync and cause one extra hot-range continuation. At 10,000 plays this measured
  +3.1% (cold) / +0.6% (warm) sync CPU, +3.2% / +2.5% DB write statements, and
  +0.8% / +0.7% Redis commands. At 100 plays the relative effect is larger
  (+0.18 s and +16 statements per operation) because the extra continuation is a
  larger share of a small sync.
- Peak child RSS/USS during syncs was unchanged within run-to-run variation.
- Idle CPU moved from the interactive process to the background process; total
  idle sync work remained zero.
- No correctness regression: all 48 measured samples preserved the exact All Time
  play count, left zero dirty days and published 11 snapshots. Five snapshots
  intentionally trailed a simultaneous mark until the settle window (0 stale in
  every unloaded cell).

## Tests and scope

- 160 targeted Statistics/Celery tests and 89 Statistics view/startup tests
  passed against an isolated Redis. A full fast suite was also run.
- `test_background_sync_runs_on_the_bulk_lane_but_keeps_its_priority`,
  `test_forced_refresh_stays_on_the_interactive_lane` and
  `test_talent_fragment_rebuild_runs_on_the_bulk_lane` cover the routing.
- Not measured: production prefork worker contention, PostgreSQL, real Plex /
  Jellyfin / Stremio receivers, and a library large enough to make one range take
  minutes. The native run cannot report PSS or container peak memory.

## Rollback

Revert the routing and queue override. No data migration, cache key or published
payload changed, so a rollback takes effect on the next task publication; any
message already queued on `celery` still runs the same task body.
