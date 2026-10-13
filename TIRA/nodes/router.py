from state import IncidentState


def router_node(state: IncidentState) -> dict:
    d = state["description"].lower()
    if "order" in d or "pending" in d:
        n = "pending_order"
    elif "activation" in d or "esim" in d:
        n = "activation"
    elif "switch" in d or "provisioning" in d:
        n = "switch"
    elif "clnr" in d:
        n = "clnr"
    else:
        n = "human_review"
    return {"next_agent": n, "findings": [f"Router selected {n}"]}
