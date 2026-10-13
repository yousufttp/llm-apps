from services.activation_service import check_activation_status
from state import IncidentState


def activation_node(state: IncidentState) -> dict:
    r = check_activation_status(state["incident_id"])
    a = state["activation_attempts"] + 1
    if r["check_status"] == "timeout":
        return {
            "activation_status": "unknown",
            "activation_reason": "",
            "activation_attempts": a,
            "findings": ["Activation check timed out"],
        }
    return {
        "activation_status": r["activation_status"],
        "activation_reason": r["reason"],
        "activation_attempts": a,
        "findings": [f"Activation status is {r['activation_status']}: {r['reason']}"],
    }
