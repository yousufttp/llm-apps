def check_activation_status(incident_id: str) -> dict:
    m = {
        "INC1001": {
            "check_status": "success",
            "activation_status": "failed",
            "reason": "esim_profile_missing",
        },
        "INC1002": {
            "check_status": "success",
            "activation_status": "blocked",
            "reason": "pending_order_exists",
        },
        "INC1003": {
            "check_status": "timeout",
            "activation_status": "unknown",
            "reason": "",
        },
        "INC1004": {
            "check_status": "success",
            "activation_status": "success",
            "reason": "",
        },
        "INC1005": {
            "check_status": "success",
            "activation_status": "failed",
            "reason": "clnr_limit_error",
        },
    }
    return m.get(
        incident_id,
        {
            "check_status": "success",
            "activation_status": "unknown",
            "reason": "no_test_data",
        },
    )
