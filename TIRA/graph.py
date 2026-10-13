import sqlite3
from functools import lru_cache
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from config import settings
from nodes.activation import activation_node
from nodes.clnr import clnr_node
from nodes.human_review import human_review_node
from nodes.pending_order import pending_order_node
from nodes.remediation import remediation_node
from nodes.router import router_node
from nodes.supervisor import supervisor_node
from nodes.switch import switch_node
from state import IncidentState


def route_from_router(state):
    return state["next_agent"]


def route_from_supervisor(state):
    return state["next_agent"]


def route_after_human_review(state):
    return "remediation" if state["human_decision"] == "approved" else "end"


@lru_cache(maxsize=1)
def build_graph():
    b = StateGraph(IncidentState)
    for name, node in {
        "router": router_node,
        "pending_order": pending_order_node,
        "activation": activation_node,
        "switch": switch_node,
        "clnr": clnr_node,
        "supervisor": supervisor_node,
        "human_review": human_review_node,
        "remediation": remediation_node,
    }.items():
        b.add_node(name, node)
    b.add_edge(START, "router")
    b.add_conditional_edges(
        "router",
        route_from_router,
        {
            "pending_order": "pending_order",
            "activation": "activation",
            "switch": "switch",
            "clnr": "clnr",
            "human_review": "human_review",
        },
    )
    for n in ["pending_order", "activation", "switch", "clnr"]:
        b.add_edge(n, "supervisor")
    b.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "pending_order": "pending_order",
            "activation": "activation",
            "switch": "switch",
            "clnr": "clnr",
            "human_review": "human_review",
            "end": END,
        },
    )
    b.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {"remediation": "remediation", "end": END},
    )
    b.add_edge("remediation", END)
    conn = sqlite3.connect(settings.db_path, check_same_thread=False)
    saver = SqliteSaver(conn)
    g = b.compile(checkpointer=saver)
    g._tira_checkpoint_conn = conn
    g._tira_checkpointer = saver
    return g
