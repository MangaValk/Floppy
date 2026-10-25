# SQLite availability and verification

Ordinary restarts do not warm the database, run `quick_check`, run
`foreign_key_check`, or invoke no-op migration handlers. Admission reads the
schema, migration history, model table/column names and recovery sidecars.
Each SQLite statement has a five-second progress deadline and a two-second busy
timeout; the entrypoint bounds the whole command, including imports and I/O,
to 30 seconds (then five seconds to kill it). A kernel storage operation in
uninterruptible sleep cannot be made healthy by a Python or shell deadline.

An expired 48-hour verification, changed image SHA, absent old verification
record, interrupted scan or previous timeout requests verification after
startup. These are not corruption findings. An old record is not proof that
the current database is entirely healthy; admission checks only accessibility
and compatibility. Latent damage outside the pages read can be found later.

Availability still blocks for:

- unreadable/malformed database or incompatible migration history/schema;
- unresolved, accepted legacy, prepared, corrupt or unreadable recovery reports;
- a previous explicitly failed/blocked startup check;
- a database replacement that would inherit another file's verification;
- pending migrations without an unchanged verified recovery snapshot and
  matching migration plan/image, or with a missing/changed backup;
- admission exceeding its deadline or storage/lock errors.

The parked container serves a diagnosis/recovery page. Admission never repairs
rows. An incident-scoped operator decision dispatches bounded offline recovery
before admission, while services remain stopped; stale approvals do not trigger
a new scan after the incident closes. PostgreSQL retains its existing
migration/startup path and does not run SQLite verification.

## Pending migrations: explicit offline preparation

Stop **all** application containers, workers, scheduled jobs and other database
writers. Use the intended new image with the same database, secret and backup
mounts, overriding its entrypoint:

```sh
docker compose run --rm --no-deps --entrypoint python floppy \
  manage.py sqlite_startup --prepare-migrations
docker compose up -d floppy
```

For Unraid/Portainer, run the equivalent one-off container using that image and
the existing mounts/environment, with `python manage.py sqlite_startup
--prepare-migrations` as its command. Do not start a second normal application
container against the database during preparation.

Preparation makes a durable recovery snapshot under `BACKUP_DIR/verification`,
checks its structure **and** foreign keys, and records a private migration
permit beside the live database. Main database, WAL and rollback-journal file
identity/size/mtime bracket preparation. Startup rechecks those signatures,
the snapshot signature, migration plan and image SHA before permitting DDL.
Absent and zero-byte WAL files are equivalent because neither contains frames;
nonempty WAL files retain their full fingerprint. SQLite may create an empty WAL
while opening a read-only backup. No WAL/SHM files are manually removed.
Changed data fingerprints, restored/replaced files, changed backups or changed plans
requires preparation again. Online verification cannot issue this permit.
Preparation invalidates any previous permit before beginning.

Maintenance has a one-hour process deadline by default. `--timeout SECONDS`
allows an explicitly chosen longer maintenance window. On failure/timeout,
inspect the phase/logs and storage; no new migration permit is granted. This
workflow can cost a full copy plus two scans and needs space for the snapshot
and SQLite temporary files. It deliberately occurs in a scheduled maintenance
window, rather than on every restart. Regular quick-check-only backups and
old live verification records cannot authorize migrations.

SQLite migrations use the progress watchdog: 180 seconds with neither read
nor CPU progress stops the command; an absolute four-hour ceiling remains.
They do not retry automatically after failure. The recovery snapshot remains
available for inspection/restoration. Migration `events.0017` creates its
datetime index transactionally, without Django's unrelated global FK exit
scan; interrupted index creation and its migration record roll back together.
No production migration records are faked or deleted.

## Verification while serving traffic

Supervisor manages `sqlite-verification` independently of Celery and web
workers. It waits 60 seconds before its first attempt, then checks hourly.
All automatic full-check attempts are limited to once per 48 hours per database
file, including failed/interrupted attempts. Hourly wakeups retain the failure
diagnosis rather than repeatedly copying/scanning a large database.
A database-adjacent advisory lock excludes duplicate
comprehensive verifiers. A dead process releases the lock automatically.

The verifier runs at lower CPU priority. The [online backup API](https://www.sqlite.org/c3ref/backup_finish.html) copies 256 pages
per step and yields between steps, releasing its live read lock between
steps. Structural checking runs on the private copy. Relational checking runs
on that copy with periodic yields, after the live connection is closed. It
holds no live write transaction and no long-lived live scan/read snapshot.
Retention removes old verification snapshots only after both checks pass;
failed checks cannot prune the last fully verified recovery copy.
Continuous writers can force backup retries; the process deadline ends the
attempt rather than holding availability hostage. This is pacing, not a hard
storage bandwidth guarantee; monitor traffic on slow/shared storage.

Observe Supervisor state, `[sqlite-verification]` phase/error logs, and
`DB_FILE.verification.json` (phase, start/elapsed time, backup path, separate
structural/relational outcomes). A timed-out worker may leave its last running
phase in the file; the parent logs the deadline failure. Manually request an
attempt with `python manage.py sqlite_startup --background`.

A snapshot passing `quick_check` establishes structural integrity of its
copy only. It does **not** establish relational integrity. Existing scheduled
snapshots retain their quick-check-only contract and cannot satisfy the
migration gate. The comprehensive verifier separately runs
`foreign_key_check`, publishes relationship findings as a blocking incident,
and leaves live rows untouched. Corruption/relationship findings remain on
disk, visible in logs and block the next startup. They do not trigger repairs
or terminate an already-serving process.

For relationship recovery, stop writers and run
`python manage.py sqlite_startup --recover`; this uses the existing
incident-scoped, backup-protected recovery policy and operator decisions.
Then prepare pending migrations again. For physical corruption or unreadable
reports, preserve the database and sidecars, inspect/restore a known-good
backup offline and explicitly archive the old incident only after confirming
the restored database is healthy. Never delete WAL/SHM to force a start.
