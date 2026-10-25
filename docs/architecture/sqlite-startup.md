# SQLite availability and verification

Ordinary restarts do not warm the database, run `quick_check`, run
`foreign_key_check`, or invoke no-op migration handlers. Admission reads the
schema, migration history, model table/column names and recovery sidecars.
Each SQLite statement has a five-second progress deadline and a two-second busy
timeout; the entrypoint bounds the whole command, including imports and I/O,
to 30 seconds (then five seconds to kill it). A kernel storage operation in
uninterruptible sleep cannot be made healthy by a Python or shell deadline.

An expired verification, absent record, interrupted scan or previous timeout
only lets the sliced background verifier continue; a changed image does not. These are not corruption findings. An old record is not proof that
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

## Pending migrations: automatic snapshot at startup

When migrations are pending and no valid permit exists, admission exits 11 and
the entrypoint (services not yet started) runs `sqlite_startup
--prepare-migrations --fast`: an online-API copy of the database, verified with
`quick_check` on the copy, then a permit, then re-admission and migrate. It
skips the relationship (`foreign_key_check`) scan, which runs afterwards in the
background verifier. **Tradeoff:** a pre-existing foreign-key conflict is not
caught before the migration; the verified copy is the restore point. Incidents
and previous failed/blocked checks still block. Set
`FLOPPY_SQLITE_AUTO_SNAPSHOT=false` to require the manual step below. Measured
here: 18.6s for a 2GB database on local SSD.

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

Supervisor runs `sqlite_startup --background` (`sqlite-verification`) 60 seconds
after start and then every 10 minutes, at lower CPU priority. Each run is a
**time slice** (`src/config/sqlite_sliced_check.py`); it makes no copy of the
database and holds no write lock. Hard bounds, all overridable by environment:

- one slice: 300 s (`FLOPPY_SQLITE_VERIFY_SLICE_SECONDS`), enforced with
  `sqlite3_interrupt` because `quick_check` is a single opcode that a progress
  handler cannot stop;
- active verification per rolling 24 h: 3600 s (`..._DAILY_SECONDS`);
- one table's `quick_check`: 150 s (`..._UNIT_SECONDS`), then it falls back to
  resumable row reads;
- read transactions last at most one slice, so WAL checkpoints stall at most
  that long. Connections are read-only, `mmap_size=0`, 64 MiB page cache.

Progress lives in `DB_FILE.verification.progress.json` (identity-bound to the
file, so a replaced database starts over; **not** to the image: a new image
never restarts or re-triggers verification). It records per-unit `verified_at`,
`verified_through` (the oldest unit), `unverified_units`, `fk_incomplete` flags
and the slice ledger. Units are re-verified after 7 days, oldest first. Because
work is capped per day and persisted, a database too slow to finish in a day
simply takes several days to cover, rather than hours in one run; this is
visible, never silent.

Per-unit coverage, which is deliberately different from one full `quick_check`:

| Unit | Detects | Does not detect |
|---|---|---|
| `__pages__`: sequential read in 8 MiB chunks, resumable | unreadable sectors/I/O errors, truncation; header `page_count` vs file size; `freelist_count` sanity | page contents are not interpreted |
| `quick_check(table)` per table (includes that table's indexes) | b-tree/page/record-format damage | nothing beyond `quick_check` itself (it never compared indexes with tables) |
| `rows` fallback (table over its 150 s unit budget) | every record and overflow chain decodes, descent root to leaf | page-level invariants and **that table's indexes** |
| `foreign_key_check(table)` | relationship conflicts | a table whose check exceeds the slice is marked `fk_incomplete` and retried; it can stay incomplete on very slow storage |

Findings use the existing reports: damage writes a `corrupt` incident and
conflicts a `blocked` one, both of which block the next start; live rows are
never touched. Busy/I/O/interrupted errors are transient and retried.
The previous design copied the whole database (read plus write), ran
`quick_check` and `foreign_key_check` on the copy under a one-hour kill, and
therefore could not finish on a 5 GB database on slow storage while contending
for the same disk. That path remains only for `--prepare-migrations`
(maintenance window, snapshot required for the migration permit). The
background run no longer produces verification copies; recovery copies come from
the scheduled snapshot task (whose own `quick_check` of its copy is not yet
sliced).

Observe `[sqlite-verification] slice status=...` logs and the progress file.
Manually run a slice with `python manage.py sqlite_startup --background`.

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
