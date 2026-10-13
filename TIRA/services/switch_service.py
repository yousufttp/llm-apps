def check_switch_status(incident_id: str) -> dict:
    m = {
        "INC1001": {"check_status": "success", "switch_status": "mismatch"},
        "INC1002": {"check_status": "success", "switch_status": "not_applicable"},
        "INC1003": {"check_status": "timeout", "switch_status": "unknown"},
        "INC1004": {"check_status": "success", "switch_status": "clear"},
        "INC1005": {"check_status": "success", "switch_status": "clear"},
    }
    return m.get(incident_id, {"check_status": "success", "switch_status": "unknown"})
