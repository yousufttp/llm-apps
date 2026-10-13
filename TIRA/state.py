import operator
from typing import Annotated, TypedDict


class IncidentState(TypedDict):
    incident_id: str
    run_id: str
    description: str
    next_agent: str
    order_status: str
    order_check_status: str
    activation_status: str
    activation_reason: str
    activation_attempts: int
    switch_status: str
    clnr_status: str
    human_decision: str
    findings: Annotated[list[str], operator.add]
    resolved: bool
    root_cause: str
