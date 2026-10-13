"""One-time initial schema snapshot generator; refuses to overwrite a migration."""

from pathlib import Path
from sqlalchemy import create_engine
from alembic.autogenerate import produce_migrations, render_python_code
from alembic.migration import MigrationContext
from careagent.models import Base

target = Path("backend/migrations/versions/0001_initial.py")
if target.exists():
    raise SystemExit("Initial migration already exists; create a new Alembic revision instead")
with create_engine("sqlite://").connect() as connection:
    migration = produce_migrations(MigrationContext.configure(connection), Base.metadata)
content = '''"""Initial Oracle-compatible schema snapshot."""
from alembic import op
import sqlalchemy as sa
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
'''
content += render_python_code(migration.upgrade_ops)
content += "\n\ndef downgrade():\n" + render_python_code(migration.downgrade_ops) + "\n"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(content, encoding="utf-8")
