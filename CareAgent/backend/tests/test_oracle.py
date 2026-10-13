"""Opt-in tests require an EMPTY disposable Oracle 21c schema; no existing schema is dropped."""

import os
from uuid import uuid4
import pytest
from sqlalchemy import create_engine, inspect, select, func
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command
from careagent.models import Account, Conversation, Service, User
from careagent.seed import seed
from careagent.checkpointer import OracleSaver
from careagent.agents import build_graph
from careagent.workflow import Workflow
from .test_checkpointer import exercise_saver


@pytest.mark.oracle
def test_oracle_migration_seed_checkpoints_and_recovery(monkeypatch):
    url = os.getenv("TEST_ORACLE_URL")
    if not url:
        pytest.skip("Set TEST_ORACLE_URL to an empty, disposable Oracle 21c test schema")
    engine = create_engine(url, pool_pre_ping=True)
    if inspect(engine).get_table_names():
        pytest.fail(
            "Oracle integration tests require an empty dedicated schema; refusing to modify existing tables"
        )
    from careagent import db, config

    monkeypatch.setenv("DATABASE_URL", url)
    config.settings.cache_clear()
    db.engine.cache_clear()
    try:
        command.upgrade(Config("alembic.ini"), "head")
        factory = sessionmaker(engine, expire_on_commit=False)
        seed(factory)
        seed(factory)
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(Account)) == 2
        exercise_saver(factory)
        with factory.begin() as session:
            thread = Conversation(user_id="user-alex", service_id="mobile-main")
            session.add(thread)
            session.flush()
            user = session.get(User, "user-alex")
        workflow = Workflow(factory, build_graph(factory, OracleSaver(factory)))
        result = workflow.run(thread, user, str(uuid4()), "suspend")
        workflow = Workflow(factory, build_graph(factory, OracleSaver(factory)))
        approval = result["pending"][0]["approval_id"]
        workflow.approve(thread, approval, True)
        workflow.approve(thread, approval, True)
        with factory() as session:
            assert session.get(Service, "mobile-main").status == "suspended"
        with factory() as session:
            session.get(Service, "mobile-main").status = "active"
            session.flush()
            session.rollback()
        with factory() as session:
            assert session.get(Service, "mobile-main").status == "suspended"
        command.downgrade(Config("alembic.ini"), "base")
    finally:
        engine.dispose()
        db.engine().dispose()
        db.engine.cache_clear()
        config.settings.cache_clear()
