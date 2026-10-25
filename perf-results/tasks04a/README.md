# TASKS-04A — prefork worker private memory

Status: **IMPROVED**. Freezing the Celery parent image before the first prefork
fork keeps the initial children's Django image shared instead of copying it in
each child's private memory. Decision record:
[`docs/plans/TASKS-04A-celery-idle-memory.md`](../../docs/plans/TASKS-04A-celery-idle-memory.md).

## Files

| File | Contents |
| --- | --- |
| `measure.py` | Starts real prefork workers on disposable SQLite/Redis, seeds 10k plays, samples child RSS/USS. |
| `bench_tasks.py` | Benchmark-only `memory` and `sync` tasks loaded into the production Celery app. |
| `analyse.py` | Produces `memory.json` / `memory.md`. |
| `baseline-separate*.json` | Five worker starts with the committed `worker_ready`-only freeze. |
| `after-separate*.json` | Five worker starts with the before-create freeze. |
| `after-merged*.json` | Two worker starts on one combined `celery,interactive` worker. |
| `baseline-peak*.json`, `after-peak*.json` | Three full-sync runs each, with in-task peak sampling. |
| `memory.json`, `memory.md` | Machine-readable and readable comparison. |

## Environment and method

Apple M1 Pro, 10 logical CPUs, 16 GiB RAM; macOS 27.2 arm64, Python 3.12.15,
SQLite 3.53.4 WAL, Redis 8.8.0. Native host, no container quota. Real Celery
prefork workers (`--pool=prefork --concurrency=1`) in separate processes; a
disposable database and socket-only Redis. Fixture: one user with 10,000
completed, scored movies across 3,650 days. No provider or production data.

The worker child reports its own memory through a benchmark task, so USS does
not require `task_for_pid` access from the parent. Warm-up task first, then the
measured sample. Idle is after the warm-up task, before the full sweep; loaded
is after the sweep. Peak during a sync is sampled every 20 ms inside the syncing
child. PSS and parent USS are unavailable on macOS and are reported as null, not
zero.

## Commands

```sh
# Baseline (committed worker_ready-only handler)
SECRET=test-only uv run --no-sync python perf-results/tasks04a/measure.py \
  --output perf-results/tasks04a/baseline-separate.json --topology separate --samples 5
for i in 2 3 4 5; do
  SECRET=test-only uv run --no-sync python perf-results/tasks04a/measure.py \
    --output "perf-results/tasks04a/baseline-separate-$i.json" --topology separate --samples 1
done

# After (before-create freeze)
SECRET=test-only uv run --no-sync python perf-results/tasks04a/measure.py \
  --output perf-results/tasks04a/after-separate.json --topology separate --samples 5
for i in 2 3 4 5; do
  SECRET=test-only uv run --no-sync python perf-results/tasks04a/measure.py \
    --output "perf-results/tasks04a/after-separate-$i.json" --topology separate --samples 1
done
for i in 1 2; do
  SECRET=test-only uv run --no-sync python perf-results/tasks04a/measure.py \
    --output "perf-results/tasks04a/after-merged-$i.json" --topology merged --samples 1
done

python3 perf-results/tasks04a/analyse.py --dir perf-results/tasks04a \
  --json perf-results/tasks04a/memory.json --markdown perf-results/tasks04a/memory.md
```

Each run creates and removes its own temporary directory, SQLite file and Redis
socket. The `os._exit(0)` at the end avoids Celery's result-consumer thread
outliving the disposable broker.

## Raw result

| Variant | Idle child USS | Idle child RSS | Idle parent RSS | Total private |
| --- | ---: | ---: | ---: | ---: |
| Baseline, separate (5 starts) | 54.5 MiB | 61.4 MiB | 29.8 MiB | 168.9 MiB |
| After, separate (5 starts) | 24.4 MiB | 60.8 MiB | 25.7 MiB | 100.4 MiB |
| After, merged control (2 starts) | 24.5 MiB | 60.9 MiB | 25.7 MiB | 50.2 MiB |

- Idle child USS: **−55.2%**; total private for the two-worker topology:
  **−40.6%**. Child RSS is essentially flat (−1.0%) because the saved pages were
  shared copies that RSS already discounted in the parent; USS is the private
  footprint that matters under pressure.
- Full-sync peak (median of 3 runs): USS 48.3 → 44.9 MiB (**−7.1%**), RSS
  56.6 → 55.7 MiB (**−1.7%**). The task's own working set dominates the peak.
- Merged topology is ~50 MiB smaller than separate. Task 04 showed the separate
  topology cuts priority-0 webhook wait p95 from 1.8 s to 0.003 s, so the memory
  is buying the latency guarantee.
- No worker churn or task loss: every full sweep published all 11 ranges and
  preserved the exact play total; child `gc_freeze_count` stayed ~150k in both
  variants and every child completed its warm-up task.

## Limitations

- macOS only; PSS and parent USS are unavailable, and no Linux cgroup limit was
  exercised. The 10k fixture makes a short sync, so the peak is not a
  multi-minute range.
- The merged control has two runs, enough to show the topology's memory
  difference, not a distribution.
- The absolute saving scales with the shared Django image; a container with a
  different image or number of workers will have a different MiB value, but the
  mechanism (initial fork inherits a frozen image) is the same.
