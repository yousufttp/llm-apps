from services.order_service import check_order_status
from state import IncidentState


def pending_order_node(state: IncidentState) -> dict:
    r = check_order_status(state["incident_id"])
    if r["check_status"] == "timeout":
        return {
            "order_status": "unknown",
            "order_check_status": "timeout",
            "findings": ["Pending Order check timed out"],
        }
    return {
        "order_status": r["order_status"],
        "order_check_status": "success",
        "findings": [f"Order status is {r['order_status']}"],
    }
