
# evaluation/run_local_evaluation.py

import json
from pathlib import Path
from uuid import uuid4

from langgraph.types import Command

from database import init_db, save_evaluation_result
from graph import build_graph
from main import create_initial_incident, create_thread_id


DATASET_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "golden_dataset.json"
)


def is_ordered_subsequence(
    actual_path: list[str],
    expected_path: list[str],
) -> bool:
    """
    Returns True when every expected node appears
    in the actual path in the correct order.

    Extra nodes in the actual path are allowed.
    """
    iterator = iter(actual_path)

    return all(
        any(actual == expected for actual in iterator)
        for expected in expected_path
    )


def run_case(graph, case: dict) -> dict:
    incident = create_initial_incident(
        incident_id=case["incident_id"],
        description=case["description"],
    )

    thread_id = create_thread_id(
        incident["incident_id"],
        incident["run_id"],
    )

    config = {
        "configurable": {
            "thread_id": thread_id
        },
        "recursion_limit": 20,
    }

    result = graph.invoke(
        incident,
        config=config,
    )

    # Offline/local evaluation automatically approves
    # so that we can test the full end-to-end flow.
    if "__interrupt__" in result:
        result = graph.invoke(
            Command(resume="approved"),
            config=config,
        )

    return result


def main() -> None:
    init_db()

    graph = build_graph()

    cases = json.loads(
        DATASET_PATH.read_text(
            encoding="utf-8"
        )
    )

    experiment_name = (
        f"local-{uuid4().hex[:8]}"
    )

    total_root_cause = 0
    total_resolved = 0
    total_trajectory = 0

    for case in cases:
        result = run_case(
            graph,
            case,
        )

        # -----------------------------
        # Root-cause evaluation
        # -----------------------------

        expected_root_cause = case.get(
            "expected_root_cause",
            "",
        )

        actual_root_cause = result.get(
            "root_cause",
            "",
        )

        root_cause_ok = (
            actual_root_cause
            == expected_root_cause
        )

        # -----------------------------
        # Resolved-state evaluation
        # -----------------------------

        expected_resolved = bool(
            case.get(
                "expected_resolved_after_approval",
                False,
            )
        )

        actual_resolved = bool(
            result.get(
                "resolved",
                False,
            )
        )

        resolved_ok = (
            actual_resolved
            == expected_resolved
        )

        # -----------------------------
        # Trajectory evaluation
        # -----------------------------

        actual_path = result.get(
            "execution_path",
            [],
        )

        expected_path = case.get(
            "expected_execution_path",
            [],
        )

        trajectory_ok = (
            is_ordered_subsequence(
                actual_path,
                expected_path,
            )
        )

        # -----------------------------
        # Totals
        # -----------------------------

        total_root_cause += int(
            root_cause_ok
        )

        total_resolved += int(
            resolved_ok
        )

        total_trajectory += int(
            trajectory_ok
        )

        # -----------------------------
        # Store evaluation results
        # -----------------------------

        save_evaluation_result(
            experiment_name,
            case["incident_id"],
            "root_cause_correct",
            float(root_cause_ok),
            (
                f"expected={expected_root_cause}, "
                f"actual={actual_root_cause}"
            ),
        )

        save_evaluation_result(
            experiment_name,
            case["incident_id"],
            "resolved_correct",
            float(resolved_ok),
            (
                f"expected={expected_resolved}, "
                f"actual={actual_resolved}"
            ),
        )

        save_evaluation_result(
            experiment_name,
            case["incident_id"],
            "trajectory_correct",
            float(trajectory_ok),
            (
                f"expected_path={expected_path}, "
                f"actual_path={actual_path}"
            ),
        )

        # -----------------------------
        # Console result
        # -----------------------------

        print(
            case["incident_id"],
            (
                "root_cause="
                + (
                    "PASS"
                    if root_cause_ok
                    else "FAIL"
                )
            ),
            (
                "resolved="
                + (
                    "PASS"
                    if resolved_ok
                    else "FAIL"
                )
            ),
            (
                "trajectory="
                + (
                    "PASS"
                    if trajectory_ok
                    else "FAIL"
                )
            ),
        )

        if not trajectory_ok:
            print(
                "  Expected path:",
                expected_path,
            )
            print(
                "  Actual path:  ",
                actual_path,
            )

    # -----------------------------
    # Experiment summary
    # -----------------------------

    count = len(cases)

    print(
        "\nExperiment:",
        experiment_name,
    )

    print(
        "Root-cause accuracy:",
        total_root_cause / count,
    )

    print(
        "Resolved accuracy:",
        total_resolved / count,
    )

    print(
        "Trajectory accuracy:",
        total_trajectory / count,
    )


if __name__ == "__main__":
    main()