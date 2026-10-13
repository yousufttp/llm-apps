import json
from pathlib import Path
from langsmith import Client, evaluate
from langgraph.types import Command
from evaluation.evaluators import root_cause_evaluator, resolved_evaluator
from graph import build_graph
from main import create_initial_incident, create_thread_id

DATASET_NAME = "tira-golden-dataset"
P = Path(__file__).resolve().parents[1] / "data" / "golden_dataset.json"


def sync_dataset(client):
    cases = json.loads(P.read_text())
    try:
        ds = client.read_dataset(dataset_name=DATASET_NAME)
    except Exception:
        ds = client.create_dataset(
            dataset_name=DATASET_NAME,
            description="TIRA telecom incident golden dataset",
        )
        for case in cases:
            client.create_example(
                dataset_id=ds.id,
                inputs={
                    "incident_id": case["incident_id"],
                    "description": case["description"],
                },
                outputs=case,
            )
    return str(ds.id)


def target(inputs):
    g = build_graph()
    incident = create_initial_incident(inputs["incident_id"], inputs["description"])
    tid = create_thread_id(incident["incident_id"], incident["run_id"])
    cfg = {"configurable": {"thread_id": tid}, "recursion_limit": 20}
    r = g.invoke(incident, config=cfg)
    if "__interrupt__" in r:
        r = g.invoke(Command(resume="approved"), config=cfg)
    return r


def main():
    c = Client()
    sync_dataset(c)
    evaluate(
        target,
        data=DATASET_NAME,
        evaluators=[root_cause_evaluator, resolved_evaluator],
        experiment_prefix="tira",
    )


if __name__ == "__main__":
    main()
