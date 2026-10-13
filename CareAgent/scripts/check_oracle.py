"""Read-only connection check. Does not print credentials or create database objects."""

from sqlalchemy import text
from careagent.config import settings
from careagent.db import engine

config = settings()
if not config.database_url and not config.oracle_password:
    raise SystemExit("Set ORACLE_PASSWORD in the local .env file before checking the connection.")
try:
    with engine().connect() as connection:
        version = connection.scalar(text("SELECT banner FROM v$version WHERE banner LIKE 'Oracle Database%'"))
        details = connection.execute(
            text(
                "SELECT SYS_CONTEXT('USERENV','SERVICE_NAME'), "
                "SYS_CONTEXT('USERENV','CURRENT_SCHEMA') FROM dual"
            )
        ).one()
        print(f"Connected: {version}; service={details[0]}; schema={details[1]}")
except Exception as exc:
    # Driver exception messages may include connection details. Only print its code.
    original = getattr(exc, "orig", None)
    detail = original.args[0] if original and original.args else None
    print("Connection failed:", getattr(detail, "full_code", type(exc).__name__))
    raise SystemExit(1) from None
