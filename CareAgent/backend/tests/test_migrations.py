from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, create_mock_engine, inspect, select, func
from sqlalchemy.orm import sessionmaker
from careagent.models import Base, Account
from careagent.seed import seed


def test_migrations_and_repeatable_seed(tmp_path, monkeypatch):
    from careagent import db

    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    monkeypatch.setattr(db, "engine", lambda: engine)
    command.upgrade(Config("alembic.ini"), "head")
    assert set(Base.metadata.tables) <= set(inspect(engine).get_table_names())
    factory = sessionmaker(engine)
    seed(factory)
    seed(factory)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Account)) == 2
    command.downgrade(Config("alembic.ini"), "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]
    engine.dispose()


def test_schema_compiles_for_oracle():
    statements = []
    engine = create_mock_engine(
        "oracle+oracledb://",
        lambda sql, *args, **kwargs: statements.append(str(sql.compile(dialect=engine.dialect))),
    )
    Base.metadata.create_all(engine)
    ddl = "\n".join(statements)
    assert "BLOB" in ddl
    assert "TIMESTAMP" in ddl
    assert "CREATE TABLE graph_checkpoints" in ddl
