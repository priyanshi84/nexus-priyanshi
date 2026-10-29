import contextlib
import importlib.util
import io
import os
import sqlite3
import sys
import types
import unittest
from types import SimpleNamespace
from unittest import mock


# ---------------------------------------------------------------------------
# In-memory fakes for the project's database module (stand-in in sys.modules)
# ---------------------------------------------------------------------------

class _StopLoop(Exception):
    """Raised by the fake sleep to break out of process_jobs' infinite loop."""


class _FakeConnection:
    """Wraps a shared in-memory sqlite connection; close() is a no-op."""

    def __init__(self, real):
        self._real = real

    def execute(self, *args, **kwargs):
        return self._real.execute(*args, **kwargs)

    def commit(self):
        self._real.commit()

    def rollback(self):
        self._real.rollback()

    def close(self):
        pass


_STATE = {"connection": None, "system_state": {}}


def _fake_get_connection():
    return _FakeConnection(_STATE["connection"])


def _fake_get_system_state(key, default=None):
    return _STATE["system_state"].get(key, default)


_database_pkg = types.ModuleType("database")
_database_mod = types.ModuleType("database.database")
_database_mod.get_connection = _fake_get_connection
_database_mod.get_system_state = _fake_get_system_state
_database_pkg.database = _database_mod
sys.modules["database"] = _database_pkg
sys.modules["database.database"] = _database_mod


def _load_worker():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workers", "worker.py")
    spec = importlib.util.spec_from_file_location("worker_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


worker = _load_worker()


class WorkerTests(unittest.TestCase):
    def setUp(self):
        connection = sqlite3.connect(":memory:", check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute(
            """
            CREATE TABLE jobs (
                id TEXT PRIMARY KEY,
                type TEXT,
                body TEXT,
                status TEXT,
                attempts INTEGER,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT,
                event_type TEXT,
                reason TEXT,
                created_at TEXT
            )
            """
        )
        connection.commit()
        self.connection = connection
        _STATE["connection"] = connection
        _STATE["system_state"] = {}

    def tearDown(self):
        self.connection.close()
        _STATE["connection"] = None
        _STATE["system_state"] = {}

    # helpers -------------------------------------------------------------

    def _add_job(self, job_id="job-1", status="QUEUED", attempts=0):
        self.connection.execute(
            "INSERT INTO jobs (id, type, body, status, attempts, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (job_id, "email", "hello", status, attempts, "2024-01-01T00:00:00", "2024-01-01T00:00:00"),
        )
        self.connection.commit()

    def _job(self, job_id="job-1"):
        return self.connection.execute(
            "SELECT * FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()

    def _event_types(self, job_id="job-1"):
        rows = self.connection.execute(
            "SELECT event_type FROM events WHERE job_id = ? ORDER BY id", (job_id,)
        ).fetchall()
        return [r["event_type"] for r in rows]

    def _run_loop(self):
        """Run process_jobs until it idles (sleep(0.5)) and then stop it."""
        sleeps = []

        def fake_sleep(seconds):
            sleeps.append(seconds)
            if seconds == 0.5:
                raise _StopLoop()

        fake_time = SimpleNamespace(sleep=fake_sleep)
        with mock.patch.object(worker, "time", fake_time):
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(_StopLoop):
                    worker.process_jobs()
        return sleeps

    # tests ---------------------------------------------------------------

    def test_record_event_inserts_row(self):
        before = self.connection.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"]
        self.assertEqual(before, 0)

        worker.record_event("job-9", "RUNNING", "some reason")

        rows = self.connection.execute("SELECT * FROM events").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["job_id"], "job-9")
        self.assertEqual(rows[0]["event_type"], "RUNNING")
        self.assertEqual(rows[0]["reason"], "some reason")
        self.assertTrue(rows[0]["created_at"])

    def test_worker_running_flag(self):
        # Default is running.
        self.assertTrue(worker.is_worker_running())
        _STATE["system_state"]["worker_running"] = "false"
        self.assertFalse(worker.is_worker_running())
        _STATE["system_state"]["worker_running"] = "TRUE"
        self.assertTrue(worker.is_worker_running())

    def test_failure_mode_flag(self):
        # Default is enabled.
        self.assertTrue(worker.is_failure_mode_enabled())
        _STATE["system_state"]["fail_mode"] = "false"
        self.assertFalse(worker.is_failure_mode_enabled())
        _STATE["system_state"]["fail_mode"] = "True"
        self.assertTrue(worker.is_failure_mode_enabled())

    def test_process_jobs_success_when_failure_mode_off(self):
        _STATE["system_state"]["fail_mode"] = "false"
        self._add_job()
        self.assertEqual(self._job()["status"], "QUEUED")
        self.assertEqual(self._job()["attempts"], 0)

        self._run_loop()

        job = self._job()
        self.assertEqual(job["status"], "SUCCESS")
        self.assertEqual(job["attempts"], 1)
        self.assertEqual(self._event_types(), ["RUNNING", "SUCCESS"])

    def test_process_jobs_retries_then_dead_when_failure_mode_on(self):
        _STATE["system_state"]["fail_mode"] = "true"
        self._add_job()

        self._run_loop()

        job = self._job()
        self.assertEqual(job["status"], "DEAD")
        self.assertEqual(job["attempts"], worker.MAX_ATTEMPTS)
        self.assertEqual(
            self._event_types(),
            ["RUNNING", "FAILED", "RUNNING", "FAILED", "RUNNING", "DEAD"],
        )

    def test_process_jobs_does_nothing_when_worker_stopped(self):
        _STATE["system_state"]["worker_running"] = "false"
        self._add_job()

        sleeps = self._run_loop()

        self.assertEqual(sleeps, [0.5])
        job = self._job()
        self.assertEqual(job["status"], "QUEUED")
        self.assertEqual(job["attempts"], 0)
        self.assertEqual(self._event_types(), [])


if __name__ == "__main__":
    unittest.main()
