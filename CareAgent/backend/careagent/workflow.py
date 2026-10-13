import hashlib
import json
import logging
import re
import time
from datetime import timedelta
from contextlib import contextmanager
from fastapi import HTTPException
from sqlalchemy import select, update, or_
from langgraph.types import Command
from .models import Conversation, AgentRun, Message, Approval, now
from .telemetry import tracer, runs, latency

logger = logging.getLogger("careagent.workflow")


class Workflow:
    def __init__(self, factory, graph):
        self.factory, self.graph = factory, graph

    @contextmanager
    def claim(self, thread_id):
        with self.factory.begin() as db:
            result = db.execute(
                update(Conversation)
                .where(
                    Conversation.id == thread_id,
                    or_(Conversation.lease_until.is_(None), Conversation.lease_until < now()),
                )
                .values(lease_until=now() + timedelta(minutes=5))
            )
            if result.rowcount != 1:
                raise HTTPException(409, "This conversation is already processing. Retry shortly.")
        try:
            yield
        finally:
            with self.factory.begin() as db:
                db.execute(update(Conversation).where(Conversation.id == thread_id).values(lease_until=None))

    def config(self, thread_id):
        return {"configurable": {"thread_id": thread_id}, "recursion_limit": 40}

    def summary(self, state):
        values = state.values
        pending = [i.value for task in state.tasks for i in task.interrupts]
        messages = [r["message"] for r in values.get("results", [])]
        if pending:
            messages.append(pending[0]["message"] + " Review the proposal and choose Approve or Decline.")
        if values.get("clarification"):
            messages.append(values["clarification"])
        return {
            "message": "\n\n".join(messages) or "Please describe your telecom issue.",
            "results": values.get("results", []),
            "pending": pending,
        }

    def run(self, thread, user, run_id, text, progress=None):
        start = time.monotonic()
        config = self.config(thread.id)
        request_hash = hashlib.sha256(text.encode()).hexdigest()
        with self.claim(thread.id), tracer.start_as_current_span("supervisor.run"):
            snapshot = self.graph.get_state(config)
            pending = [i.value for task in snapshot.tasks for i in task.interrupts]
            handoff = bool(
                pending
                and re.search(r"\b(human|operator|person|representative)\b", text.lower())
                and not re.search(r"\b(not|don't|never)\b", text.lower())
            )
            with self.factory.begin() as db:
                existing = db.get(AgentRun, run_id)
                if existing:
                    if existing.thread_id != thread.id or existing.request_hash != request_hash:
                        raise HTTPException(409, "Run identifier already used for another request")
                    if existing.result:
                        return json.loads(existing.result)
                else:
                    snapshot = self.graph.get_state(config)
                    if snapshot.next and not handoff:
                        raise HTTPException(
                            409, "Resolve the pending approval or recover the current run first"
                        )
                    db.add(AgentRun(id=run_id, thread_id=thread.id, request_hash=request_hash))
                    db.add(Message(thread_id=thread.id, role="user", content=text))
            snapshot = self.graph.get_state(config)
            recovering = snapshot.values.get("run_id") == run_id
            if handoff:
                input_state = Command(
                    resume={
                        "approval_id": pending[0]["approval_id"],
                        "approved": False,
                        "handoff": True,
                        "run_id": run_id,
                        "text": text,
                    }
                )
            elif recovering:
                input_state = None
            else:
                with self.factory() as db:
                    history = db.scalars(
                        select(Message)
                        .where(Message.thread_id == thread.id)
                        .order_by(Message.created_at.desc())
                        .limit(11)
                    ).all()
                    history = [{"role": m.role, "content": m.content} for m in reversed(history)]
                input_state = {
                    "thread_id": thread.id,
                    "user_id": user.id,
                    "service_id": thread.service_id,
                    "run_id": run_id,
                    "text": text,
                    "history": history[:-1],
                }
            if handoff or not recovering or (snapshot.next and not any(t.interrupts for t in snapshot.tasks)):
                for event in self.graph.stream(input_state, config, stream_mode="updates"):
                    if progress:
                        for node in event:
                            if node != "__interrupt__":
                                progress(node)
            result = self.summary(self.graph.get_state(config))
            with self.factory.begin() as db:
                db.get(AgentRun, run_id).result = json.dumps(result)
                db.add(Message(thread_id=thread.id, role="assistant", content=result["message"]))
            runs.add(1, {"status": "success"})
            latency.record(time.monotonic() - start)
            logger.info("agent_run_completed")
            return result

    def approve(self, thread, approval_id, approved):
        config = self.config(thread.id)
        with self.claim(thread.id):
            with self.factory() as db:
                approval = db.get(Approval, approval_id)
                if not approval or approval.thread_id != thread.id:
                    raise HTTPException(404, "Approval not found")
                snapshot = self.graph.get_state(config)
                pending = [i.value for task in snapshot.tasks for i in task.interrupts]
                matches = pending and pending[0]["approval_id"] == approval_id
                # A crash can commit an action before the graph checkpoint. Resume that same interrupt;
                # the execution tool reads the durable result and never repeats the mutation.
                if approval.status != "pending" and not matches:
                    return {"message": json.loads(approval.result)["message"], "pending": [], "results": []}
                if not matches:
                    raise HTTPException(409, "This approval is not the current workflow step")
            self.graph.invoke(Command(resume={"approval_id": approval_id, "approved": approved}), config)
            result = self.summary(self.graph.get_state(config))
            with self.factory.begin() as db:
                db.add(Message(thread_id=thread.id, role="assistant", content=result["message"]))
            return result

    def recover(self, thread, user):
        snapshot = self.graph.get_state(self.config(thread.id))
        with self.factory() as db:
            pending = [i.value for task in snapshot.tasks for i in task.interrupts]
            if pending:
                approval = db.get(Approval, pending[0]["approval_id"])
                if approval.status != "pending":
                    return self.approve(thread, approval.id, approval.status != "rejected")
                return self.summary(snapshot)
            run = db.get(AgentRun, snapshot.values.get("run_id")) if snapshot.values else None
            if run and (snapshot.next or not run.result):
                return self.run(thread, user, run.id, snapshot.values["text"])
            # Recover a request persisted immediately before the first checkpoint.
            run = db.scalar(
                select(AgentRun).where(AgentRun.thread_id == thread.id, AgentRun.result.is_(None))
            )
            if run:
                message = db.scalar(
                    select(Message)
                    .where(Message.thread_id == thread.id, Message.role == "user")
                    .order_by(Message.created_at.desc())
                    .limit(1)
                )
                return self.run(thread, user, run.id, message.content)
        return self.summary(snapshot)
