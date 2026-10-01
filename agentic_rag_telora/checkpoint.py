import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

DATABASE_PATH = Path(__file__).with_name("chat_checkpoints.sqlite")


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH, timeout=30, check_same_thread=False)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=30000")
    return connection


def initialize_database() -> None:
    with _connect() as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS checkpoints (
            thread_id TEXT PRIMARY KEY, title TEXT, messages TEXT NOT NULL, route TEXT,
            customer_name TEXT, mobile_number TEXT, address TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        connection.execute("""CREATE TABLE IF NOT EXISTS feedback (
            request_id TEXT PRIMARY KEY, thread_id TEXT NOT NULL,
            original_question TEXT NOT NULL, follow_up TEXT,
            faq_ids TEXT NOT NULL, similarity_scores TEXT NOT NULL,
            satisfied INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        columns = {row[1] for row in connection.execute("PRAGMA table_info(checkpoints)")}
        if "title" not in columns:
            connection.execute("ALTER TABLE checkpoints ADD COLUMN title TEXT")
        if "created_at" not in columns:
            connection.execute("ALTER TABLE checkpoints ADD COLUMN created_at TEXT")
            connection.execute(
                "UPDATE checkpoints SET created_at = COALESCE(updated_at, CURRENT_TIMESTAMP) "
                "WHERE created_at IS NULL"
            )
        null_thread_rows = connection.execute(
            "SELECT rowid FROM checkpoints WHERE thread_id IS NULL"
        ).fetchall()
        for (row_id,) in null_thread_rows:
            connection.execute(
                "UPDATE checkpoints SET thread_id = ? WHERE rowid = ?",
                (str(uuid.uuid4()), row_id),
            )


def list_sessions() -> list[dict[str, str | None]]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT thread_id, title, messages, COALESCE(created_at, updated_at), updated_at "
            "FROM checkpoints WHERE thread_id IS NOT NULL ORDER BY updated_at DESC"
        ).fetchall()
    sessions = [
        {
            "thread_id": row[0],
            "title": row[1] or _title_from_messages(row[2]),
            "created_at": row[3],
            "updated_at": row[4],
        }
        for row in rows
    ]
    unique_sessions = []
    seen_titles = set()
    for session in sessions:
        title = session["title"] or "New conversation"
        if title in seen_titles:
            continue
        seen_titles.add(title)
        unique_sessions.append(session)
    return unique_sessions


def _title_from_messages(messages_json: str) -> str:
    for message in json.loads(messages_json):
        if message.get("role") == "user" and message.get("content"):
            return message["content"].strip()[:80]
    return "New conversation"


def _encrypt(value: str | None, cipher: Fernet) -> str | None:
    return cipher.encrypt(value.encode()).decode() if value else None


def _decrypt(value: str | None, cipher: Fernet) -> str | None:
    return cipher.decrypt(value.encode()).decode() if value else None


def load_checkpoint(thread_id: str, cipher: Fernet) -> dict[str, Any]:
    with _connect() as connection:
        row = connection.execute(
            "SELECT messages, route, customer_name, mobile_number, address, title "
            "FROM checkpoints WHERE thread_id = ?", (thread_id,)
        ).fetchone()
    if not row:
        return {"messages": [], "route": None, "pii": {}}
    return {"title": row[5] or _title_from_messages(row[0]),
            "messages": json.loads(row[0]), "route": row[1], "pii": {
        "customer_name": _decrypt(row[2], cipher),
        "mobile_number": _decrypt(row[3], cipher),
        "address": _decrypt(row[4], cipher),
    }}


def save_checkpoint(thread_id: str, title: str, messages: list[dict[str, str]], route: str,
                    pii: dict[str, str | None], cipher: Fernet) -> None:
    with _connect() as connection:
        connection.execute("""INSERT INTO checkpoints
            (thread_id, title, messages, route, customer_name, mobile_number, address)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(thread_id) DO UPDATE SET messages=excluded.messages,
            title=COALESCE(checkpoints.title, excluded.title),
            route=excluded.route, customer_name=excluded.customer_name,
            mobile_number=excluded.mobile_number, address=excluded.address,
            updated_at=CURRENT_TIMESTAMP""", (
                thread_id, title, json.dumps(messages), route,
                _encrypt(pii.get("customer_name"), cipher),
                _encrypt(pii.get("mobile_number"), cipher),
                _encrypt(pii.get("address"), cipher),
            ))


def save_feedback(request_id: str, thread_id: str, original_question: str,
                  follow_up: str | None, faq_ids: list[str],
                  similarity_scores: list[float], satisfied: bool) -> None:
    with _connect() as connection:
        connection.execute(
            """INSERT OR IGNORE INTO feedback
            (request_id, thread_id, original_question, follow_up, faq_ids,
             similarity_scores, satisfied)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (request_id, thread_id, original_question, follow_up,
             json.dumps(faq_ids), json.dumps(similarity_scores), int(satisfied)),
        )


def update_feedback_follow_up(request_id: str, follow_up: str,
                              faq_ids: list[str], similarity_scores: list[float]) -> None:
    with _connect() as connection:
        connection.execute(
            "UPDATE feedback SET follow_up = ?, faq_ids = ?, similarity_scores = ? "
            "WHERE request_id = ?",
            (follow_up, json.dumps(faq_ids), json.dumps(similarity_scores), request_id),
        )
