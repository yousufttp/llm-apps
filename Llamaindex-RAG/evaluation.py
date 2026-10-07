import json
from pathlib import Path

from llama_index.core.schema import QueryBundle

from src.loader import load_incidents
from src.indexer import create_index
from src.reranker import create_reranker


FINAL_TOP_K = 3
CANDIDATE_TOP_K = 10


def load_evaluation_dataset():
    file_path = (
        Path(__file__).resolve().parent
        / "data"
        / "evaluation_dataset.json"
    )

    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def calculate_metrics(retrieved, expected):
    retrieved_set = set(retrieved)

    relevant_retrieved = expected.intersection(
        retrieved_set
    )

    # Recall@K
    recall = (
        len(relevant_retrieved)
        / len(expected)
    )

    # Hit Rate@K
    hit = 1 if relevant_retrieved else 0

    # Reciprocal Rank
    reciprocal_rank = 0

    for rank, incident_id in enumerate(
        retrieved,
        start=1,
    ):
        if incident_id in expected:
            reciprocal_rank = 1 / rank
            break

    return recall, hit, reciprocal_rank


def evaluate():

    documents = load_incidents()
    index = create_index(documents)

    # Baseline retriever
    baseline_retriever = index.as_retriever(
        similarity_top_k=FINAL_TOP_K
    )

    # Retrieve more candidates for reranking
    candidate_retriever = index.as_retriever(
        similarity_top_k=CANDIDATE_TOP_K
    )

    reranker = create_reranker(
        top_n=FINAL_TOP_K
    )

    test_cases = load_evaluation_dataset()

    baseline_recall_total = 0
    baseline_hit_total = 0
    baseline_rr_total = 0

    reranked_recall_total = 0
    reranked_hit_total = 0
    reranked_rr_total = 0

    for test in test_cases:

        query = test["query"]
        expected = set(
            test["expected_incidents"]
        )

        # -------------------------
        # Baseline retrieval
        # -------------------------

        baseline_results = (
            baseline_retriever.retrieve(query)
        )

        baseline_ids = [
            result.metadata["incident_id"]
            for result in baseline_results
        ]

        (
            baseline_recall,
            baseline_hit,
            baseline_rr,
        ) = calculate_metrics(
            baseline_ids,
            expected,
        )

        # -------------------------
        # Candidate retrieval
        # -------------------------

        candidates = (
            candidate_retriever.retrieve(query)
        )

        # -------------------------
        # LLM reranking
        # -------------------------

        query_bundle = QueryBundle(
            query_str=query
        )

        reranked_results = (
            reranker.postprocess_nodes(
                candidates,
                query_bundle=query_bundle,
            )
        )

        reranked_ids = [
            result.metadata["incident_id"]
            for result in reranked_results
        ]

        (
            reranked_recall,
            reranked_hit,
            reranked_rr,
        ) = calculate_metrics(
            reranked_ids,
            expected,
        )

        # Add totals
        baseline_recall_total += baseline_recall
        baseline_hit_total += baseline_hit
        baseline_rr_total += baseline_rr

        reranked_recall_total += reranked_recall
        reranked_hit_total += reranked_hit
        reranked_rr_total += reranked_rr

        # -------------------------
        # Print test result
        # -------------------------

        print("\n--------------------------------")
        print(f"Query: {query}")
        print(f"Expected: {sorted(expected)}")

        print("\nBaseline:")
        print(baseline_ids)
        print(
            f"Recall@{FINAL_TOP_K}: "
            f"{baseline_recall:.2f}"
        )
        print(
            f"RR: {baseline_rr:.2f}"
        )

        print("\nReranked:")
        print(reranked_ids)
        print(
            f"Recall@{FINAL_TOP_K}: "
            f"{reranked_recall:.2f}"
        )
        print(
            f"RR: {reranked_rr:.2f}"
        )

    # -------------------------
    # Aggregate results
    # -------------------------

    number_of_tests = len(test_cases)

    print("\n================================")
    print("BASELINE VS RERANKED")
    print("================================")

    print("\nBaseline")

    print(
        f"Recall@{FINAL_TOP_K}: "
        f"{baseline_recall_total / number_of_tests:.2f}"
    )

    print(
        f"Hit Rate@{FINAL_TOP_K}: "
        f"{baseline_hit_total / number_of_tests:.2f}"
    )

    print(
        f"MRR: "
        f"{baseline_rr_total / number_of_tests:.2f}"
    )

    print("\nReranked")

    print(
        f"Recall@{FINAL_TOP_K}: "
        f"{reranked_recall_total / number_of_tests:.2f}"
    )

    print(
        f"Hit Rate@{FINAL_TOP_K}: "
        f"{reranked_hit_total / number_of_tests:.2f}"
    )

    print(
        f"MRR: "
        f"{reranked_rr_total / number_of_tests:.2f}"
    )


if __name__ == "__main__":
    evaluate()