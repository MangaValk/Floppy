# SQLite 0206 startup investigation — October 24, 2026

## Assessment

There are two reproducible software failure mechanisms. Neither establishes
that the production database is corrupt or requires an Unraid upgrade.

1. **False JSONField E180 under a writer lock.** Django 5.2.17's SQLite
   `supports_json_field` cached property runs `SELECT JSON(...)` inside
   `transaction.atomic()`. Floppy configures `BEGIN IMMEDIATE`, so entering
   that transaction requests a writer lock even though the probe only reads.
   Django catches every `OperationalError` in this block and caches `False`.
   A lock timeout therefore becomes an unsupported-feature report. The test
   reproduces Django returning `False` and Floppy's corrected probe returning
   `True` against the same WAL database while another connection holds the
   write lock. This confirms the mechanism, not which exception production
   encountered: the original caught exception was not logged.
2. **A choices-only migration still scans the database.** Django ignores
   `choices` when deciding whether a field requires DDL. 0206 generates no
   schema DDL on SQLite or PostgreSQL. Nevertheless, the migration executor
   enters SQLite's schema editor, which disables foreign-key enforcement,
   starts an atomic transaction (`BEGIN IMMEDIATE` here), applies the no-op
   field change, and inserts the migration record. On schema-editor exit,
   Django runs `PRAGMA foreign_key_check` over the entire database before
   committing and re-enabling enforcement. A migration record written inside
   that transaction is not proof of a successful commit.

The installed `f04f2675a` has the original 0206. This checkout already includes
`fd2ad997c`, which skips that scan for forward 0206 and restricts it to
`app_metadatabackfillstate` for forward 0207. Those changes were already
committed before this investigation; they have not been newly implemented
here. Their behavior is now regression-tested through Django's executor.
There is no reason to replace 0206 with `SeparateDatabaseAndState`: that still
enters the executor's schema-editor context and does not itself remove the
exit scan or the transaction lock. Do not fake either migration.

0205 adds Item's `provider_franchise` JSON field. 0207 adds a real, non-null
Boolean column with a Python default. SQLite can rebuild the metadata-state
table to materialize that default, preserving existing rows; it does not
rebuild the 2.1 GB database as a whole. Its custom operation introspects the
column first, or queries `information_schema.columns` on PostgreSQL. If the
column exists it skips the addition, but still updates migration state.
PostgreSQL's normal AddField path adds the column and supplies the default
for existing rows. No PostgreSQL implementation was changed here.

## What the production evidence establishes

- The duplicate migration container caused real writer contention. Stopping it
  removes that competitor; it does not eliminate the exit scan or make a
  blocked storage read return.
- `D` state with `folio_wait_bit_common` and a `pread64` stack is consistent
  with a kernel storage/page-read wait. It does not identify a Python call,
  SQL statement, damaged page, or the component responsible for the wait.
- An unrestricted foreign-key scan can read a large part of this library and
  expose slow/stalled storage even though the named migration has no DDL.
  The original migration therefore explains substantial unexpected I/O. A
  Python stack or SQL trace is still needed to prove that the observed
  production wait was inside this scan rather than setup, lock acquisition,
  migration recording, or commit.
- `Applying ...` is emitted before entering the schema editor. `OK` follows
  successful application. Docker buffering can hide the last emitted phase;
  this change makes migration output unbuffered and uses verbosity 2 from the
  first attempt. Timeout and other exit statuses are now distinguished.
- Floppy's `AppConfig.ready()` suppresses startup task scheduling for manage.py
  commands. Django's pre/post-migrate handlers run outside the individual
  migration; post-migrate includes content-type/permission work and Floppy's
  demo-account provisioning. They do not run between 0206's start and success.
- The connection hook attempts WAL/synchronous/busy-timeout PRAGMAs and logs
  failures with a traceback. It does not explain away an I/O stall. The new
  JSON probe propagates operational failures other than a missing JSON
  function, making those failures visible instead of reporting E180.

No production/container state was inspected during this investigation. The
supplied Mac backup path was absent in this workspace. Its validity and the
meaning of the reported successful overnight check remain unverified.

## Changes and limits

`config.sqlite_backend` subclasses Django's SQLite backend and changes only
the JSON probe: a standalone SELECT, without acquiring a writer transaction.
Missing JSON still returns unsupported; locks and I/O errors propagate and are
not cached as missing JSON. `IMMEDIATE`, WAL, system checks, and PostgreSQL
settings remain in place.

The migration phase retains its 900-second timeout and five sequential
attempts. It now prints the exit status and identifies timeout 124 explicitly.
This is diagnostic improvement, not a cure for a legitimate migration taking
longer than 15 minutes. For that case use the single supervised maintenance
run below, which has no entrypoint wall-clock timeout.

The integrity watchdog is not reused for migrations: it observes read counts
and CPU, not writes/durable commits, and its fallback sidecar describes the
integrity check. Reusing it unchanged could label legitimate write/commit
waits as stalls and publish the wrong phase. A kernel-blocked process may
remain alive even after SIGKILL; no retry or alternate container is safe until
it has actually exited. A more general migration supervisor is outside this
targeted fix.

## Recovery procedure

Run the host commands on Unraid. This work has not published an image. Use a
reviewed image containing **both** `fd2ad997c` and this JSON-probe fix; the old
installed image and an unverified `latest` tag are insufficient evidence.

1. Capture `docker inspect Yamtrack` locally (it may contain credentials),
   current logs, mount source/destination, image identity, and all containers
   mounting this database. Verify whether the temporary `--skip-checks` patch
   or direct-disk mapping actually exists. Do not assume either does.
2. Disable the restart policy while doing maintenance and stop Yamtrack:

   ```sh
   docker update --restart=no Yamtrack
   docker stop Yamtrack
   ```

   Stop every other holder of the same database, including maintenance
   containers. Confirm their host processes have exited and no file holders
   remain (`fuser`/`lsof`, using both the current share path and physical
   path). A container stop request or elapsed timeout alone is insufficient.
   If any process remains in `D` state, do not start another migrator.
3. Locate and preserve the stated backup; do not overwrite it. Once every
   database process has exited, make a separate cold copy of the current DB
   **with any existing WAL/SHM files** in a new location. Verify copy completion
   before proceeding. Do not delete sidecars, restore an older snapshot over
   the current database, or run repair/rebuild operations. If a consistent
   backup cannot be obtained because reads stall, resolve that read failure
   first.
4. Run exactly one maintenance container using the reviewed image, the same
   database mount, runtime environment, and network as Yamtrack, with its
   normal entrypoint overridden and restart disabled. Keep Yamtrack stopped.
   In that container's `/floppy` directory, run this command in the foreground
   and save its output:

   ```sh
   DB_POOL_ENABLED=false python -u -c '
   import faulthandler, runpy, sys
   faulthandler.dump_traceback_later(120, repeat=True)
   sys.argv = ["manage.py", "migrate", "--noinput", "-v", "2"]
   runpy.run_path("manage.py", run_name="__main__")
   '
   ```

   This keeps system checks, has no automatic retry or 900-second timeout, and
   emits a Python stack every two minutes while running. Do not start a
   concurrent `docker exec ... migrate`. A stack in
   `check_constraints()`/`foreign_key_check` identifies the scan; a stack in
   `_start_transaction_under_autocommit()` identifies transaction entry;
   recorder/commit frames distinguish those later phases. A lone
   `cursor.execute()` frame without its callers is not sufficient evidence.
5. If it stalls again, compare the Python stack with host `/proc/<pid>/stat`,
   `/proc/<pid>/io`, `wchan`, and kernel stack over several samples. The new
   forward 0206 should not run a foreign-key scan. If it does, verify the
   actual loaded migration file and image digest. If only filesystem reads
   remain blocked, no Python migration change can release that kernel wait.
6. **Only if evidence implicates the share/FUSE path**, after all holders have
   exited, change the bind source from `/mnt/user/cache/yamtrack/db` to the
   verified existing `/mnt/disk5/cache/yamtrack/db`, preserving the container
   destination and all files. This tests bypassing FUSE without copying the
   database or changing Unraid. Never expose the same file to simultaneous
   writers through both mount paths. If direct-disk reads also stall, that
   does not support blaming FUSE alone; the host storage wait must be resolved
   before migration can finish. An OS upgrade is not an established remedy.
7. Require migration exit status 0. In the same maintenance environment run:

   ```sh
   python manage.py showmigrations app --plan
   python manage.py migrate --check
   python manage.py floppy_preflight
   ```

   Confirm `[X]` for both 0206 and 0207, no pending migrations, and successful
   preflight checks. Read-only schema inspection must show `terminal`; verify
   the migration rows persisted from a fresh connection, rather than relying
   only on an `Applying` log line. Do not use `--fake` to reach this state.
8. Exit/remove the maintenance container before restarting Yamtrack on the
   same reviewed image and verified mount. Remove the temporary entrypoint
   patch, restore the original restart policy, and start it normally. Require
   Docker health to pass, a successful response from
   `http://10.0.69.1:7000/health/`, and a login/library smoke check. Until these
   succeed, service restoration remains unverified.

## Validation

The focused tests cover a real competing SQLite writer, missing JSON,
operational errors followed by a successful retry, the original no-op
migration's whole-database scan, patched 0206's SQL/state/recording, 0207's
row preservation/default/column-exists path, and 0206 PostgreSQL SQL collection
without a server. Existing SQLite settings, safety, integrity, startup,
API-contract, and About tests are included in the targeted run. PostgreSQL
execution and Linux-only watchdog tests need their normal CI/runtime gates;
SQL collection is not a substitute for a live PostgreSQL upgrade replay.

Local focused result: 170 tests run, 157 passed and 13 platform-specific skips.
That run used `FLOPPY_TEST_FAST_DB=1`; the dedicated migration tests execute
0206/0207 separately through Django's executor.

The subsequent full fast suite used normal migration replay on Django 5.2.17
and SQLite 3.53.4, matching the reported production versions. It ran 9,587
tests: 9,547 passed, 23 skipped, and 17 failed because the execution sandbox
denied local socket binds. All 83 tests in the affected modules
(`app.tests.test_installer`, `config.tests.test_sqlite_recovery_server`, and
`config.tests.test_test_network`) passed when rerun with local socket access,
including all 17 affected cases. No application failures remain unresolved.
The full slow/browser/provider suite and live PostgreSQL upgrade replay were
not run. `ruff check src`, `sh -n entrypoint.sh`, `git diff --check`, and
`makemigrations --check --dry-run` passed.

Sources: Django 5.2.17 [SQLite features](https://github.com/django/django/blob/5.2.17/django/db/backends/sqlite3/features.py),
[SQLite schema editor](https://github.com/django/django/blob/5.2.17/django/db/backends/sqlite3/schema.py),
and the installed Django migration executor and field comparison code.
