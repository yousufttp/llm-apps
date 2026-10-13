from services.switch_service import check_switch_status
from state import IncidentState


def switch_node(state: IncidentState) -> dict:
    r = check_switch_status(state["incident_id"])
    if r["check_status"] == "timeout":
        return {"switch_status": "unknown", "findings": ["Switch check timed out"]}
    return {
        "switch_status": r["switch_status"],
        "findings": [f"Switch status is {r['switch_status']}"],
    }
