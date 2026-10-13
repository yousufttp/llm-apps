import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator
from config import settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS tira_incident_runs (
          run_id TEXT PRIMARY KEY, thread_id TEXT UNIQUE NOT NULL, incident_id TEXT NOT NULL, status TEXT NOT NULL,
          started_at TEXT NOT NULL, completed_at TEXT, root_cause TEXT, resolved INTEGER NOT NULL DEFAULT 0);
        CREATE INDEX IF NOT EXISTS idx_tira_incident_runs_incident ON tira_incident_runs(incident_id);
        CREATE TABLE IF NOT EXISTS tira_remediation_operations (
          id INTEGER PRIMARY KEY AUTOINCREMENT, idempotency_key TEXT UNIQUE NOT NULL, run_id TEXT NOT NULL, incident_id TEXT NOT NULL,
          root_cause TEXT NOT NULL, status TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tira_evaluation_results (
          id INTEGER PRIMARY KEY AUTOINCREMENT, experiment_name TEXT NOT NULL, incident_id TEXT NOT NULL,
          metric_name TEXT NOT NULL, metric_value REAL NOT NULL, details TEXT, created_at TEXT NOT NULL);
        """)


def create_run(run_id, thread_id, incident_id):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO tira_incident_runs(run_id,thread_id,incident_id,status,started_at) VALUES(?,?,?,'running',?)",
            (run_id, thread_id, incident_id, utc_now()),
        )


def mark_run_status(run_id, status, *, resolved=False, root_cause=""):
    completed_at = utc_now() if status in {"completed", "rejected", "failed"} else None
    with get_connection() as conn:
        conn.execute(
            "UPDATE tira_incident_runs SET status=?,resolved=?,root_cause=?,completed_at=COALESCE(?,completed_at) WHERE run_id=?",
            (status, int(resolved), root_cause, completed_at, run_id),
        )


def save_evaluation_result(
    experiment_name, incident_id, metric_name, metric_value, details=""
):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO tira_evaluation_results(experiment_name,incident_id,metric_name,metric_value,details,created_at) VALUES(?,?,?,?,?,?)",
            (
                experiment_name,
                incident_id,
                metric_name,
                metric_value,
                details,
                utc_now(),
            ),
        )
