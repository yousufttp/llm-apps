import hashlib
import json
import math
import os
import sqlite3
from pathlib import Path
from typing import Any

from openai import OpenAI

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_FAQ_PATH = "mock_telecom_faq.json"
DEFAULT_VECTOR_DB_PATH = "faq_vectors.sqlite"
DEFAULT_MIN_SIMILARITY = 0.60


def embedding_model() -> str:
    return os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)


def faq_path() -> Path:
    return Path(os.getenv("FAQ_DATA_PATH", DEFAULT_FAQ_PATH))


def vector_db_path() -> Path:
    return Path(os.getenv("FAQ_VECTOR_DB_PATH", DEFAULT_VECTOR_DB_PATH))


def load_faqs(path: Path | None = None) -> list[dict[str, str]]:
    source = path or faq_path()
    with source.open(encoding="utf-8") as file:
        records = json.load(file)
    if not isinstance(records, list):
        raise ValueError("FAQ data must be a JSON array.")
    required = {"id", "category", "subcategory", "question", "answer"}
    for record in records:
        if not isinstance(record, dict) or not required.issubset(record):
            raise ValueError("Every FAQ record must contain id, category, subcategory, question, and answer.")
    return records


def embedding_text(record: dict[str, str]) -> str:
    # Each short question-and-answer record is already a natural chunk for this dataset.
    return "\n".join([
        f"Category: {record['category']}",
        f"Subcategory: {record['subcategory']}",
        f"Question: {record['question']}",
        f"Answer: {record['answer']}",
    ])


def content_hash(record: dict[str, str]) -> str:
    return hashlib.sha256(embedding_text(record).encode("utf-8")).hexdigest()


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Vectors must have the same dimension.")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


def _connect(path: Path | None = None) -> sqlite3.Connection:
    connection = sqlite3.connect(path or vector_db_path(), timeout=30)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=30000")
    return connection


def initialize_vector_cache(path: Path | None = None) -> None:
    with _connect(path) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS faq_embeddings (
            faq_id TEXT NOT NULL,
            embedding_model TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            dimension INTEGER NOT NULL,
            embedding TEXT NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (faq_id, embedding_model)
        )""")


def _embed(client: OpenAI, text: str, model: str) -> list[float]:
    response = client.embeddings.create(model=model, input=text)
    return list(response.data[0].embedding)


def sync_embeddings(
    client: OpenAI,
    records: list[dict[str, str]] | None = None,
    force_refresh: bool = False,
    db_path: Path | None = None,
) -> dict[str, Any]:
    records = records if records is not None else load_faqs()
    model = embedding_model()
    initialize_vector_cache(db_path)
    current_ids = {record["id"] for record in records}
    statuses: list[dict[str, str]] = []
    vectors: list[dict[str, Any]] = []

    with _connect(db_path) as connection:
        cached = {
            row[0]: row for row in connection.execute(
                "SELECT faq_id, content_hash, dimension, embedding FROM faq_embeddings "
                "WHERE embedding_model = ?", (model,)
            ).fetchall()
        }
        for record in records:
            faq_id = record["id"]
            current_hash = content_hash(record)
            row = cached.get(faq_id)
            vector = None
            status = "cache_hit"
            if not force_refresh and row and row[1] == current_hash:
                candidate = json.loads(row[3])
                if len(candidate) == row[2] and candidate:
                    vector = candidate
            if vector is None:
                vector = _embed(client, embedding_text(record), model)
                status = "regenerated"
                connection.execute(
                    """INSERT INTO faq_embeddings
                    (faq_id, embedding_model, content_hash, dimension, embedding,
                     category, subcategory, question, answer)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(faq_id, embedding_model) DO UPDATE SET
                    content_hash=excluded.content_hash, dimension=excluded.dimension,
                    embedding=excluded.embedding, category=excluded.category,
                    subcategory=excluded.subcategory, question=excluded.question,
                    answer=excluded.answer, updated_at=CURRENT_TIMESTAMP""",
                    (faq_id, model, current_hash, len(vector), json.dumps(vector),
                     record["category"], record["subcategory"], record["question"], record["answer"]),
                )
            vectors.append({**record, "embedding": vector})
            statuses.append({"faq_id": faq_id, "status": status})

        stale_rows = connection.execute(
            "SELECT faq_id FROM faq_embeddings WHERE embedding_model = ?",
            (model,),
        ).fetchall()
        for (faq_id,) in stale_rows:
            if faq_id not in current_ids:
                connection.execute(
                    "DELETE FROM faq_embeddings WHERE faq_id = ? AND embedding_model = ?",
                    (faq_id, model),
                )
                statuses.append({"faq_id": faq_id, "status": "removed/stale"})

    return {"records": vectors, "model": model, "statuses": statuses}


def retrieve_faqs(
    client: OpenAI,
    query: str,
    category: str,
    top_k: int = 3,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
    index: dict[str, Any] | None = None,
) -> dict[str, Any]:
    index = index or sync_embeddings(client)
    query_vector = _embed(client, query, index["model"])
    candidates = [record for record in index["records"] if record["category"] == category]
    results = []
    for record in candidates:
        vector = record["embedding"]
        if len(vector) != len(query_vector):
            continue
        score = cosine_similarity(query_vector, vector)
        if score >= min_similarity:
            results.append({key: record[key] for key in (
                "id", "category", "subcategory", "question", "answer")}
                           | {"similarity": score})
    results.sort(key=lambda item: item["similarity"], reverse=True)
    return {
        "records": results[:top_k],
        "category": category,
        "query": query,
        "model": index["model"],
        "statuses": index["statuses"],
    }
