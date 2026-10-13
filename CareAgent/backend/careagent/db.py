from functools import lru_cache
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import settings


@lru_cache
def engine():
    url = settings().db_url()
    kwargs = {"connect_args": {"check_same_thread": False}} if str(url).startswith("sqlite") else {}
    return create_engine(url, pool_pre_ping=True, **kwargs)


def session_factory():
    return sessionmaker(engine(), expire_on_commit=False)


def db_session():
    with session_factory()() as db:
        yield db
