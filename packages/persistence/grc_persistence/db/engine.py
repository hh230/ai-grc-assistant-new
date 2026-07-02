"""Async engine and session-factory construction.

Kept deliberately thin: the composition root (future ``apps/*`` wiring) decides the URL and
pool settings; this module just builds an :class:`AsyncEngine` and a matching
``async_sessionmaker``. ``expire_on_commit=False`` because aggregates are mapped *out* of
the ORM before commit, so callers never touch expired ORM attributes afterward.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(url: str, *, echo: bool = False) -> AsyncEngine:
    """Create an async engine for ``url`` (e.g. ``postgresql+asyncpg://…``)."""
    return create_async_engine(url, echo=echo, future=True)


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build a session factory bound to ``engine`` for the Unit of Work to use."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=True,
    )
