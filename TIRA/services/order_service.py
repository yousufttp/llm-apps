def check_order_status(incident_id: str) -> dict:
    m = {
        "INC1001": {"check_status": "success", "order_status": "completed"},
        "INC1002": {"check_status": "success", "order_status": "pending"},
        "INC1003": {"check_status": "timeout", "order_status": "unknown"},
        "INC1004": {"check_status": "success", "order_status": "completed"},
        "INC1005": {"check_status": "success", "order_status": "completed"},
    }
    return m.get(incident_id, {"check_status": "success", "order_status": "unknown"})
