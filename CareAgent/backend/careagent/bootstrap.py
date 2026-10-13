"""Wait for Oracle, apply migrations, seed once, then run the API."""

import time
from sqlalchemy import text
from alembic.config import Config
from alembic import command
from .db import engine
from .seed import seed


def main():
    for attempt in range(90):
        try:
            with engine().connect() as db:
                db.execute(text("SELECT 1 FROM DUAL"))
            break
        except Exception:
            if attempt == 89:
                raise RuntimeError("Oracle did not become ready within 15 minutes") from None
            time.sleep(10)
    with engine().connect() as db:
        schema = db.scalar(text("SELECT SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') FROM dual"))
        if schema.upper() in {"SYS", "SYSTEM"}:
            raise RuntimeError(
                "Configure a dedicated CareAgent schema; administrative schemas are not supported"
            )
    command.upgrade(Config("alembic.ini"), "head")
    seed()


if __name__ == "__main__":
    main()
