"""Deterministic, server-authoritative demo policy. Models cannot bypass it."""

import json
import uuid
from sqlalchemy import select
from .models import Account, Service, Device, TradeIn, Promotion, Invoice, Approval, Audit, Case
from .telemetry import tracer, escalations

ISSUES = (
    "activation",
    "discounts",
    "billing",
    "trade_in",
    "disconnect",
    "reconnect",
    "suspension",
    "human",
    "unsupported",
)


def stable_id(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "careagent:" + key))


def eligibility(db, service, issue):
    account = db.get(Account, service.account_id)
    if issue in ("billing", "disconnect", "human", "unsupported"):
        return None, "This request requires an operator review."
    if account.restricted:
        return None, "The account has a service restriction; an operator must review it."
    transitions = {
        "activation": ("pending", "active"),
        "reconnect": ("suspended", "active"),
        "suspension": ("active", "suspended"),
    }
    if issue in transitions:
        source, target = transitions[issue]
        if service.status != source:
            return None, f"{issue.title()} requires {source} service; this service is {service.status}."
        return {"status": target}, f"Change {service.label} from {source} to {target}."
    if issue == "discounts":
        if service.status != "active" or service.discount_code:
            return None, "Discounts require active service with no existing promotion."
        promotion = db.scalar(select(Promotion).where(Promotion.service_kind == service.kind))
        if promotion:
            return {"discount_code": promotion.code}, promotion.description
        return None, "No eligible offer is available."
    if issue == "trade_in":
        device = db.scalar(select(Device).where(Device.service_id == service.id))
        if service.kind != "mobile" or not device or not device.eligible:
            return None, "Trade-in requires an eligible mobile device."
        if db.scalar(select(TradeIn).where(TradeIn.device_id == device.id)):
            return None, "This device already has a trade-in submission."
        return {
            "device_id": device.id
        }, f"Start a simulated trade-in for {device.model}; valuation requires inspection."
    return None, "Unsupported request."


def escalate(db, thread_id, service, issue, reason, key, evidence=None):
    case_id = stable_id("case:" + key)
    if db.get(Case, case_id) is None:
        db.add(
            Case(
                id=case_id,
                thread_id=thread_id,
                service_id=service.id,
                issue=issue,
                summary=reason,
                evidence=json.dumps(
                    {
                        "service_status": service.status,
                        "service_version": service.version,
                        "findings": evidence or [],
                    }
                ),
            )
        )
        escalations.add(1, {"issue": issue})
    return {"kind": "escalated", "case_id": case_id, "message": reason + " Sent to the operator queue."}


def prepare(factory, state):
    issue = state["tasks"][state["index"]]
    key = f"{state['run_id']}:{state['index']}"
    with tracer.start_as_current_span("worker." + issue), factory.begin() as db:
        service = db.get(Service, state["service_id"])
        if issue == "billing" and not state.get("billing_dispute"):
            invoice = db.scalar(select(Invoice).where(Invoice.account_id == service.account_id))
            return {
                "kind": "resolved",
                "message": f"Account bill: ${(invoice.total_cents - invoice.credit_cents) / 100:.2f}. "
                + invoice.breakdown
                + f" Credits applied: ${invoice.credit_cents / 100:.2f}.",
            }
        params, description = eligibility(db, service, issue)
        if params is None:
            return escalate(db, state["thread_id"], service, issue, description, key, state.get("results"))
        approval_id = stable_id("approval:" + key)
        approval = db.get(Approval, approval_id)
        if approval is None:
            approval = Approval(
                id=approval_id,
                thread_id=state["thread_id"],
                service_id=service.id,
                issue=issue,
                expected_version=service.version,
                parameters=json.dumps(params),
                status="pending",
            )
            db.add(approval)
        return {
            "kind": "approval",
            "approval_id": approval.id,
            "message": description,
            "issue": issue,
            "parameters": params,
        }


def verify(db, service, issue, params, approval_id):
    db.flush()
    db.refresh(service)
    if issue == "trade_in":
        return db.scalar(select(TradeIn).where(TradeIn.approval_id == approval_id)) is not None
    return all(getattr(service, key) == value for key, value in params.items())


def execute(factory, state, decision):
    with tracer.start_as_current_span("tool.execute"), factory.begin() as db:
        approval = db.scalar(
            select(Approval).where(Approval.id == state["current"]["approval_id"]).with_for_update()
        )
        service = db.scalar(select(Service).where(Service.id == approval.service_id).with_for_update())
        if approval.status != "pending":
            return json.loads(approval.result)
        if decision.get("approval_id") != approval.id or decision.get("approved") is not True:
            approval.status = "rejected"
            result = {"kind": "rejected", "message": "Change declined. No service changes were made."}
        else:
            params, reason = eligibility(db, service, approval.issue)
            if service.version != approval.expected_version or params != json.loads(approval.parameters):
                approval.status = "stale"
                result = escalate(
                    db,
                    approval.thread_id,
                    service,
                    approval.issue,
                    "The account or service changed after this proposal. " + reason,
                    approval.id,
                )
            else:
                with db.begin_nested() as mutation:
                    if approval.issue == "trade_in":
                        db.add(
                            TradeIn(
                                id=stable_id("trade:" + approval.id),
                                device_id=params["device_id"],
                                approval_id=approval.id,
                            )
                        )
                    else:
                        for key, value in params.items():
                            setattr(service, key, value)
                    service.version += 1
                    with tracer.start_as_current_span("validation.readback"):
                        valid = verify(db, service, approval.issue, params, approval.id)
                    if not valid:
                        mutation.rollback()
                if valid:
                    approval.status = "executed"
                    result = {
                        "kind": "resolved",
                        "message": f"{approval.issue.replace('_', ' ').title()} completed and verified.",
                    }
                    db.add(
                        Audit(
                            action_key=approval.id,
                            actor_id=state["user_id"],
                            service_id=service.id,
                            operation=approval.issue,
                            detail=json.dumps(params),
                        )
                    )
                else:
                    approval.status = "failed"
                    result = escalate(
                        db,
                        approval.thread_id,
                        service,
                        approval.issue,
                        "The fix failed verification; simulated changes were rolled back.",
                        approval.id,
                    )
        approval.result = json.dumps(result)
        return result
