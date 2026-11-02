import contextlib
import importlib.util
import io
import os
import sqlite3
import sys
import types
import unittest
from unittest import mock

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_STUBBED_NAMES = (
    "fastapi",
    "pydantic",
    "database",
    "database.database",
)
_ORIGINAL_MODULES = {name: sys.modules.get(name) for name in _STUBBED_NAMES}


# ---------------------------------------------------------------------------
# Stand-ins for third-party packages and project modules not in the repo.
# ---------------------------------------------------------------------------
class _FakeHTTPException(Exception):
    def __init__(self, status_code=500, detail=None):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class _FakeAPIRouter:
    def __init__(self, prefix="", tags=None):
        self.prefix = prefix
        self.tags = tags or []

    def _decorator(self, *args, **kwargs):
        def wrap(func):
            return func

        return wrap

    post = _decorator
    get = _decorator


class _FakeBaseModel:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def _fake_get_connection():
    raise RuntimeError("get_connection must be patched in tests")


def _fake_get_system_state(key, default=None):
    return default


fastapi_stub = types.ModuleType("fastapi")
fastapi_stub.APIRouter = _FakeAPIRouter
fastapi_stub.HTTPException = _FakeHTTPException

pydantic_stub = types.ModuleType("pydantic")
pydantic_stub.BaseModel = _FakeBaseModel

database_pkg_stub = types.ModuleType("database")
database_pkg_stub.__path__ = []
database_db_stub = types.ModuleType("database.database")
database_db_stub.get_connection = _fake_get_connection
database_db_stub.get_system_state = _fake_get_system_state
database_pkg_stub.database = database_db_stub

sys.modules["fastapi"] = fastapi_stub
sys.modules["pydantic"] = pydantic_stub
sys.modules["database"] = database_pkg_stub
sys.modules["database.database"] = database_db_stub


def _load(name, relpath):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(BACKEND_DIR, relpath)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


worker = _load("worker_under_test", os.path.join("workers", "worker.py"))
jobs = _load("jobs_under_test", os.path.join("api", "jobs.py"))


def tearDownModule():
    for name, original in _ORIGINAL_MODULES.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


# ---------------------------------------------------------------------------
# In-memory fakes
# ---------------------------------------------------------------------------
class _StopLoop(Exception):
    pass


class _SharedConnection:
    """Wraps one in-memory sqlite connection; close() is a no-op so that the
    code under test can open and close connections freely."""

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


def _make_database():
    real = sqlite3.connect(":memory:")
    real.row_factory = sqlite3.Row
    real.execute(
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
    real.execute(
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
    real.commit()
    return real


class WorkerLogicTests(unittest.TestCase):
    def setUp(self):
        self.real = _make_database()
        self.conn = _SharedConnection(self.real)
        self.state = {"worker_running": "true", "fail_mode": "true"}
        self.sleeps = []

        def fake_state(key, default=None):
            return self.state.get(key, default)

        def fake_sleep(seconds):
            self.sleeps.append(seconds)
            if seconds == 0.5:
                raise _StopLoop()

        patches = [
            mock.patch.object(worker, "get_connection", lambda: self.conn),
            mock.patch.object(worker, "get_system_state", fake_state),
            mock.patch.object(
                worker, "time", types.SimpleNamespace(sleep=fake_sleep)
            ),
            mock.patch.object(jobs, "get_connection", lambda: self.conn),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.real.close)

    def _add_job(self, job_id="job-1", status="QUEUED", attempts=0,
                 created_at="2024-01-01T00:00:00"):
        self.real.execute(
            "INSERT INTO jobs (id, type, body, status, attempts, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (job_id, "email", "hello", status, attempts, created_at, created_at),
        )
        self.real.commit()

    def _job(self, job_id="job-1"):
        return self.real.execute(
            "SELECT * FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()

    def _events(self, job_id="job-1"):
        rows = self.real.execute(
            "SELECT event_type, reason FROM events WHERE job_id = ? ORDER BY id",
            (job_id,),
        ).fetchall()
        return [(r["event_type"], r["reason"]) for r in rows]

    def _run_worker(self):
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(_StopLoop):
                worker.process_jobs()

    # -- worker helpers ----------------------------------------------------
    def test_record_event_inserts_row(self):
        worker.record_event("abc", "RUNNING", "some reason")
        row = self.real.execute("SELECT * FROM events").fetchone()
        self.assertEqual(row["job_id"], "abc")
        self.assertEqual(row["event_type"], "RUNNING")
        self.assertEqual(row["reason"], "some reason")
        self.assertTrue(row["created_at"])

    def test_state_flags_are_case_insensitive(self):
        self.state["worker_running"] = "TRUE"
        self.state["fail_mode"] = "False"
        self.assertTrue(worker.is_worker_running())
        self.assertFalse(worker.is_failure_mode_enabled())
        self.state["worker_running"] = "false"
        self.assertFalse(worker.is_worker_running())

    def test_state_flags_default_to_true(self):
        self.state.clear()
        self.assertTrue(worker.is_worker_running())
        self.assertTrue(worker.is_failure_mode_enabled())

    # -- worker loop -------------------------------------------------------
    def test_job_succeeds_when_failure_mode_off(self):
        self.state["fail_mode"] = "false"
        self._add_job()
        self._run_worker()
        job = self._job()
        self.assertEqual(job["status"], "SUCCESS")
        self.assertEqual(job["attempts"], 1)
        self.assertEqual([e[0] for e in self._events()], ["RUNNING", "SUCCESS"])

    def test_job_retries_then_dies_when_failure_mode_on(self):
        self._add_job()
        self._run_worker()
        job = self._job()
        self.assertEqual(job["status"], "DEAD")
        self.assertEqual(job["attempts"], worker.MAX_ATTEMPTS)
        self.assertEqual(
            [e[0] for e in self._events()],
            ["RUNNING", "FAILED", "RUNNING", "FAILED", "RUNNING", "DEAD"],
        )
        self.assertEqual(self.sleeps.count(2), worker.MAX_ATTEMPTS)

    def test_retry_wait_job_is_picked_up(self):
        self.state["fail_mode"] = "false"
        self._add_job(status="RETRY_WAIT", attempts=1)
        self._run_worker()
        job = self._job()
        self.assertEqual(job["status"], "SUCCESS")
        self.assertEqual(job["attempts"], 2)

    def test_paused_worker_does_not_touch_jobs(self):
        self.state["worker_running"] = "false"
        self._add_job()
        self._run_worker()
        job = self._job()
        self.assertEqual(job["status"], "QUEUED")
        self.assertEqual(job["attempts"], 0)
        self.assertEqual(self._events(), [])

    def test_oldest_job_is_processed_first(self):
        self.state["fail_mode"] = "false"
        self._add_job("newer", created_at="2024-02-01T00:00:00")
        self._add_job("older", created_at="2024-01-01T00:00:00")
        self._run_worker()
        first_event = self.real.execute(
            "SELECT job_id FROM events ORDER BY id LIMIT 1"
        ).fetchone()
        self.assertEqual(first_event["job_id"], "older")

    # -- jobs API ----------------------------------------------------------
    def test_create_job_queues_and_records_acceptance(self):
        result = jobs.create_job(jobs.JobCreate(id="j1", type="email", body="hi"))
        self.assertEqual(
            result,
            {"message": "Job accepted", "job_id": "j1", "status": "QUEUED"},
        )
        job = self._job("j1")
        self.assertEqual(job["status"], "QUEUED")
        self.assertEqual(job["attempts"], 0)
        self.assertEqual(self._events("j1"), [("ACCEPTED", "Job accepted by NEXUS")])

    def test_create_duplicate_job_returns_409(self):
        payload = jobs.JobCreate(id="dup", type="email", body="hi")
        jobs.create_job(payload)
        with self.assertRaises(_FakeHTTPException) as ctx:
            jobs.create_job(payload)
        self.assertEqual(ctx.exception.status_code, 409)
        count = self.real.execute(
            "SELECT COUNT(*) FROM jobs WHERE id = 'dup'"
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_get_jobs_orders_newest_first(self):
        self._add_job("a", created_at="2024-01-01T00:00:00")
        self._add_job("b", created_at="2024-03-01T00:00:00")
        result = jobs.get_jobs()
        self.assertEqual(result["count"], 2)
        self.assertEqual([j["id"] for j in result["jobs"]], ["b", "a"])
        self.assertEqual(result["jobs"][0]["status"], "QUEUED")

    def test_get_events_orders_oldest_first(self):
        self.real.execute(
            "INSERT INTO events (job_id, event_type, reason, created_at) "
            "VALUES ('x', 'LATE', 'r', '2024-02-01T00:00:00')"
        )
        self.real.execute(
            "INSERT INTO events (job_id, event_type, reason, created_at) "
            "VALUES ('x', 'EARLY', 'r', '2024-01-01T00:00:00')"
        )
        self.real.commit()
        result = jobs.get_events()
        self.assertEqual(result["count"], 2)
        self.assertEqual(
            [e["event_type"] for e in result["events"]], ["EARLY", "LATE"]
        )


if __name__ == "__main__":
    unittest.main()
