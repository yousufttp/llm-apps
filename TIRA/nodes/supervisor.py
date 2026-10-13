from state import IncidentState

MAX_ACTIVATION_ATTEMPTS = 3


def supervisor_node(state: IncidentState) -> dict:
    if state["order_check_status"] == "timeout":
        return {
            "next_agent": "human_review",
            "findings": ["Order status could not be verified"],
        }
    if state["order_status"] == "pending":
        return {
            "next_agent": "human_review",
            "root_cause": "pending_order",
            "findings": ["Pending order is blocking activation"],
        }
    if (
        state["order_status"] == "completed"
        and state["activation_status"] == "not_checked"
    ):
        return {"next_agent": "activation"}
    if state["activation_status"] == "success":
        return {
            "next_agent": "end",
            "resolved": True,
            "root_cause": "no_active_failure",
        }
    if state["activation_attempts"] >= MAX_ACTIVATION_ATTEMPTS:
        return {
            "next_agent": "human_review",
            "findings": ["Activation attempt limit reached"],
        }
    if state["activation_status"] == "unknown":
        return {
            "next_agent": "human_review",
            "findings": ["Activation status could not be verified"],
        }
    if (
        state["activation_reason"] == "clnr_limit_error"
        and state["clnr_status"] == "not_checked"
    ):
        return {"next_agent": "clnr"}
    if (
        state["activation_status"] in {"failed", "blocked"}
        and state["activation_reason"] != "clnr_limit_error"
        and state["switch_status"] == "not_checked"
    ):
        return {"next_agent": "switch"}
    if state["switch_status"] == "mismatch":
        return {
            "next_agent": "human_review",
            "root_cause": "switch_provisioning_mismatch",
            "findings": ["Switch provisioning mismatch identified"],
        }
    if state["switch_status"] == "clear":
        return {
            "next_agent": "human_review",
            "root_cause": "activation_failure_unresolved",
            "findings": ["Switch is clear but activation remains unresolved"],
        }
    if state["switch_status"] == "unknown":
        return {
            "next_agent": "human_review",
            "findings": ["Switch status could not be verified"],
        }
    if state["clnr_status"] == "limit_error":
        return {
            "next_agent": "human_review",
            "root_cause": "clnr_limit_error",
            "findings": ["CLNR limit error identified"],
        }
    if state["clnr_status"] in {"clear", "unknown"}:
        return {
            "next_agent": "human_review",
            "root_cause": "activation_failure_unresolved",
            "findings": ["CLNR did not provide a remediable root cause"],
        }
    return {
        "next_agent": "human_review",
        "findings": ["Supervisor could not determine a safe next action"],
    }
