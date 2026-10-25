# TASKS-04A — Celery process topology and idle resident memory

Verdict: **IMPROVED** for steady-state and peak private memory, with no worker
churn and no latency regression. Machine-readable results:
[`perf-results/tasks04a/memory.json`](../../perf-results/tasks04a/memory.json).
Raw runs and commands: [`perf-results/tasks04a/README.md`](../../perf-results/tasks04a/README.md).

## Problem: confirmed

At `fcccc54a2` (after TASKS-04), `_freeze_parent_image` in
`src/config/celery.py` connected only to `worker_ready`. Celery creates the
initial prefork children before `worker_ready`, so those children forked an
**unfrozen** parent image. Each child then ran `worker_process_init` →
`gc.collect()`, which writes object headers and copies every examined page. The
private copy stayed in each initial child for its whole life. Replacement
children, forked after `worker_ready`, inherited the frozen parent and shared
those pages, so the first child of every worker was the expensive one.

`src/config/runtime_profile.py` chooses the topology: constrained and standard
hosts run a dedicated `interactive` worker plus a background worker; the minimal
tier merges every queue into one worker. Nothing in this change alters that
choice.

## Change

`src/config/celery.py` now freezes the parent image at
`worker_before_create_process`, before the first child is forked, and keeps
`worker_ready` as a fallback for pools that do not send the before-create
signal. A process-wide guard freezes once, so a replacement fork does not retain
transient parent state permanently. The child still collects and freezes its own
leftovers, because objects created after the parent freeze are genuinely private.

No task, queue, route, scheduling or data-shape change. `src/config/tests/test_celery_gc.py`
covers before-create ordering, the ready fallback, retry after a failed
freeze/collection, and the child path.

## Method

- Native Apple M1 Pro, 10 logical CPUs, 16 GiB RAM; macOS 27.2 arm64, Python
  3.12.15, SQLite 3.53.4, Redis 8.8.0. No container quota.
- Real prefork worker processes (`--pool=prefork --concurrency=1`), disposable
  SQLite and socket-only Redis. Separate topology: `interactive` + `celery`.
  Merged control: one worker consuming both.
- Fixture: one user with 10,000 completed, scored movies across 3,650 days.
- Idle: each child reports its own `psutil` RSS/USS after a warm-up task. Five
  independent worker starts per separate variant; two for the merged control.
- Load: one full Statistics sweep, then the same child memory probe. Peak during
  a sync is sampled every 20 ms by the task itself; median of three runs.
- PSS is unavailable on macOS and is reported as null, not zero. Parent USS is
  likewise unavailable; “total private” uses each child's USS plus its parent's
  RSS, so it is a lower bound on the process group's private footprint.

Commands:

```sh
SECRET=test-only uv run --no-sync python perf-results/tasks04a/measure.py \
  --output perf-results/tasks04a/baseline-separate.json --topology separate --samples 5
SCRIPT_DIR=perf-results/tasks04a ; for i in 2 3 4 5; do \
  SECRET=test-only uv run --no-sync python perf-results/tasks04a/measure.py \
    --output "perf-results/tasks04a/baseline-separate-$i.json" --topology separate --samples 1 ; done
SECRET=test-only uv run --no-sync python perf-results/tasks04a/measure.py \
  --output perf-results/tasks04a/after-separate.json --topology separate --samples 5
SCRIPT_DIR=perf-results/tasks04a ; for i in 2 3 4 5; do \
  SECRET=test-only uv run --no-sync python perf-results/tasks04a/measure.py \
    --output "perf-results/tasks04a/after-separate-$i.json" --topology separate --samples 1 ; done
python3 perf-results/tasks04a/analyse.py --dir perf-results/tasks04a \
  --json perf-results/tasks04a/memory.json --markdown perf-results/tasks04a/memory.md
```

The baseline ran with the committed `worker_ready`-only handler; the after ran
with the patch. `git diff src/config/celery.py` is the complete production diff.

## Result

| Variant | Idle child USS | Idle child RSS | Idle parent RSS | Total private |
| --- | ---: | ---: | ---: | ---: |
| Baseline, separate | 54.5 MiB | 61.4 MiB | 29.8 MiB | 168.9 MiB |
| After, separate | 24.4 MiB | 60.8 MiB | 25.7 MiB | 100.4 MiB |
| After, merged control | 24.5 MiB | 60.9 MiB | 25.7 MiB | 50.2 MiB |

- Child private memory (USS) fell **55.2%** (54.5 → 24.4 MiB) at idle; total
  private memory of the two-worker topology fell **40.6%** (168.9 → 100.4 MiB).
- Peak during a full sync: USS 48.3 → 44.9 MiB (**−7.1%**), RSS 56.6 → 55.7 MiB
  (**−1.7%**, median of three runs each). Peak is dominated by the task's own
  working set, so the inherited-image saving is smaller there.
- RSS moves little because it counts shared pages; USS/PSS is the number that
  matters for memory pressure. Child RSS stayed ~61 MiB.
- The merged minimal-tier topology uses about **50 MiB less** total private
  memory than the separate topology. That is the real price of isolation. Task
  04 measured the benefit: a priority-0 webhook waited 1.8 s p95 on a merged
  worker versus 0.003 s on the separate topology. Keeping the split is justified.
- No worker churn: worker starts and task success were unchanged; the 10,000-play
  sweep still published all 11 ranges and preserved the exact play count.

## Tests and scope

Five `config.tests.test_celery_gc` regressions plus the installer/runtime-profile
tests passed. Production prefork workers, Linux cgroup memory and PostgreSQL were
not run; macOS cannot report PSS. The 10,000-play fixture is a short task, so the
peak measurement does not cover a multi-minute range.

## Rollback

Revert `src/config/celery.py` and delete the regression file. There is no state,
schema or task-protocol change; the next worker restart restores the previous
freeze timing.
