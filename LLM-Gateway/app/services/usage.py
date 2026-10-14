import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = Path("data/gateway.db")

# USD per 1 million tokens.
# Learning-project rates, not live billing data.
MODEL_PRICES = {
    "gpt-4.1-mini": {
        "input": 0.40,
        "output": 1.60,
    }
}


def estimate_cost(
    provider: str | None,
    model: str | None,
    prompt_tokens: int | None,
    completion_tokens: int | None
) -> float | None:

    if prompt_tokens is None or completion_tokens is None:
        return None

    if provider == "OllamaProvider":
        return 0.0

    prices = MODEL_PRICES.get(model)

    if prices is None:
        return None

    return (
        prompt_tokens * prices["input"]
        + completion_tokens * prices["output"]
    ) / 1_000_000


def _init_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        conn.execute("PRAGMA journal_mode=WAL")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS gateway_usage (
                request_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                requested_model TEXT NOT NULL,
                actual_provider TEXT,
                actual_model TEXT,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                estimated_cost_usd REAL,
                latency_ms INTEGER,
                status TEXT NOT NULL
            )
        """)


async def init_database():
    await asyncio.to_thread(_init_database)


def _save_usage(record: dict):
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        conn.execute("""
            INSERT INTO gateway_usage (
                request_id,
                created_at,
                requested_model,
                actual_provider,
                actual_model,
                prompt_tokens,
                completion_tokens,
                estimated_cost_usd,
                latency_ms,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record["request_id"],
            datetime.now(timezone.utc).isoformat(),
            record["requested_model"],
            record["actual_provider"],
            record["actual_model"],
            record["prompt_tokens"],
            record["completion_tokens"],
            record["estimated_cost_usd"],
            record["latency_ms"],
            record["status"]
        ))


async def save_usage(record: dict):
    await asyncio.to_thread(_save_usage, record)


def _get_usage(limit: int):
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute("""
            SELECT *
            FROM gateway_usage
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,)).fetchall()

        return [dict(row) for row in rows]


async def get_usage(limit: int = 20):
    return await asyncio.to_thread(_get_usage, limit)