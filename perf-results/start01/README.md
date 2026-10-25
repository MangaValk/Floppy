# START-01: startup integrity and file warming

Verdict: **INCONCLUSIVE — START-01 remains open.** Measurable warming was
confirmed, but unnecessary physical I/O or a safe, meaningful end-to-end gain
was not established. No application implementation was changed.

## Results and decision

Twelve accepted independent data-cold starts completed, three per size and
verification state, using the final sequential probe protocol. All passed
post-start storage, foreign-key and library-count checks. The source scope is
unchanged between measured SHA `27b89e56a5a91548ebd4a84eba2fc5bce119fff4`
and reviewed HEAD `f04f2675a5e9ac5b9cd8fd6db5208b322d2b5c64`; intervening
unrelated work was not included in the benchmark image or this investigation.

The complete machine-readable readings are in [measurements.json](measurements.json),
with readable per-run CPU, wall time, bytes, memory, migration-stage and
post-ready readings in [raw-observations.md](raw-observations.md).
Every sample retains original counters, configuration, logs and cProfile files
under `raw/`. [profile-summary.txt](profile-summary.txt) shows representative
function attribution. [decision.json](decision.json) records the verdict and
condition contrasts separately from optimization deltas.

Baseline raw seconds, in trial order:

| Movies | Verification | Healthy seconds | First usable seconds |
|---|---|---|---|
| 1,000 | Required | 32.353, 28.996, 46.559 | 33.913, 30.033, 47.615 |
| 1,000 | Recent record valid | 67.417, 22.863, 18.523 | 68.876, 23.667, 19.292 |
| 100,000 | Required | 29.679, 21.754, 27.720 | 38.143, 30.068, 53.815 |
| 100,000 | Recent record valid | 20.255, 18.341, 19.680 | 36.242, 25.665, 24.998 |

Baseline medians; CPU, I/O and peak memory below run through first usability:

| Movies | Verification | CPU seconds | Total block I/O bytes | Peak MiB |
|---|---|---:|---:|---:|
| 1,000 | Required | 31.243 | 74,170,368 | 569.750 |
| 1,000 | Recent record valid | 27.932 | 25,370,624 | 552.613 |
| 100,000 | Required | 38.435 | 497,356,800 | 1,130.762 |
| 100,000 | Recent record valid | 27.207 | 473,841,664 | 1,136.266 |

Lower latency, CPU, bytes and memory are desirable for an equivalent workload.
These four rows are **conditions of the same implementation**, not before/after
results. Ordered trials, changing shared-host contention and application/image
cache residency confound a causal comparison of their overall timings. No p95,
p99, statistical significance or new speedup is claimed.

### Confirmed quantity and exact mechanism

All six valid-record starts called only `_skip_recently_verified`: **zero warming
passes and zero full scans**. Its schema/open check read 368,640 physical bytes
per run. There is no observed repeated warming initiated by web or Celery workers.

Each required-verification start warmed exactly one file length: **7,639,040
bytes** for the small fixture or **441,847,808 bytes** for the large fixture. WAL
was zero at start. This is one additional userspace sequential pass before SQLite
reads its b-trees; it is not proof of an additional physical disk pass.

| Movies | Warming wall seconds | Warming CPU seconds | Following scan wall seconds |
|---|---|---|---|
| 1,000 | 0.0647, 0.0883, 0.0874 | 0.0268, 0.0656, 0.0644 | 0.4866, 0.1450, 0.1263 |
| 100,000 | 1.5393, 0.9083, 1.4679 | 0.9496, 0.6613, 0.5966 | 4.5146, 4.0748, 2.6021 |

The subsequent full scans reported **zero additional physical read_bytes in all
six runs**. They still made logical reads (about 22.3 MB small / 1.69 GB large).
Representative cProfile attribution puts 0.870 of 0.904 warming wall seconds in
54 `FileIO.readinto` calls; 4.005 of 4.070 scan seconds are SQLite `execute` calls.
The quick-check and foreign-key operations remain the integrity gates.

The measured warming cost is real. Its necessity and net benefit depend on the
read pattern/storage: deleting the pass can move the same disk reads into SQLite
and change random-read latency. A counterfactual benefit on NAS/spinning storage
was **not measured**. The supplied source concern therefore does not establish
that this pass is unnecessary. Migration/static/bootstrap stage costs are retained
in the raw observations; changing them belongs to START-02 and was not attempted.

### Target, changed readings and deltas

The baseline-informed candidate target would be to remove one file-length of
userspace warming reads (441,847,808 bytes on the large fixture), while preserving
both SQLite checks, reducing total guard CPU/wall time, and not increasing
physical I/O, startup-to-healthy/usable, peak memory or response/queue latency.
This is a proposed evaluation target, **not an achieved result**. No fixed
percentage improvement was assumed before the baseline.

No implementation candidate was adopted: the existing verified fast path already
avoids the work, and this baseline does not establish that removing cold warming
would produce a meaningful safe improvement. Per the work item's stop rule, the
implementation remains intact. **Changed raw readings: not applicable. Absolute
and percentage optimization deltas: not applicable, not zero.** There is no changed
application commit to measure. Tests passing are not evidence of a speedup.

For the requested required/valid-record condition comparison only, large-fixture
median healthy time differs by -8.040 s (-29.01%), usable time by -12.478 s
(-32.71%), CPU by -11.228 s (-29.21%), block I/O by -23,515,136 bytes (-4.73%),
and peak memory by +5.504 MiB (+0.49%). These observations include host/cache
variation and the existing scan bypass; they are **not optimization gains**.
Exact condition deltas are in `decision.json`.

### Correctness, side effects and limits

- All 12 accepted runs returned `quick_check=ok`, zero foreign-key conflicts,
  unchanged item/movie counts, and 564 applied migrations. Logs confirm no pending
  migrations; stage wall/CPU costs remain captured despite the no-op migration plan.
- All 89 Linux integrity/recovery/watchdog regressions passed; macOS passed with
  14 expected Linux-only skips. No recovery, verification validity, repair, migration,
  auth, provider or PostgreSQL branch was changed. No new implementation regression
  tests are needed because no implementation candidate was retained.
- Library and invalid-token webhook latencies are retained per run. No new latency,
  memory or queue benefit/regression can be attributed to an unchanged implementation.
  Accepted webhook delivery/queue delay was not benchmarked; rejection probes are
  not a substitute. Some baseline logs show transient Redis cooldown errors and an
  unregistered `app.tasks.reconcile_game_groups_backfill` task on the unchanged image;
  these were not reclassified as START-01 regressions or repaired out of scope.
- Only **data-cold / otherwise idle application / shared loaded host** conditions
  were accepted. Five warm repetitions and a dedicated idle-host comparison were
  not collected: large shared-host variation made a fine-grained speed claim
  unjustified. The exploratory warm sample is excluded. No production/provider
  workload, loaded application queue, PostgreSQL runtime, slow NAS/HDD, fragmented
  or freelist-heavy database, nonempty-WAL startup, or simultaneous container
  writers was measured. The helper's WAL and failure behavior is covered by tests.

Files changed are confined to this evidence/harness directory,
`docs/plans/START-01-startup-integrity.md`, and the START-01 status entry in
`docs/plans/Floppy_Performance_Master_Backlog.md`. The master backlog is explicitly
excluded by `.git/info/exclude`; its local status is updated, while the scoped
plan and evidence are committed without importing the entire private backlog.
Rollback requires no application or data migration: revert that scoped
documentation/evidence commit and remove the local master-backlog status note
if desired.
Disposable resources use the `floppy-start01-*` names; the runner removes its
application/Redis containers and internal network after a run. Fixture volumes
may be removed with `docker volume rm floppy-start01-small floppy-start01-large`
when unused. The pinned image can be retained for reproduction.

Separately scoped follow-up needed to close START-01: paired, alternating
full-start counterfactual trials on an isolated host with representative NAS/HDD,
fragmented/free-page and WAL cases, including accepted-webhook queue latency.
START-02 work, issue creation and speculative implementation changes are excluded.

## Reproduction and environment

Source SHA: `27b89e56a5a91548ebd4a84eba2fc5bce119fff4`.
The image is built from `git archive HEAD`, excluding unrelated pre-existing
working-tree edits. `image.json`, `docker-environment.json`, `build.log.gz`,
`linux-limits.txt` and `shared-host-load.txt` retain environment evidence.

Host: Apple M1 Pro, 16 GiB RAM, macOS 27.2 build 26B5101f / Darwin 27.2.0 arm64. Docker Engine 28.1.1,
10 virtual CPUs, approximately 7.65 GiB VM memory, Linux 6.10.14-linuxkit.
The VM is shared with other running workloads; it is **not an idle host**.
Containers are limited to 2 CPUs, 2 GiB RAM, no container swap allowance,
256 processes, and 4096 file descriptors. Python 3.12.15, Django 5.2.17,
SQLite 3.53.4; the image installs the checkout's locked production dependencies.

```sh
mkdir -p /tmp/floppy-start01-source
git archive 27b89e56a5a91548ebd4a84eba2fc5bce119fff4 | tar -x -C /tmp/floppy-start01-source
docker build --build-arg COMMIT_SHA=27b89e56a5a91548ebd4a84eba2fc5bce119fff4 \
  -t floppy:start01-baseline /tmp/floppy-start01-source
python3 perf-results/start01/run.py --cold-only
python3 perf-results/start01/analyse.py
```

Shell commands were executed through `rtk proxy`; Docker required sandbox
escalation. Scripts above contain the full Docker arguments and fixture commands.
The runner resumes existing result directories; move `raw/` aside before
collecting fresh observations rather than reusing completed samples.
`run.py` without `--cold-only` additionally collects one excluded warmup and
five warm starts per size/verification combination. `--smoke` is exploratory.

All data is disposable. Fixtures have one synthetic user and either 1,000 or
100,000 manually sourced movies and catalog items, with 2 KiB synopsis fields.
The schema is produced by normal Django migrations, not by bypassing migrations.
The larger fixture copies the smaller schema using SQLite's backup API and adds
rows through the ORM. No production database, real user or provider is used.

Each measured start restores the same per-size database snapshot before creating
a fresh application container. A synthetic authenticated DB session is created
before timing. For `verified`, the existing verification writer binds a fresh
record to that restored file's actual inode/device and the benchmark image SHA.
For `unverified`, that record is removed. Prior startup status is cleared.
Before a cold start the file is fsynced and Linux `POSIX_FADV_DONTNEED` is issued.
This is **SQLite-data-cold**, not a rebooted machine or flushed host SSD cache.
Application/dependency image caches can remain warm. Kernel advice is best effort;
actual disk reads are recorded rather than assumed. For warm trials, the file
is read before launch instead. WAL is checkpointed and its initial size recorded.

Redis is flushed before every preparation. The only seeded Redis entries are
controlled empty TMDB provider catalogs needed by library rendering. In addition,
benchmark-only `requests.Session.request` mocks in Gunicorn/Celery return an empty
provider result without HTTP I/O, even if Redis is unavailable. A network-disabled
container self-check verified that response shape; mock calls appear in the logs.
The Docker
network is internal, with no published port or external provider access. The
application uses ordinary production settings and the standard runtime entrypoint.
Explicit web sizing is one Gunicorn worker/two threads; standard resource tier
selects a background Celery worker (celery,discover) and dedicated interactive
worker, each concurrency one, with beat. Actual sizing and process lists are
stored per sample. No imported data or provider accounts are configured.

Time zero is immediately before launching `/runtime-entrypoint.sh` inside the
fresh container, excluding image creation, fixture preparation, and the measurement
process's own imports. Readiness is the first HTTP 200 from `/health/`, not the
Docker healthcheck scheduler's 45-second sampling interval. First usable is an
authenticated `/medialist/movie` response containing a fixture title. Health is
polled until successful, then one authenticated library request is made. The
interval is 250 ms plus request time and scheduling. Health requests allow ten
seconds and library requests sixty seconds to complete; application timeouts are
unchanged. This prevents the probe from cancelling a slow library render and
building a queue of retries. Accepted samples use
`sequential-health-then-library-v2` throughout. These are observed response times,
not an exact server-listen instant. Older two-second probes produced overlapping
requests on the large fixture; all of those exploratory samples are excluded in
`rejected-smoke/two-second-probes/`.

Cgroup v2 `cpu.stat`, `io.stat`, `memory.peak`, `memory.current` and `memory.stat`
are captured at initial, ready and log-stage boundaries. CPU and block I/O use
ready-minus-initial counters; peak memory is the cgroup high-water value through
readiness, including file cache. CPU is aggregate CPU-seconds, not elapsed time.
`io.stat` retains per-device observations; the summary sums reported rbytes/wbytes.
Per-process `/proc/self/io` distinguishes logical `rchar` from physical `read_bytes`
inside the integrity stages. These physical/block counters are Linux VM
observations, not independent host SSD hardware counters. `sitecustomize.py` wraps only the startup policy's
fast-path/warming/scan functions, retaining cProfile data and stage wall/CPU/I/O.
Profiler serialization has a small included overhead; these are instrumented runs.
Migration/static/ownership stage CPU comes from cgroup snapshots at log boundaries.
Full raw counters, log timestamps, profiles and container configuration are retained.

After readiness, ten sequential authenticated library requests and ten invalid-token
Plex webhook POSTs measure idle application response times under shared-host load.
The latter must reject the token and never enqueue work; it is **not** a measurement
of accepted-webhook queue latency or provider integration performance. Post-ready
checks are outside startup counters and assert quick_check=ok, no foreign-key
conflicts, unchanged item/movie counts and the applied migration count.

## Scope and source trace

`runtime-entrypoint.sh` resolves the listener then execs `entrypoint.sh`. For SQLite,
the entrypoint waits on `config.sqlite_startup_watchdog`, which runs
`config.sqlite_recovery_policy.check_database_for_startup` before migrations,
collectstatic, ownership repair, runtime sizing, supervisord, Gunicorn or Celery.
The failed-check path parks startup and serves recovery; it does not start migrations.
`DB_HOST` selects PostgreSQL and bypasses the SQLite guard entirely.

The policy reads the prior status before overwriting it, reopens retired acceptance,
handles incident-scoped decisions, and calls `_skip_recently_verified`. The existing
fast path checks the verification's age (48h), image SHA, file device/inode, prior
status and unresolved recovery report, then opens SQLite and reads sqlite_master.
It returns before warming or scanning. An open error falls through to the full scan.

For an unverified file, `_warm_cache` calls `sqlite_integrity.warm_database_cache`:
one 8 MiB reusable buffer, sequential reads of the database and WAL, and best-effort
sequential access advice. `_scan_and_publish_block` then runs quick_check and the
foreign-key inspection on a SQLite connection, with progress callbacks. Successful
scans record verification. Existing repairs retain their locked, verified-backup,
incident-token and rollback safeguards. Errors do not turn into a verification.
The scan runs in one child; web/Celery workers cannot repeat it during this startup
because services start afterward. Other containers sharing the file are not simulated.
The periodic snapshot path in `src/app/tasks_db_backup.py` calls
`create_live_database_snapshot`, which can also record recent verification after
checking the copy. That schedule is not on the synchronous startup critical path.

## Correctness validation

```sh
UV_CACHE_DIR=/tmp/start01-uv-cache SECRET=test-only scripts/test.sh \
  config.tests.test_sqlite_startup_fast_path \
  config.tests.test_sqlite_recovery_policy \
  config.tests.test_sqlite_integrity \
  config.tests.test_sqlite_data_preserving_recovery
```

macOS: 89 tests, 14 Linux-only skips, passed. Linux: all 89 passed, including
watchdog progress/stalls, termination, verification invalidation, snapshot checks,
failure/retry behavior, write-lock/recovery decisions and data-preserving repairs.
Exact-runtime Linux test output is `tests-linux-exact-runtime.log.gz`.
These SimpleTestCase suites can run with Django configured with SECRET_KEY,
INSTALLED_APPS=[], DATABASES={}, USE_TZ=True and unittest's loader.
In the production test container `/opt/venv` was moved to `/test-venv` before
invoking `/test-venv/bin/python`, allowing shell-test PATH stubs to be selected.
The image's fixed virtualenv otherwise overrides those stubs; that initial test
invocation failed two fixture assumptions, retained in
`tests-linux-production-env.log.gz`. The corrected exact-dependency run passed.
An additional Debian source-test image run also passed all 89 (`tests-linux.log.gz`).

Initial local test invocation could not access the default uv cache; rerunning
with the writable temporary cache above passed. Exploratory fixture failures
(invalid source enum, missing provider fixtures and an incorrect post-ready URL)
were corrected before the baseline. `rejected-smoke/` observations are excluded.

Raw `.log.gz` files are losslessly compressed; `log-manifest.json` retains their
uncompressed sizes and SHA-256 hashes. Read one with `gzip -cd PATH.log.gz`.
The collector writes plain logs during a fresh run; packaging does not modify
observations or raw log bytes.
