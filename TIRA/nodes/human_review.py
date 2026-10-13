from langgraph.types import interrupt
from state import IncidentState

ALLOWED_DECISIONS = {"approved", "rejected"}


def human_review_node(state: IncidentState) -> dict:
    d = interrupt(
        {
            "incident_id": state["incident_id"],
            "run_id": state["run_id"],
            "root_cause": state["root_cause"],
            "findings": state["findings"],
            "question": "Approve remediation?",
            "allowed_decisions": sorted(ALLOWED_DECISIONS),
        }
    )
    n = str(d).strip().lower()
    if n not in ALLOWED_DECISIONS:
        n = "rejected"
    return {"human_decision": n, "findings": [f"Human decision received: {n}"]}
