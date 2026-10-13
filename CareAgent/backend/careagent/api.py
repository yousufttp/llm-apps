import asyncio
import json
import secrets
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Literal
from uuid import UUID, uuid4
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, text, delete
from argon2.exceptions import VerificationError
from ag_ui.core import RunAgentInput
from .config import settings
from .db import engine, session_factory, db_session
from .models import (
    User,
    Session,
    Service,
    Account,
    Invoice,
    Conversation,
    Message,
    Approval,
    Case,
    Audit,
    now,
)
from .auth import current_user, operator, owned_thread, hasher, digest
from .checkpointer import OracleSaver
from .agents import build_graph
from .workflow import Workflow
from .telemetry import configure


def serialize(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


@asynccontextmanager
async def lifespan(app):
    factory = session_factory()
    app.state.workflow = Workflow(factory, build_graph(factory, OracleSaver(factory)))
    yield
    engine().dispose()


app = FastAPI(title="CareAgent", version="0.1.0", lifespan=lifespan)
configure(app, engine(), settings())


@app.middleware("http")
async def origin_check(request: Request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and origin != settings().allowed_origin:
            return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
    return await call_next(request)


@app.get("/health/live")
def live():
    return {"status": "ok"}


@app.get("/health/ready")
def ready(db=Depends(db_session)):
    try:
        db.execute(text("SELECT 1 FROM DUAL") if engine().dialect.name == "oracle" else text("SELECT 1"))
        db.scalar(select(User.id).limit(1))
    except Exception:
        raise HTTPException(503, "Database not ready")
    return {"status": "ready", "model_mode": settings().model_mode}


class Login(BaseModel):
    email: str = Field(max_length=150)
    password: str = Field(max_length=200)


@app.post("/api/v1/auth/login")
def login(body: Login, response: Response, db=Depends(db_session)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    try:
        if not user or not hasher.verify(user.password_hash, body.password):
            raise HTTPException(401, "Invalid credentials")
    except VerificationError:
        raise HTTPException(401, "Invalid credentials")
    token = secrets.token_urlsafe(32)
    db.add(Session(token_hash=digest(token), user_id=user.id, expires_at=now() + timedelta(hours=8)))
    db.commit()
    response.set_cookie(
        "careagent_session",
        token,
        httponly=True,
        samesite="strict",
        secure=settings().cookie_secure,
        max_age=28800,
        path="/",
    )
    return {"id": user.id, "role": user.role, "email": user.email}


@app.post("/api/v1/auth/logout")
def logout(request: Request, response: Response, db=Depends(db_session)):
    db.execute(
        delete(Session).where(Session.token_hash == digest(request.cookies.get("careagent_session", "")))
    )
    db.commit()
    response.delete_cookie("careagent_session")
    return {"ok": True}


@app.get("/api/v1/me")
def me(user=Depends(current_user)):
    return {"id": user.id, "role": user.role, "email": user.email, "model_mode": settings().model_mode}


@app.get("/api/v1/account")
def account(user=Depends(current_user), db=Depends(db_session)):
    if not user.account_id:
        raise HTTPException(403, "Customer account required")
    return {
        "account": serialize(db.get(Account, user.account_id)),
        "services": [
            serialize(s) for s in db.scalars(select(Service).where(Service.account_id == user.account_id))
        ],
        "invoices": [
            serialize(i) for i in db.scalars(select(Invoice).where(Invoice.account_id == user.account_id))
        ],
    }


class NewThread(BaseModel):
    service_id: str = Field(max_length=36)


@app.post("/api/v1/conversations")
def create_thread(body: NewThread, user=Depends(current_user), db=Depends(db_session)):
    service = db.get(Service, body.service_id)
    if not service or service.account_id != user.account_id:
        raise HTTPException(404, "Service not found")
    thread = Conversation(user_id=user.id, service_id=service.id)
    db.add(thread)
    db.commit()
    return serialize(thread)


@app.get("/api/v1/conversations")
def threads(user=Depends(current_user), db=Depends(db_session)):
    return [
        serialize(t)
        for t in db.scalars(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.created_at.desc())
        )
    ]


@app.get("/api/v1/conversations/{thread_id}")
def thread_detail(thread_id: UUID, user=Depends(current_user), db=Depends(db_session)):
    thread = owned_thread(db, str(thread_id), user)
    return {
        "thread": serialize(thread),
        "messages": [
            serialize(m)
            for m in db.scalars(
                select(Message).where(Message.thread_id == thread.id).order_by(Message.created_at)
            )
        ],
        "approvals": [
            serialize(a)
            for a in db.scalars(
                select(Approval).where(Approval.thread_id == thread.id).order_by(Approval.created_at)
            )
        ],
    }


class Chat(BaseModel):
    run_id: UUID = Field(default_factory=uuid4)
    message: str = Field(min_length=1, max_length=4000)


@app.post("/api/v1/conversations/{thread_id}/messages")
def chat(thread_id: UUID, body: Chat, request: Request, user=Depends(current_user), db=Depends(db_session)):
    thread = owned_thread(db, str(thread_id), user)
    return request.app.state.workflow.run(thread, user, str(body.run_id), body.message)


@app.post("/api/v1/conversations/{thread_id}/recover")
def recover(thread_id: UUID, request: Request, user=Depends(current_user), db=Depends(db_session)):
    thread = owned_thread(db, str(thread_id), user)
    return request.app.state.workflow.recover(thread, user)


class Decision(BaseModel):
    approved: bool


@app.post("/api/v1/approvals/{approval_id}")
def approve(
    approval_id: UUID, body: Decision, request: Request, user=Depends(current_user), db=Depends(db_session)
):
    approval = db.get(Approval, str(approval_id))
    if not approval:
        raise HTTPException(404, "Approval not found")
    thread = owned_thread(db, approval.thread_id, user)
    return request.app.state.workflow.approve(thread, approval.id, body.approved)


@app.get("/api/v1/cases")
def cases(user=Depends(current_user), db=Depends(db_session)):
    q = select(Case)
    if user.role != "operator":
        q = q.join(Conversation).where(Conversation.user_id == user.id)
    return [serialize(c) for c in db.scalars(q.order_by(Case.created_at.desc()))]


@app.get("/api/v1/operator/cases/{case_id}")
def case_detail(case_id: UUID, user=Depends(operator), db=Depends(db_session)):
    case = db.get(Case, str(case_id))
    if not case:
        raise HTTPException(404, "Case not found")
    service = db.get(Service, case.service_id)
    return {
        "case": serialize(case),
        "service": serialize(service),
        "invoices": [
            serialize(i) for i in db.scalars(select(Invoice).where(Invoice.account_id == service.account_id))
        ],
        "messages": [
            serialize(m)
            for m in db.scalars(
                select(Message).where(Message.thread_id == case.thread_id).order_by(Message.created_at)
            )
        ],
        "actions": [
            serialize(a) for a in db.scalars(select(Approval).where(Approval.thread_id == case.thread_id))
        ],
    }


class Resolution(BaseModel):
    action: Literal["resolve", "credit", "disconnect"]
    note: str = Field(min_length=5, max_length=2000)
    credit_cents: int = Field(default=0, ge=0, le=10000)
    confirmed: bool = False


@app.post("/api/v1/operator/cases/{case_id}/resolve")
def resolve(case_id: UUID, body: Resolution, user=Depends(operator), db=Depends(db_session)):
    case = db.scalar(select(Case).where(Case.id == str(case_id)).with_for_update())
    if not case:
        raise HTTPException(404, "Case not found")
    if case.status == "resolved":
        return serialize(case)
    if not body.confirmed:
        raise HTTPException(422, "Explicit operator confirmation required")
    service = db.scalar(select(Service).where(Service.id == case.service_id).with_for_update())
    if body.action == "credit":
        if case.issue != "billing" or body.credit_cents <= 0:
            raise HTTPException(422, "Credits require a billing case and a positive amount")
        invoice = db.scalar(select(Invoice).where(Invoice.account_id == service.account_id).with_for_update())
        if invoice.credit_cents + body.credit_cents > invoice.total_cents:
            raise HTTPException(422, "Credit exceeds remaining invoice balance")
        expected = invoice.credit_cents + body.credit_cents
        invoice.credit_cents = expected
        db.flush()
        db.refresh(invoice)
        if invoice.credit_cents != expected:
            raise HTTPException(409, "Credit verification failed")
    elif body.action == "disconnect":
        if case.issue != "disconnect":
            raise HTTPException(422, "Disconnection requires a disconnect case")
        service.status = "disconnected"
        service.version += 1
        db.flush()
        db.refresh(service)
        if service.status != "disconnected":
            raise HTTPException(409, "Disconnection verification failed")
    db.add(
        Audit(
            action_key="case:" + case.id,
            actor_id=user.id,
            service_id=service.id,
            operation=body.action,
            detail=body.model_dump_json(),
        )
    )
    case.status, case.resolution = "resolved", body.note
    db.commit()
    return serialize(case)


@app.post("/api/v1/agent")
async def agent(body: RunAgentInput, request: Request, user=Depends(current_user), db=Depends(db_session)):
    try:
        thread_id, run_id = str(UUID(body.thread_id)), str(UUID(body.run_id))
    except ValueError:
        raise HTTPException(422, "Thread and run identifiers must be UUIDs")
    thread = owned_thread(db, thread_id, user)
    messages = [m for m in body.messages if m.role == "user"]
    content = messages[-1].content if messages else None
    if not isinstance(content, str) or not content.strip() or len(content) > 4000:
        raise HTTPException(422, "A text message of 1–4000 characters is required")

    async def events():
        queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def progress(node):
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "STEP_STARTED", "stepName": node})
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "STEP_FINISHED", "stepName": node})

        async def work():
            try:
                result = await asyncio.to_thread(
                    request.app.state.workflow.run, thread, user, run_id, content, progress
                )
                mid = str(uuid4())
                await queue.put({"type": "TEXT_MESSAGE_START", "messageId": mid, "role": "assistant"})
                await queue.put(
                    {"type": "TEXT_MESSAGE_CONTENT", "messageId": mid, "delta": result["message"]}
                )
                await queue.put({"type": "TEXT_MESSAGE_END", "messageId": mid})
                await queue.put({"type": "STATE_SNAPSHOT", "snapshot": result})
                await queue.put({"type": "RUN_FINISHED", "threadId": thread_id, "runId": run_id})
            except Exception as exc:
                message = (
                    exc.detail
                    if isinstance(exc, HTTPException)
                    else "Run interrupted. Retry the same request to recover."
                )
                await queue.put({"type": "RUN_ERROR", "message": message, "code": "RUN_FAILED"})
            finally:
                await queue.put(None)

        yield "data: " + json.dumps({"type": "RUN_STARTED", "threadId": thread_id, "runId": run_id}) + "\n\n"
        task = asyncio.create_task(work())
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield "data: " + json.dumps(event) + "\n\n"
        finally:
            # Finish persisting a run even if the browser disconnects.
            await asyncio.shield(task)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
