from services.remediation_service import remediate_issue
from state import IncidentState


def remediation_node(state: IncidentState) -> dict:
    if state["human_decision"] != "approved":
        return {
            "resolved": False,
            "findings": ["Remediation skipped because approval was not granted"],
        }
    key = f"{state['run_id']}:{state['root_cause']}:remediation"
    r = remediate_issue(
        run_id=state["run_id"],
        incident_id=state["incident_id"],
        root_cause=state["root_cause"],
        idempotency_key=key,
    )
    return {
        "resolved": r["status"] == "success",
        "findings": [f"Remediation result: {r['message']}"],
    }
