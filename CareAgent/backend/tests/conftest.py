import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from careagent.models import Base
from careagent.seed import seed

# API import must not initialize an Oracle connection during offline unit tests.
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ["TELEMETRY_ENABLED"] = "false"
os.environ["MODEL_MODE"] = "demo"


@pytest.fixture
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    seed(factory)
    yield factory
    engine.dispose()


@pytest.fixture
def client(factory, monkeypatch):
    from careagent import api
    from careagent.db import db_session

    monkeypatch.setattr(api, "session_factory", lambda: factory)

    def session():
        with factory() as db:
            yield db

    api.app.dependency_overrides[db_session] = session
    with TestClient(api.app) as client:
        yield client
    api.app.dependency_overrides.clear()


def sign_in(client, email="alex@example.test"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "CareDemo123!"})
    assert response.status_code == 200, response.text


def conversation(client, service="mobile-main"):
    response = client.post("/api/v1/conversations", json={"service_id": service})
    assert response.status_code == 200, response.text
    return response.json()["id"]
