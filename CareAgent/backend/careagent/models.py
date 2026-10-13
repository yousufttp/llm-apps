import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, TIMESTAMP, ForeignKey, LargeBinary, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(100))
    restricted: Mapped[int] = mapped_column(Integer, default=0)


class User(Base):
    __tablename__ = "app_users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(150), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"))


class Session(Base):
    __tablename__ = "app_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"))
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP)


class Service(Base):
    __tablename__ = "services"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    label: Mapped[str] = mapped_column(String(100))
    plan: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))
    version: Mapped[int] = mapped_column(Integer, default=1)
    discount_code: Mapped[str | None] = mapped_column(String(30))


class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    total_cents: Mapped[int] = mapped_column(Integer)
    credit_cents: Mapped[int] = mapped_column(Integer, default=0)
    breakdown: Mapped[str] = mapped_column(Text)


class Promotion(Base):
    __tablename__ = "promotions"
    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    service_kind: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(String(200))


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"), unique=True)
    model: Mapped[str] = mapped_column(String(100))
    eligible: Mapped[int] = mapped_column(Integer, default=1)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"), index=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"))
    lease_until: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=now)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    thread_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=now)


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    thread_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"))
    request_hash: Mapped[str] = mapped_column(String(64))
    result: Mapped[str | None] = mapped_column(Text)


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    thread_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"))
    issue: Mapped[str] = mapped_column(String(30))
    expected_version: Mapped[int] = mapped_column(Integer)
    parameters: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    result: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=now)


class TradeIn(Base):
    __tablename__ = "trade_ins"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), unique=True)
    approval_id: Mapped[str] = mapped_column(ForeignKey("approvals.id"), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="submitted")


class Case(Base):
    __tablename__ = "support_cases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    thread_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"))
    issue: Mapped[str] = mapped_column(String(30))
    summary: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")
    resolution: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=now)


class Audit(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    action_key: Mapped[str] = mapped_column(String(100), unique=True)
    actor_id: Mapped[str] = mapped_column(String(36))
    service_id: Mapped[str] = mapped_column(String(36))
    operation: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=now)


class CheckpointRow(Base):
    __tablename__ = "graph_checkpoints"
    __table_args__ = (UniqueConstraint("thread_id", "namespace", "checkpoint_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    thread_id: Mapped[str] = mapped_column(String(36), index=True)
    namespace: Mapped[str] = mapped_column(String(200), default="root")
    checkpoint_id: Mapped[str] = mapped_column(String(100))
    parent_id: Mapped[str | None] = mapped_column(String(100))
    payload_type: Mapped[str] = mapped_column(String(30))
    payload: Mapped[bytes] = mapped_column(LargeBinary)
    metadata_json: Mapped[str] = mapped_column(Text)


class CheckpointWrite(Base):
    __tablename__ = "graph_writes"
    __table_args__ = (UniqueConstraint("thread_id", "namespace", "checkpoint_id", "task_id", "write_index"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    thread_id: Mapped[str] = mapped_column(String(36), index=True)
    namespace: Mapped[str] = mapped_column(String(200))
    checkpoint_id: Mapped[str] = mapped_column(String(100))
    task_id: Mapped[str] = mapped_column(String(100))
    task_path: Mapped[str | None] = mapped_column(String(500))
    write_index: Mapped[int] = mapped_column(Integer)
    channel: Mapped[str] = mapped_column(String(100))
    payload_type: Mapped[str] = mapped_column(String(30))
    payload: Mapped[bytes] = mapped_column(LargeBinary)
