# START-02 — Repeated static collection and bootstrap

The repeated work is confirmed. Full acceptance is **INCONCLUSIVE**; START-02 remains open. See the final comparison below.

## Reproduction and environment

Baseline commit: `d6292bdbe0281b68057b485bfff1601139f40057`.
Candidate commit: `9d460bc3523a51280fad55cf763845fbf9d784d3` in isolated
`codex/start02-bootstrap`; the shared checkout continued receiving unrelated work.
Both images use exactly that commit's locked dependencies. See `image-*.json`
and `environment.json` for image identities, OS, CPU, Docker and limits.

Host: Apple M1 Pro, 10 logical CPUs, macOS 27.2 arm64. Docker Desktop 28.1.1
uses Linux 6.10.14-linuxkit aarch64, overlay2, 10 CPUs and 8,218,034,176 bytes
of VM memory. Both runtime images use Alpine 3.24.3, Python 3.12.15,
Django 5.2.17 and SQLite 3.53.4. Fixture snapshot hashes, exact byte/page counts
and stack versions are in `runtime-and-fixtures.json`.

Each fresh container has 2 CPUs, 2 GiB memory with no additional swap, 256 PIDs,
4096 file descriptors, one Gunicorn worker with two threads and two Celery worker
services at concurrency one: background consumes `celery,discover` with beat,
and the dedicated interactive worker consumes `interactive`. Redis is flushed
for each trial. The internal Docker
network has no published port or external-provider traffic; provider requests
are mocked by benchmark-only `sitecustomize.py`.

Fixtures contain one user and 1,000 / 100,000 manually sourced tracked movies,
with 2 KiB synopses. A fixed SQLite snapshot is restored before each startup.
Preparation checkpoints WAL, creates an authenticated session and either removes
the verification record or creates one bound to the restored database and image.
There are 564 applied migrations and no pending schema changes. Cold means
fsync plus POSIX_FADV_DONTNEED on the disposable database; code, image and host
storage caches are not globally flushed. Warm means explicitly reading that file.

Startup wall time begins immediately before `/runtime-entrypoint.sh`, excludes
fixture preparation and Docker create, and ends at successful `/health/` or the
first authenticated `/medialist/movie` response containing fixture data.
The health probe has a ten-second client budget; the sequential library probe
has sixty seconds. Poll interval is 250 ms. Cgroup CPU, total block I/O and peak
memory are sampled through first usability. Per-stage cgroup deltas and per-Python
lifetime CPU/RSS/I/O are preserved. Existing integrity phases are cProfile-instrumented
identically in both versions; dedicated static cProfile runs are separate diagnostics.
Healthy here means the first successful health endpoint response, not Docker's
periodic HEALTHCHECK state transition. Its 45-second interval, 30-second start
period and service startup priorities remain unchanged; the scheduler can hide
an endpoint readiness improvement until its next probe.
Block I/O can include asynchronous writeback, so stage attribution does not prove
specific copy-on-write internals. Logical process bytes and physical bytes are distinct.

Each ready container receives ten sequential library GETs and ten Plex POSTs
with invalid tokens (expected 401). Paired warm trials also exercise the real
interactive Celery queue with its built-in `celery.accumulate` task. That measures
queue round-trip latency, not an authenticated accepted-webhook workload.
The application has no synthetic concurrent user load; the Docker host has large,
changing unrelated load. Host load averages are preserved per trial. No idle-host,
loaded-application, PostgreSQL service or external provider performance claim is made.

Commands (run from repository root; Docker permission is required):

```sh
# Build each image from git archive of its commit, not the dirty checkout.
git archive <SHA> | tar -x -C <empty-source-directory>
docker build --build-arg COMMIT_SHA=<SHA> -t floppy:start02-<variant> <source-directory>
python3 perf-results/start02/validate_static.py
python3 perf-results/start02/run.py --variant baseline --cold-only
python3 perf-results/start02/run.py --variant changed --cold-only
# Warm: trial 0 is warmup, then trials 1..5; alternate version order each trial.
python3 perf-results/start02/run.py --variant <variant> --warm-only --sizes small --verification verified --queue-canary --index <0..5>
python3 perf-results/start02/run.py --variant changed --sizes small --verification verified --cold-only --index 0 --label changed-custom-uid --puid 2001 --pgid 2002 --queue-canary
python3 perf-results/start02/analyse.py
python3 perf-results/start02/compare.py
```

The runner resumes accepted result files; move `raw/` aside to repeat from scratch.
It uses only names prefixed `floppy-start02-`. The two fixture volumes intentionally
survive runs for reproducibility; remove only those volumes when finished.
Raw observations, stage tables, full cgroup readings, logs, profiles, asset hashes
and inspections are retained under this directory. No p95/p99 is estimated from
three cold or five warm observations.

Validation commands (isolated candidate worktree):

```sh
UV_CACHE_DIR=/tmp/start02-uv-cache UV_PROJECT_ENVIRONMENT=/Users/dannyvfilms/Developer/Cursor/release/.venv SECRET=test-only scripts/test.sh config.tests.test_static_collection app.tests.test_data_paths app.tests.test_container_bootstrap app.tests.test_css_assets
UV_CACHE_DIR=/tmp/start02-uv-cache UV_PROJECT_ENVIRONMENT=/Users/dannyvfilms/Developer/Cursor/release/.venv SECRET=test-only scripts/test.sh config.tests.test_sqlite_integrity config.tests.test_sqlite_recovery_policy config.tests.test_sqlite_startup_fast_path config.tests.test_sqlite_data_preserving_recovery config.tests.test_runtime_profile config.tests.test_server_port_recovery app.tests.test_preflight_runtime
uv run --no-sync ruff check src
# From the shared checkout, mount its evidence and the isolated candidate source:
docker run --rm --network none -e SECRET=test-only -w /work/src -v /tmp/floppy-start02-worktree:/work:ro -v "$PWD/perf-results/start02:/bench:ro" --entrypoint sh floppy:start02-changed -c 'mv /opt/venv /test-venv; PYTHONPATH=/work/src /test-venv/bin/python /bench/linux_tests.py'
python3 perf-results/start02/verify.py
```

Project-runner results: 44 passed; 146 passed with 14 macOS-specific skips.
Exact-runtime Linux: all 102 passed, including those platform cases. Ruff passed
across `src`. Targeted suites cover static cache validity, concurrent checks,
failure/retry, custom IDs, process/bootstrap contracts, preflight, migration
startup paths and existing integrity/recovery/watchdog behavior. A full application
suite and PostgreSQL service run were not performed for the unadopted candidate.
Logs are losslessly compressed (`*.log.gz`) with original and compressed SHA-256
checksums in `log-manifest.json`; profiler files remain directly usable.

## Cause and bounded implementation

Dockerfile already collects static files at image build. Runtime chain is
`runtime-entrypoint.sh` → `entrypoint.sh` → integrity gate → migrations →
`collectstatic` → ownership repair → resource sizing → `supervisord.conf`.
Baseline performs another complete Django bootstrap/collection and recursive
static ownership repair on every start, even with 274 unmodified files.
The dedicated baseline profile attributes most of the collection wall time to
imports and `django.setup()`. Integrity/recovery work is not repeated by workers:
services start only after these synchronous gates.

The candidate records the standard local static inputs/output after build-time
collection and ownership normalization to UID/GID 1000. Runtime checks file and
directory metadata, settings code and static-app configuration without importing
Django. Unchanged image assets reuse collection and, for default IDs, ownership.
Missing/corrupt records, changed input/output/configuration, symlinks or unsupported
storage/finders fall back to the existing commands. The runtime never updates the
image record. Whole-second file mtimes match Django collectstatic's existing
unmodified-file comparison; this is not a content-integrity/security hash service.
All asset bytes are separately hashed in validation. Custom UID/GID still trigger
recursive static ownership repair. A subsequent restart of that same customized
container conservatively falls back if recorded ownership no longer matches.

No migration, SQLite policy, runtime entrypoint, supervisor command, scheduling,
queue separation, timeout or worker restart behavior changes. Other data/log/
backup/nginx ownership paths are untouched. Remaining repeated small interpreters
are measured but left outside this narrow change.

At the measured SHA, runtime-entrypoint invokes `config.server_port` once to
render nginx listeners and persist the selected port, then execs entrypoint.
The SQLite gate calls `check_database_for_startup` before migrations and before
services. The shell's migration retry loop runs once on these up-to-date fixtures.
`runtime_profile.emit_env` and `sizing_report` run before supervisor, whose priorities
start nginx (1), Gunicorn (5) and Celery (10). Standard sizing merges discover into
the background queue while keeping interactive dedicated. Worker Django imports
and Celery beat continue after supervisor starts; none invokes collectstatic.
Those imports can overlap health/readiness probes and are included in total
cgroup CPU and memory. The build recorder uses collectstatic's management-command
identity during Django setup so it does not schedule application startup work.


## Final measurements and acceptance

**Verdict: INCONCLUSIVE for the full START-02 acceptance criteria.** The redundant work and its CPU cost are confirmed; the bounded candidate beats its static-stage target. End-to-end startup improvement is not statistically established on this changing shared host. START-02 remains unchecked. Candidate implementation is committed on `codex/start02-bootstrap` and preserved as `candidate.patch.gz`; it is not adopted into the shared checkout. Unrelated staged work is preserved.

There are 24 accepted cold starts, ten accepted alternating warm observations after two warmups, and one custom-UID correctness startup: 37 successful starts. The rejected canary warmup is retained separately and excluded.

### Static work (lower is better)

| Cache | Metric | Baseline median | Candidate median | Absolute delta | Percent |
|---|---|---:|---:|---:|---:|
| cold | static_cpu_s | 3.249003 | 0.205217 | -3.043786 | -93.68% |
| cold | static_wall_s | 4.612658 | 0.207104 | -4.405554 | -95.51% |
| warm | static_cpu_s | 2.437729 | 0.268611 | -2.169118 | -88.98% |
| warm | static_wall_s | 3.807237 | 0.228202 | -3.579035 | -94.01% |

Default-mode runtime full collections fall from one to zero and recursive static chowns from one to zero on every accepted candidate start. Warmup filesystem diffs show 305 changed collected-static paths before and zero after. Cold ownership-stage medians fall from 1.992 wall seconds / 0.237 CPU-seconds to 0.0015 / 0.0015, with associated reads/writes from 8,196,096 / 8,073,216 bytes to zero. These are stage-associated cgroup observations, not a block-level proof of filesystem copy-up causality. The separate cProfile diagnostics show baseline Django setup/imports versus metadata traversal in the candidate.

### Raw health / first-usable observations (seconds)

Every CPU, memory, I/O and latency reading is also in [raw-observations.md](raw-observations.md) and [measurements.json](measurements.json). All absolute and percentage cohort deltas are in [comparison.md](comparison.md) and [comparison.json](comparison.json). Lower is better.

| Version / size / verification / cache | n | Healthy raw | First usable raw |
|---|---:|---|---|
| baseline / large / unverified / cold | 3 | 101.024, 99.795, 66.156 | 118.582, 136.955, 92.941 |
| baseline / large / verified / cold | 3 | 29.693, 38.325, 48.427 | 45.184, 55.363, 65.074 |
| baseline / small / unverified / cold | 3 | 34.923, 31.041, 35.419 | 36.748, 33.330, 37.354 |
| baseline / small / verified / cold | 3 | 42.348, 65.886, 72.854 | 43.619, 67.125, 76.716 |
| baseline / small / verified / warm | 5 | 36.015, 33.405, 42.812, 46.313, 40.776 | 37.828, 35.093, 45.893, 47.741, 42.675 |
| changed / large / unverified / cold | 3 | 46.150, 27.924, 26.779 | 66.631, 41.048, 36.977 |
| changed / large / verified / cold | 3 | 25.925, 23.392, 22.635 | 36.669, 33.764, 38.707 |
| changed / small / unverified / cold | 3 | 42.473, 44.449, 35.207 | 45.966, 45.869, 36.755 |
| changed / small / verified / cold | 3 | 41.973, 47.323, 32.084 | 43.979, 48.876, 34.302 |
| changed / small / verified / warm | 5 | 25.317, 41.351, 27.809, 24.173, 40.430 | 27.063, 42.704, 29.299, 26.863, 42.133 |

### Interpretation and side effects

Alternating warm cohort medians: healthy 40.776 → 27.809 seconds (-12.967, -31.80%); first usable 42.675 → 29.299 (-13.376, -31.34%); CPU through usability 36.296 → 29.276 (-7.020, -19.34%); total block I/O 87,515,136 → 53,227,520 bytes (-34,287,616, -39.18%); peak through usability 558.781 → 543.230 MiB (-15.551, -2.78%). These observations are not all attributable to static collection: host load and worker initialization overlap vary.

The five paired first-usable differences are -10.766, +7.611, -16.594, -20.878 and -0.542 seconds. The exact two-sided sign-flip p-value is 0.1875 (same for health); five pairs and nonstationary host load do not establish a statistically reliable overall latency gain. The small/unverified cold cohort is slower by 9.120 seconds (+24.82%) at its median, while other cold cohorts are faster; ordered cohort differences cannot identify the cause.

Post-ready warm library median is 469.588 → 291.814 ms (-37.86%); rejected webhook median 10.523 → 5.419 ms (-48.50%). Interactive queue round-trip cohort medians are 426.918 → 437.593 ms (+10.675, +2.50%); the paired median difference is -124.543 ms. Peak at the earlier health milestone rises 492.730 → 518.570 MiB (+25.840, +5.24%), although peak through usability falls. No consistent resource/queue regression is established, but absence of regression under accepted webhooks or application load remains unproven. Large/verified cold disk reads also rise; total I/O is not uniformly lower.

Cold means data-cache eviction only; warm means data warmed. Both fixture sizes have the same 274 real assets. No static-file-count scaling, same-container restart timing, isolated-host, loaded-application, PostgreSQL performance or accepted-webhook workload was measured. Ordinary PostgreSQL startup still uses the same collection/fallback path; this candidate does not touch database code.

### Correctness, files and rollback

See correctness-summary.json for every accepted-start invariant and correctness/ for real-image fallback and byte comparisons. The final Linux safety test output and project-runner logs are retained with the artifacts. No passing test is treated as performance evidence.

Candidate files: Dockerfile; entrypoint.sh; src/config/static_collection.py; src/config/tests/test_static_collection.py; src/app/tests/test_data_paths.py. Shared-checkout changes for this task are the benchmark/report under perf-results/start02/ and docs/plans/START-02-static-bootstrap.md. The locally ignored master backlog was updated without force-adding it or other private plans.

Rollback: the current application needs no rollback because the candidate was not adopted. Discard a candidate deployment by running the baseline image. If adopting the patch later, reverting its entrypoint/Dockerfile changes and removing the helper restores unconditional collection and static ownership repair; no database/schema/data rollback is involved.

Separately scoped remaining validation: repeat the same paired protocol on an isolated representative host/storage, with accepted-webhook queue latency and matched idle/loaded application traffic, before adopting the candidate and closing START-02. No GitHub issue was created.
