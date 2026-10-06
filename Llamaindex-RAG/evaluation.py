import json
from pathlib import Path

from src.loader import load_incidents
from src.indexer import create_index


TOP_K = 3


def load_evaluation_dataset():
    file_path = (
        Path(__file__).resolve().parent
        / "data"
        / "evaluation_dataset.json"
    )

    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def evaluate():

    # Build the vector index
    documents = load_incidents()
    index = create_index(documents)

    # Retrieval only — no LLM needed
    retriever = index.as_retriever(
        similarity_top_k=TOP_K
    )

    test_cases = load_evaluation_dataset()

    total_recall = 0
    total_hits = 0
    total_reciprocal_rank = 0

    for test in test_cases:

        query = test["query"]
        expected = set(test["expected_incidents"])

        results = retriever.retrieve(query)

        retrieved = [
            result.metadata["incident_id"]
            for result in results
        ]

        retrieved_set = set(retrieved)

        relevant_retrieved = expected.intersection(
            retrieved_set
        )

        # -----------------------------
        # Recall@K
        # -----------------------------
        recall = len(relevant_retrieved) / len(expected)

        # -----------------------------
        # Hit Rate@K
        # -----------------------------
        hit = 1 if relevant_retrieved else 0

        # -----------------------------
        # Reciprocal Rank
        # -----------------------------
        reciprocal_rank = 0

        for rank, incident_id in enumerate(
            retrieved,
            start=1
        ):
            if incident_id in expected:
                reciprocal_rank = 1 / rank
                break

        total_recall += recall
        total_hits += hit
        total_reciprocal_rank += reciprocal_rank

        print("\n--------------------------------")
        print(f"Query: {query}")
        print(f"Expected: {sorted(expected)}")
        print(f"Retrieved: {retrieved}")

        print(
            f"Recall@{TOP_K}: "
            f"{recall:.2f}"
        )

        print(
            f"Hit@{TOP_K}: "
            f"{hit}"
        )

        print(
            f"Reciprocal Rank: "
            f"{reciprocal_rank:.2f}"
        )

    # -----------------------------
    # Aggregate Metrics
    # -----------------------------
    number_of_tests = len(test_cases)

    average_recall = (
        total_recall / number_of_tests
    )

    hit_rate = (
        total_hits / number_of_tests
    )

    mrr = (
        total_reciprocal_rank / number_of_tests
    )

    print("\n================================")
    print("RETRIEVAL EVALUATION")
    print("================================")

    print(
        f"Average Recall@{TOP_K}: "
        f"{average_recall:.2f}"
    )

    print(
        f"Hit Rate@{TOP_K}: "
        f"{hit_rate:.2f}"
    )

    print(
        f"MRR: "
        f"{mrr:.2f}"
    )


if __name__ == "__main__":
    evaluate()