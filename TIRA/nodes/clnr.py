from services.clnr_service import check_clnr_status
from state import IncidentState


def clnr_node(state: IncidentState) -> dict:
    r = check_clnr_status(state["incident_id"])
    if r["check_status"] == "timeout":
        return {"clnr_status": "unknown", "findings": ["CLNR check timed out"]}
    return {
        "clnr_status": r["clnr_status"],
        "findings": [f"CLNR status is {r['clnr_status']}"],
    }
