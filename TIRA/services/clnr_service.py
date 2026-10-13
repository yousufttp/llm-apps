def check_clnr_status(incident_id: str) -> dict:
    m = {
        "INC1001": {"check_status": "success", "clnr_status": "clear"},
        "INC1002": {"check_status": "success", "clnr_status": "clear"},
        "INC1003": {"check_status": "timeout", "clnr_status": "unknown"},
        "INC1004": {"check_status": "success", "clnr_status": "clear"},
        "INC1005": {"check_status": "success", "clnr_status": "limit_error"},
    }
    return m.get(incident_id, {"check_status": "success", "clnr_status": "unknown"})
