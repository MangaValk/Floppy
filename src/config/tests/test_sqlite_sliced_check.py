"""The background verifier is sliced, resumable and bounded per day."""

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from config import sqlite_integrity as integrity
from config import sqlite_sliced_check as sliced


class SlicedCheckTests(TestCase):
    def setUp(self):
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(directory, True))
        self.database = str(directory / "db.sqlite3")
        with sqlite3.connect(self.database) as db:
            db.executescript(
                "CREATE TABLE parent(id INTEGER PRIMARY KEY);"
                "CREATE TABLE child(id INTEGER PRIMARY KEY, "
                "parent_id INTEGER REFERENCES parent(id), note TEXT);"
                "INSERT INTO parent VALUES (1);"
            )
            db.executemany(
                "INSERT INTO child VALUES (?, 1, ?)",
                [(i, "x" * 3000) for i in range(1, 400)],
            )

    def progress(self):
        return json.loads(
            Path(f"{self.database}.verification.progress.json").read_text()
        )

    def test_clean_database_completes_and_reports_verified_through(self):
        state = sliced.run_slice(self.database)
        self.assertEqual(state["status"], "ok")
        self.assertEqual(state["unverified_units"], [])
        self.assertTrue(state["verified_through"])
        self.assertEqual(
            sliced.run_slice(self.database)["status"], "ok"
        )  # fresh: no work

    def test_image_change_does_not_restart_verification(self):
        sliced.run_slice(self.database)
        with patch.dict("os.environ", {"COMMIT_SHA": "another-image"}):
            with patch.object(sliced, "_check_table") as check:
                sliced.run_slice(self.database)
        check.assert_not_called()

    def test_expired_slice_resumes_without_redoing_finished_units(self):
        with patch.object(sliced, "SLICE_SECONDS", 0.0001):
            first = sliced.run_slice(self.database)
        self.assertEqual(first["status"], "partial")
        done = {n for n, u in first["units"].items() if u.get("verified_at")}
        with patch.object(sliced, "_scan_pages", wraps=sliced._scan_pages) as pages:
            final = sliced.run_slice(self.database)
        self.assertEqual(final["status"], "ok")
        if sliced._PAGES in done:
            pages.assert_not_called()

    def test_unit_over_budget_falls_back_to_resumable_row_reads(self):
        class SlowQuickCheck:
            """Real connection, but quick_check always runs out of time."""

            def __init__(self, conn):
                self.conn = conn

            def execute(self, sql, *args):
                if "quick_check" in sql:
                    raise sqlite3.OperationalError("interrupted")
                return self.conn.execute(sql, *args)

            def __getattr__(self, name):
                return getattr(self.conn, name)

        conn = sqlite3.connect(self.database, check_same_thread=False)
        self.addCleanup(conn.close)
        unit = {}
        far = __import__("time").monotonic() + 1000
        self.assertFalse(
            sliced._check_table(SlowQuickCheck(conn), self.database, "child", unit, far)
        )
        self.assertEqual(unit["mode"], "rows")
        self.assertTrue(
            sliced._check_table(SlowQuickCheck(conn), self.database, "child", unit, far)
        )
        self.assertTrue(unit["rows_done"])

    def test_daily_budget_caps_total_work(self):
        with patch.object(sliced, "DAILY_BUDGET_SECONDS", 0.0):
            state = sliced.run_slice(self.database)
        self.assertEqual(state["status"], "waiting-budget")

    def test_damaged_page_publishes_a_corruption_incident(self):
        with Path(self.database).open("r+b") as handle:
            handle.seek(4096 * 3)
            handle.write(b"\xff" * 64)
        state = sliced.run_slice(self.database)
        self.assertEqual(state["status"], "failed")
        report = integrity._read_incident_report(self.database)
        self.assertEqual(report["status"], "corrupt")

    def test_foreign_key_conflict_blocks_without_touching_rows(self):
        with sqlite3.connect(self.database) as db:
            db.execute("INSERT INTO child VALUES (9999, 77, 'orphan')")
        state = sliced.run_slice(self.database)
        self.assertEqual(state["status"], "blocked")
        self.assertEqual(
            integrity._read_incident_report(self.database)["status"], "blocked"
        )
        with sqlite3.connect(self.database) as db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM child").fetchone()[0], 400
            )

    def test_replaced_database_file_discards_old_progress(self):
        sliced.run_slice(self.database)
        Path(self.database).rename(f"{self.database}.old")
        with sqlite3.connect(self.database) as db:
            db.execute("CREATE TABLE t(id INTEGER)")
        state = sliced.run_slice(self.database)
        self.assertEqual(set(state["units"]), {sliced._PAGES, "t"})
