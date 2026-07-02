"""Shared fixtures for the persistence integration tests.

The suite runs against a real async engine and real transactions. By default it uses a
file-backed async SQLite database (hermetic, no external services) built from the same
``Base.metadata`` the Alembic migration encodes; point ``TEST_DATABASE_URL`` at a
PostgreSQL+asyncpg URL to run the identical tests against the production engine.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable

import pytest
import pytest_asyncio
from grc_persistence import SqlAlchemyUnitOfWork
from grc_persistence.db.engine import build_session_factory, create_engine
from grc_persistence.models import Base
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest_asyncio.fixture
async def engine(tmp_path) -> AsyncIterator[AsyncEngine]:
    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite+aiosqlite:///{tmp_path / 'grc.db'}"
    eng = create_engine(url)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await eng.dispose()


@pytest.fixture
def uow_factory(engine: AsyncEngine) -> Callable[[], SqlAlchemyUnitOfWork]:
    """Return a factory that builds a fresh Unit of Work on the shared engine."""
    session_factory = build_session_factory(engine)

    def make() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    return make
