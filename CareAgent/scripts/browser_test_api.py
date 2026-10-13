"""Isolated SQLite harness for browser tests; deployment connects to the existing Oracle."""

import os
from pathlib import Path
from uuid import uuid4

Path(".cache").mkdir(exist_ok=True)
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(".cache", f"browser-{uuid4()}.db").resolve()).replace(
    "\\", "/"
)
os.environ["MODEL_MODE"] = "demo"
os.environ["TELEMETRY_ENABLED"] = "false"

from careagent.db import engine, session_factory  # noqa: E402
from careagent.models import Base  # noqa: E402
from careagent.seed import seed  # noqa: E402
import uvicorn  # noqa: E402

Base.metadata.create_all(engine())
seed(session_factory())
uvicorn.run("careagent.api:app", host="127.0.0.1", port=8001, access_log=False)
