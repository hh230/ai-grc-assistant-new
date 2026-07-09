"""The initial Alembic migration must build exactly the schema the models describe.

Running ``upgrade head`` then reflecting the database and comparing it to ``Base.metadata``
guards against model/migration drift (a frequent source of production incidents). The
migration is dialect-portable (``JSONColumn`` renders as ``JSON`` here, ``JSONB`` on
PostgreSQL), so it runs against the same SQLite engine the rest of the suite uses.
"""

from __future__ import annotations

import pathlib

import pytest
from alembic import command
from alembic.config import Config
from grc_persistence.models import Base
from sqlalchemy import create_engine, inspect

PERSISTENCE_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _config() -> Config:
    cfg = Config(str(PERSISTENCE_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PERSISTENCE_ROOT / "grc_persistence" / "migrations"))
    return cfg


def test_migration_builds_and_drops_full_schema(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "migration.db"
    url = f"sqlite:///{db_path}"
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", url)
    cfg = _config()

    command.upgrade(cfg, "head")

    engine = create_engine(url)
    inspector = inspect(engine)
    migrated_tables = set(inspector.get_table_names()) - {"alembic_version"}
    assert migrated_tables == set(Base.metadata.tables)

    for table in sorted(Base.metadata.tables):
        migrated_columns = {col["name"] for col in inspector.get_columns(table)}
        model_columns = set(Base.metadata.tables[table].columns.keys())
        assert migrated_columns == model_columns, f"column drift in {table}"

    engine.dispose()

    command.downgrade(cfg, "base")
    inspector = inspect(create_engine(url))
    assert set(inspector.get_table_names()) - {"alembic_version"} == set()
