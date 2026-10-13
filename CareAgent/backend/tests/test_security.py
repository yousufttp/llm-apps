from uuid import uuid4
from .conftest import sign_in, conversation
from .test_workflows import send, decide


def test_auth_and_account_isolation(client):
    assert client.get("/api/v1/account").status_code == 401
    assert (
        client.post("/api/v1/auth/login", json={"email": "alex@example.test", "password": "bad"}).status_code
        == 401
    )
    sign_in(client)
    thread = conversation(client)
    pending = send(client, thread, "discount")
    case = send(client, conversation(client), "disconnect")["results"][0]["case_id"]
    sign_in(client, "jordan@example.test")
    assert client.get(f"/api/v1/conversations/{thread}").status_code == 404
    assert client.post("/api/v1/conversations", json={"service_id": "mobile-main"}).status_code == 404
    assert (
        client.post(
            "/api/v1/approvals/" + pending["pending"][0]["approval_id"], json={"approved": True}
        ).status_code
        == 404
    )
    assert client.get(f"/api/v1/operator/cases/{case}").status_code == 403
    assert client.get("/api/v1/cases").json() == []
    client.post("/api/v1/auth/logout", json={})
    assert client.get("/api/v1/me").status_code == 401


def test_restricted_account_and_origin(client):
    sign_in(client, "jordan@example.test")
    result = send(client, conversation(client, "mobile-restricted"), "reconnect")
    assert "restriction" in result["message"]
    response = client.post(
        "/api/v1/conversations",
        json={"service_id": "mobile-restricted"},
        headers={"origin": "https://evil.test"},
    )
    assert response.status_code == 403


def test_operator_credit_and_disconnect(client, factory):
    from careagent.models import Invoice, Service

    sign_in(client)
    billing = send(client, conversation(client), "refund my incorrect bill")["results"][0]["case_id"]
    disconnect = send(client, conversation(client), "disconnect")["results"][0]["case_id"]
    sign_in(client, "operator@example.test")
    endpoint = f"/api/v1/operator/cases/{billing}/resolve"
    body = {"action": "credit", "note": "Duplicate charge credited", "credit_cents": 1000, "confirmed": False}
    assert client.post(endpoint, json=body).status_code == 422
    body["confirmed"] = True
    assert client.post(endpoint, json=body).status_code == 200
    assert client.post(endpoint, json=body).status_code == 200
    assert (
        client.post(
            f"/api/v1/operator/cases/{disconnect}/resolve",
            json={"action": "disconnect", "note": "Customer requested cancellation", "confirmed": True},
        ).status_code
        == 200
    )
    with factory() as db:
        assert db.get(Invoice, "invoice-alex").credit_cents == 1000
        assert db.get(Service, "mobile-main").status == "disconnected"


def test_agui_stream_and_thread_ownership(client):
    sign_in(client)
    thread = conversation(client)
    payload = {
        "threadId": thread,
        "runId": str(uuid4()),
        "state": {},
        "messages": [{"id": str(uuid4()), "role": "user", "content": "explain my bill"}],
        "tools": [],
        "context": [],
        "forwardedProps": {},
    }
    response = client.post("/api/v1/agent", json=payload)
    assert response.status_code == 200
    for event in ["RUN_STARTED", "STEP_STARTED", "TEXT_MESSAGE_CONTENT", "STATE_SNAPSHOT", "RUN_FINISHED"]:
        assert event in response.text
    sign_in(client, "jordan@example.test")
    assert client.post("/api/v1/agent", json=payload).status_code == 404


def test_pending_action_blocks_new_request(client):
    sign_in(client)
    thread = conversation(client)
    pending = send(client, thread, "suspend")
    assert (
        client.post(f"/api/v1/conversations/{thread}/messages", json={"message": "discount"}).status_code
        == 409
    )
    decide(client, pending, False)
    assert send(client, thread, "explain bill")["results"][0]["kind"] == "resolved"
