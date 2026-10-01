import json
from pathlib import Path

import retrieval


class FakeEmbeddings:
    def create(self, *, model, input):
        class Item:
            embedding = [1.0, 0.0] if "activation" in input.lower() else [0.0, 1.0]

        class Response:
            data = [Item()]

        return Response()


class FakeClient:
    embeddings = FakeEmbeddings()


def test_cosine_similarity():
    assert retrieval.cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert retrieval.cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_content_hash_changes_when_embedded_content_changes():
    record = {"id": "A", "category": "activation", "subcategory": "sim",
              "question": "How?", "answer": "Do this."}
    original = retrieval.content_hash(record)
    record["answer"] = "Do something else."
    assert retrieval.content_hash(record) != original


def test_retrieval_filters_category_before_ranking():
    index = {
        "model": "test-model",
        "statuses": [],
        "records": [
            {"id": "ACT-1", "category": "activation", "subcategory": "sim",
             "question": "Activate", "answer": "Activate it.", "embedding": [1.0, 0.0]},
            {"id": "OTH-1", "category": "others", "subcategory": "billing",
             "question": "Bill", "answer": "View it.", "embedding": [1.0, 0.0]},
        ],
    }
    result = retrieval.retrieve_faqs(FakeClient(), "activation", "activation", 3, 0.5, index)
    assert [record["id"] for record in result["records"]] == ["ACT-1"]


def test_deleted_faq_is_removed_from_cache(tmp_path: Path):
    db_path = tmp_path / "vectors.sqlite"
    records = [{"id": "A", "category": "activation", "subcategory": "sim",
                "question": "How?", "answer": "Do this."}]
    client = FakeClient()
    retrieval.sync_embeddings(client, records, db_path=db_path)
    retrieval.sync_embeddings(client, [], db_path=db_path)
    with retrieval._connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM faq_embeddings").fetchone()[0] == 0
