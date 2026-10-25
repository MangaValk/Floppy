"""Time-sliced, resumable background verification of a live SQLite database.

Replaces the copy-then-``quick_check``-the-copy background scan, whose cost is
unbounded on slow storage. Every invocation does at most ``SLICE_SECONDS`` of
work, the total over any rolling 24 hours is capped at ``DAILY_BUDGET_SECONDS``,
and progress is persisted so a restart, a new image or a killed slice resumes
instead of starting over. Units, in order of least recently verified:

* ``pages``: sequential read of the whole file in 8 MiB chunks, resumable by
  byte offset. Proves every page is readable and the file is not truncated
  against the header's page count. It does not interpret page contents.
* per table ``quick_check(table)``: b-tree structure and record format of that
  table and its indexes. A table that does not finish within ``UNIT_SECONDS``
  falls back to ``rows`` mode: every record read by rowid range, resumable.
  That proves records and overflow chains decode, not index or page invariants.
* per table ``foreign_key_check(table)``, within the same unit budget.

Findings reuse the existing incident reports; nothing repairs live rows.
"""

from __future__ import annotations

import fcntl
import json
import os
import sqlite3
import stat
import threading
import time
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path

from config import sqlite_integrity as integrity

SLICE_SECONDS = float(os.environ.get("FLOPPY_SQLITE_VERIFY_SLICE_SECONDS", "300"))
DAILY_BUDGET_SECONDS = float(
    os.environ.get("FLOPPY_SQLITE_VERIFY_DAILY_SECONDS", "3600")
)
UNIT_SECONDS = float(os.environ.get("FLOPPY_SQLITE_VERIFY_UNIT_SECONDS", "150"))
REVERIFY_SECONDS = 7 * 86400.0
_CHUNK_BYTES = 8 * 1024 * 1024
_ROW_CHUNK = 2000
_DAY = 86400.0
_MIN_BUDGET = 5.0
_PAGES = "__pages__"
_PROGRESS_INSTRUCTIONS = 100_000


class _Expired(Exception):  # noqa: N818 - control flow, not an error
    """The unit or slice deadline passed; the work interrupted is retried."""


def _path(db_path: str) -> Path:
    return Path(f"{Path(db_path).resolve()}.verification.progress.json")


def _load(db_path: str) -> dict:
    state = integrity._read_sidecar(_path(db_path), db_path) or {}
    file_stat = Path(db_path).stat()
    identity = [file_stat.st_dev, file_stat.st_ino]
    if state.get("identity") != identity:  # replaced file: nothing carries over
        state = {"units": {}, "slices": []}
    state["identity"] = identity
    state["database"] = str(Path(db_path).resolve())
    return state


def _summarize(state: dict) -> None:
    units = state["units"]
    stamps = [u.get("verified_at") for u in units.values()]
    state["verified_through"] = min(stamps) if stamps and all(stamps) else None
    state["unverified_units"] = sorted(
        n for n, u in units.items() if not u.get("verified_at")
    )


def _save(db_path: str, state: dict) -> None:
    state["updated_at"] = datetime.now(UTC).isoformat()
    _summarize(state)
    integrity._publish_report(
        _path(db_path), json.dumps(state, sort_keys=True) + "\n", mode=0o644
    )


def _now() -> float:
    return time.time()


def _stamp() -> str:
    return datetime.now(UTC).isoformat()


def _age(unit: dict) -> float:
    verified = integrity._parse_timestamp(unit.get("verified_at"))
    return (
        float("inf")
        if verified is None
        else (datetime.now(UTC) - verified).total_seconds()
    )


@contextmanager
def _guarded(conn: sqlite3.Connection, deadline: float):
    """Interrupt the connection's statement at ``deadline``.

    The progress handler alone is not enough: ``quick_check`` runs as a single
    VDBE opcode, so only ``sqlite3_interrupt`` can stop it. The handler stays
    to pace row-reading statements.
    """

    def progress():
        time.sleep(0.002)  # pace: leave I/O and CPU to the application
        return 0

    conn.set_progress_handler(progress, _PROGRESS_INSTRUCTIONS)
    timer = threading.Timer(max(deadline - time.monotonic(), 0.0), conn.interrupt)
    timer.daemon = True
    timer.start()
    try:
        yield
    finally:
        timer.cancel()


def _fail(db_path: str, error: sqlite3.DatabaseError) -> bool:
    """Publish real damage; return False for transient (busy/IO/interrupted)."""
    code = (getattr(error, "sqlite_errorcode", 0) or 0) & 0xFF
    if code in {sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB}:
        integrity._report_corruption(db_path, str(error))
        return True
    return False


def _scan_pages(db_path: str, unit: dict, deadline: float) -> bool:
    """Sequentially read the file from the saved offset; True when finished."""
    descriptor = os.open(db_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return False
        size = os.fstat(descriptor).st_size
        offset = min(unit.get("offset", 0), size)
        while offset < size:
            if time.monotonic() > deadline:
                unit["offset"] = offset
                return False
            started = time.monotonic()
            data = os.pread(descriptor, _CHUNK_BYTES, offset)
            if not data:
                break
            offset += len(data)
            # ~50% duty cycle: never saturate shared storage.
            time.sleep(min(time.monotonic() - started, 1.0))
        unit["offset"] = offset
        if offset < size:
            msg = f"file shorter than its size on disk ({offset} < {size})"
            raise sqlite3.DatabaseError(msg)
        return True
    finally:
        os.close(descriptor)


def _header_problem(conn: sqlite3.Connection, db_path: str) -> str | None:
    pages = conn.execute("PRAGMA page_count").fetchone()[0]
    size = conn.execute("PRAGMA page_size").fetchone()[0]
    free = conn.execute("PRAGMA freelist_count").fetchone()[0]
    on_disk = Path(db_path).stat().st_size
    wal = Path(f"{db_path}-wal")
    if wal.exists() and wal.stat().st_size:
        return None  # pages may exist only in the WAL; the size test would lie
    if pages * size > on_disk:
        return f"header page_count*page_size={pages * size} exceeds file size {on_disk}"
    if free > pages:
        return f"freelist_count {free} exceeds page_count {pages}"
    return None


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _scan_rows(
    conn: sqlite3.Connection, table: str, unit: dict, deadline: float
) -> bool:
    """Read every record of ``table`` by rowid range; resumable via the cursor."""
    columns = [row[1] for row in conn.execute(f"PRAGMA table_info({_quote(table)})")]
    if conn.execute(
        "SELECT 1 FROM pragma_index_list(?) WHERE origin='pk' AND name LIKE 'sqlite_autoindex%'",
        [table],
    ).fetchone():
        # WITHOUT ROWID tables have no rowid cursor; they must finish whole.
        return False
    # `|| ''` forces the whole value (including overflow pages) to be read.
    width = " + ".join(f"coalesce(length({_quote(c)} || ''), 0)" for c in columns)
    sql = (
        f"SELECT max(r), count(*) FROM (SELECT rowid AS r, {width} AS w "  # noqa: S608
        f"FROM {_quote(table)} WHERE rowid > ? ORDER BY rowid LIMIT {_ROW_CHUNK})"
    )
    cursor = unit.get("row_cursor", -(2**63))
    while True:
        if time.monotonic() > deadline:
            unit["row_cursor"] = cursor
            return False
        last, count = conn.execute(sql, [cursor]).fetchone()
        if not count:
            unit["row_cursor"] = cursor
            return True
        cursor = last


def _interrupted(error: sqlite3.OperationalError) -> bool:
    if "interrupt" not in str(error).lower():
        raise error
    return True


def _check_table(
    conn, db_path: str, table: str, unit: dict, slice_deadline: float
) -> bool:
    """Verify one table; True when it is finished this slice."""
    if unit.get("mode") != "rows" and "quick_done" not in unit:
        unit_deadline = time.monotonic() + UNIT_SECONDS
        try:
            with _guarded(conn, min(slice_deadline, unit_deadline)):
                result = conn.execute(f"PRAGMA quick_check({_quote(table)})").fetchall()
        except sqlite3.OperationalError as error:
            _interrupted(error)
            if unit_deadline < slice_deadline:
                unit["mode"] = "rows"  # unit budget exhausted, not the slice
            return False
        if result != [("ok",)]:
            integrity._report_corruption(
                db_path, f"quick_check({table}): {result[0][0]}"
            )
            raise sqlite3.DatabaseError(result[0][0])
        unit["quick_done"] = True
    if unit.get("mode") == "rows" and "rows_done" not in unit:
        try:
            with _guarded(conn, slice_deadline):
                if not _scan_rows(conn, table, unit, slice_deadline):
                    return False
        except sqlite3.OperationalError as error:
            _interrupted(error)
            return False
        unit["rows_done"] = True
    if "fk_done" not in unit:
        try:
            with _guarded(conn, slice_deadline):
                incident = integrity._inspect_foreign_keys(conn, only_table=table)
        except sqlite3.OperationalError as error:
            _interrupted(error)
            unit["fk_incomplete"] = True  # not resumable; retried next slice
            return False
        if incident["total_conflicts"]:
            integrity._write_incident_report(db_path, incident, status="blocked")
            msg = f"foreign-key conflicts in {table}; no live rows changed"
            raise sqlite3.IntegrityError(msg)
        unit["fk_done"] = True
        unit.pop("fk_incomplete", None)
    return True


def run_slice(db_path: str) -> dict:
    """Do one bounded slice of verification; returns the persisted state."""
    started = time.monotonic()
    state = _load(db_path)
    now = _now()
    state["slices"] = [s for s in state.get("slices", []) if now - s[0] < _DAY]
    budget = DAILY_BUDGET_SECONDS - sum(s[1] for s in state["slices"])
    if budget < _MIN_BUDGET:
        state["status"] = "waiting-budget"
        _save(db_path, state)
        return state
    slice_deadline = started + min(SLICE_SECONDS, budget)
    lock_descriptor = os.open(
        f"{db_path}.verification.lock", os.O_RDWR | os.O_CREAT, 0o600
    )
    with os.fdopen(lock_descriptor, "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            state["status"] = "another-verifier-running"
            return state
        state["status"] = "running"
        try:
            with closing(
                sqlite3.connect(
                    f"{Path(db_path).resolve().as_uri()}?mode=ro",
                    uri=True,
                    timeout=5,
                    check_same_thread=False,
                )
            ) as conn:
                conn.execute("PRAGMA cache_size=-65536")
                conn.execute("PRAGMA mmap_size=0")
                tables = sorted(
                    r[0]
                    for r in conn.execute(
                        "SELECT name FROM sqlite_schema WHERE type='table' "
                        "AND name NOT LIKE 'sqlite_%'"
                    )
                )
                units = state["units"]
                for name in [_PAGES, *tables]:
                    units.setdefault(name, {})
                for name in list(units):
                    if name not in {_PAGES, *tables}:
                        del units[name]
                problem = _header_problem(conn, db_path)
                if problem:
                    integrity._report_corruption(db_path, problem)
                    state["status"] = "failed"
                    state["error"] = problem
                    return state
                due = sorted(
                    (n for n in units if _age(units[n]) > REVERIFY_SECONDS),
                    key=lambda n: (-_age(units[n]), n != _PAGES, n),
                )
                for name in due:
                    if time.monotonic() >= slice_deadline:
                        break
                    unit = units[name]
                    if _age(unit) <= REVERIFY_SECONDS:
                        continue
                    if name == _PAGES:
                        finished = _scan_pages(db_path, unit, slice_deadline)
                    else:
                        finished = _check_table(
                            conn, db_path, name, unit, slice_deadline
                        )
                    if finished:
                        keep = {"mode": unit.get("mode")} if unit.get("mode") else {}
                        units[name] = {**keep, "verified_at": _stamp()}
                    _save(db_path, state)
                _summarize(state)
                state["status"] = "partial" if state["unverified_units"] else "ok"
        except sqlite3.DatabaseError as error:
            state["status"] = "failed"
            state["error"] = str(error)
            _fail(db_path, error)
            if isinstance(error, sqlite3.IntegrityError):
                state["status"] = "blocked"
        finally:
            state["slices"].append([now, time.monotonic() - started])
            _save(db_path, state)
    return state
