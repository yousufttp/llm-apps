import hashlib
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from argon2 import PasswordHasher
from .db import db_session
from .models import Session, User, now

hasher = PasswordHasher()


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def current_user(request: Request, db=Depends(db_session)):
    token = request.cookies.get("careagent_session", "")
    session = db.get(Session, digest(token)) if token else None
    if not session or session.expires_at <= now():
        raise HTTPException(401, "Sign in to continue")
    return db.get(User, session.user_id)


def operator(user=Depends(current_user)):
    if user.role != "operator":
        raise HTTPException(403, "Operator access required")
    return user


def owned_thread(db, thread_id, user):
    from .models import Conversation

    row = db.scalar(select(Conversation).where(Conversation.id == thread_id, Conversation.user_id == user.id))
    if not row:
        raise HTTPException(404, "Conversation not found")
    return row
