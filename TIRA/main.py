import logging
from uuid import uuid4
from langgraph.types import Command
from database import create_run, init_db, mark_run_status
from graph import build_graph
from logging_config import configure_logging

logger = logging.getLogger("tira")


def create_initial_incident(
    incident_id="INC1001", description="Customer upgraded to eSIM but activation failed"
):
    run_id = uuid4().hex
    return {
        "incident_id": incident_id,
        "run_id": run_id,
        "description": description,
        "next_agent": "",
        "order_status": "not_checked",
        "order_check_status": "not_checked",
        "activation_status": "not_checked",
        "activation_reason": "",
        "activation_attempts": 0,
        "switch_status": "not_checked",
        "clnr_status": "not_checked",
        "human_decision": "pending",
        "findings": [],
        "resolved": False,
        "root_cause": "",
    }


def create_thread_id(incident_id, run_id):
    return f"{incident_id}-{run_id}"


def print_result(result):
    print("\n--- TIRA CURRENT STATE ---")
    for k, v in result.items():
        if k != "__interrupt__":
            print(f"{k}: {v}")


def run_tira():
    configure_logging()
    init_db()
    graph = build_graph()
    incident = create_initial_incident()
    thread_id = create_thread_id(incident["incident_id"], incident["run_id"])
    create_run(incident["run_id"], thread_id, incident["incident_id"])
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 20}
    logger.info(
        "Starting TIRA incident_id=%s run_id=%s thread_id=%s",
        incident["incident_id"],
        incident["run_id"],
        thread_id,
    )
    try:
        result = graph.invoke(incident, config=config)
        print_result(result)
        if "__interrupt__" in result:
            mark_run_status(incident["run_id"], "waiting_for_human")
            print("\n--- HUMAN REVIEW REQUIRED ---")
            print(result["__interrupt__"])
            decision = input("\nEnter decision (approved/rejected): ").strip().lower()
            result = graph.invoke(Command(resume=decision), config=config)
            print_result(result)
        status = (
            "rejected" if result.get("human_decision") == "rejected" else "completed"
        )
        mark_run_status(
            incident["run_id"],
            status,
            resolved=bool(result.get("resolved")),
            root_cause=result.get("root_cause", ""),
        )
    except Exception:
        logger.exception("TIRA execution failed")
        mark_run_status(incident["run_id"], "failed")
        raise
    print("\n--- FINAL RESULT ---")
    print("Incident ID:", result.get("incident_id"))
    print("Run ID:", incident["run_id"])
    print("Thread ID:", thread_id)
    print("Resolved:", result.get("resolved"))
    print("Root Cause:", result.get("root_cause"))
    print("\nFindings:")
    for f in result.get("findings", []):
        print("-", f)


if __name__ == "__main__":
    run_tira()
