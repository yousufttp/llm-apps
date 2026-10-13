from uuid import uuid4
import pytest
from sqlalchemy import select, func
from .conftest import sign_in, conversation
from careagent.models import Service, Approval, Audit, TradeIn, Invoice


def send(client, thread, message, run_id=None):
    response = client.post(
        f"/api/v1/conversations/{thread}/messages",
        json={"message": message, "run_id": run_id or str(uuid4())},
    )
    assert response.status_code == 200, response.text
    return response.json()


def decide(client, result, approved=True):
    response = client.post(
        "/api/v1/approvals/" + result["pending"][0]["approval_id"], json={"approved": approved}
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize(
    "service,issue,field,expected",
    [
        ("mobile-new", "activate", "status", "active"),
        ("broadband-new", "activate", "status", "active"),
        ("mobile-paused", "reconnect", "status", "active"),
        ("broadband-paused", "reconnect", "status", "active"),
        ("mobile-main", "suspend", "status", "suspended"),
        ("broadband-home", "suspend", "status", "suspended"),
        ("mobile-main", "discount", "discount_code", "MOBILE10"),
        ("broadband-home", "discount", "discount_code", "FIBER15"),
    ],
)
def test_confirmed_actions(client, factory, service, issue, field, expected):
    sign_in(client)
    thread = conversation(client, service)
    proposal = send(client, thread, issue)
    with factory() as db:
        assert getattr(db.get(Service, service), field) != expected
    outcome = decide(client, proposal)
    assert outcome["results"][-1]["kind"] == "resolved"
    with factory() as db:
        assert getattr(db.get(Service, service), field) == expected
        assert db.scalar(select(func.count()).select_from(Audit)) == 1


def test_trade_in_and_duplicate_approval(client, factory):
    sign_in(client)
    thread = conversation(client)
    result = send(client, thread, "trade in")
    decide(client, result)
    decide(client, result)
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(TradeIn)) == 1
    again = send(client, thread, "trade in")
    assert again["results"][0]["kind"] == "escalated"


@pytest.mark.parametrize(
    "service,query",
    [
        ("broadband-home", "trade in"),
        ("mobile-new", "trade in"),
        ("mobile-main", "activate"),
        ("mobile-main", "disconnect"),
        ("mobile-main", "I want a human"),
        ("mobile-main", "my bill is wrong"),
        ("mobile-main", "change my mailing address"),
    ],
)
def test_escalation(client, service, query):
    sign_in(client)
    outcome = send(client, conversation(client, service), query)
    assert outcome["results"][0]["kind"] == "escalated"
    assert client.get("/api/v1/cases").json()[0]["status"] == "open"


def test_bill_explanation(client, factory):
    sign_in(client)
    result = send(client, conversation(client), "explain my bill")
    assert "$135.00" in result["message"]
    assert not result["pending"]
    with factory() as db:
        assert db.get(Invoice, "invoice-alex").credit_cents == 0


def test_sequential_and_declined_actions(client, factory):
    sign_in(client)
    result = send(client, conversation(client), "discount then suspend")
    result = decide(client, result, False)
    assert result["pending"][0]["issue"] == "suspension"
    result = decide(client, result)
    assert [r["kind"] for r in result["results"]] == ["rejected", "resolved"]
    with factory() as db:
        service = db.get(Service, "mobile-main")
        assert service.discount_code is None
        assert service.status == "suspended"


def test_stale_approval(client, factory):
    sign_in(client)
    result = send(client, conversation(client), "suspend")
    with factory.begin() as db:
        db.get(Service, "mobile-main").version += 1
    result = decide(client, result)
    assert result["results"][-1]["kind"] == "escalated"
    with factory() as db:
        assert db.get(Service, "mobile-main").status == "active"


def test_verification_failure_rolls_back(client, factory, monkeypatch):
    from careagent import policy

    sign_in(client)
    result = send(client, conversation(client), "suspend")
    monkeypatch.setattr(policy, "verify", lambda *args: False)
    result = decide(client, result)
    assert result["results"][-1]["kind"] == "escalated"
    with factory() as db:
        assert db.get(Service, "mobile-main").status == "active"
        assert db.scalar(select(func.count()).select_from(Audit)) == 0


def test_idempotent_run_and_conflicting_payload(client, factory):
    sign_in(client)
    thread, run = conversation(client), str(uuid4())
    first = send(client, thread, "discount", run)
    assert send(client, thread, "discount", run) == first
    response = client.post(
        f"/api/v1/conversations/{thread}/messages", json={"message": "suspend", "run_id": run}
    )
    assert response.status_code == 409
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Approval)) == 1


def test_restart_approval(client, factory):
    from careagent.api import app
    from careagent.agents import build_graph
    from careagent.checkpointer import OracleSaver
    from careagent.workflow import Workflow

    sign_in(client)
    result = send(client, conversation(client), "suspend")
    app.state.workflow = Workflow(factory, build_graph(factory, OracleSaver(factory)))
    assert decide(client, result)["results"][-1]["kind"] == "resolved"


def test_provider_failure_handoff(client, monkeypatch):
    from careagent import agents

    def fail(*args):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(agents, "classify", fail)
    sign_in(client)
    result = send(client, conversation(client), "please help")
    assert result["results"][0]["kind"] == "escalated"


def test_recover_committed_action_before_checkpoint(client, factory):
    from careagent.api import app
    from careagent.policy import execute

    sign_in(client)
    thread = conversation(client)
    result = send(client, thread, "suspend")
    approval = result["pending"][0]["approval_id"]
    state = app.state.workflow.graph.get_state(app.state.workflow.config(thread)).values
    execute(factory, state, {"approval_id": approval, "approved": True})
    recovered = client.post(f"/api/v1/conversations/{thread}/recover", json={})
    assert recovered.status_code == 200, recovered.text
    assert not recovered.json()["pending"]
    assert recovered.json()["results"][-1]["kind"] == "resolved"
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Audit)) == 1


def test_negated_request_asks_for_clarification(client):
    sign_in(client)
    result = send(client, conversation(client), "do not disconnect")
    assert not result["pending"]
    assert not result["results"]
    assert "Which action" in result["message"]


def test_human_request_cancels_pending_plan(client, factory):
    sign_in(client)
    thread = conversation(client)
    send(client, thread, "discount then suspend")
    result = send(client, thread, "I want a human")
    assert not result["pending"]
    assert result["results"][-1]["kind"] == "escalated"
    with factory() as db:
        service = db.get(Service, "mobile-main")
        assert service.status == "active"
        assert service.discount_code is None
        assert db.scalar(select(func.count()).select_from(Approval)) == 1
