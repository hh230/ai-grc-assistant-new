"""Infrastructure / Persistence layer for the AI GRC Assistant.

This package implements the outermost adapter of the architecture (CLAUDE.md §5): it
turns the *interfaces* defined by inner layers into concrete, PostgreSQL-backed behavior
without leaking infrastructure inward.

What it provides:

- ``models``        — SQLAlchemy 2.x ORM models (the relational shape only).
- ``mappers``       — the **only** place Domain ↔ ORM translation happens.
- ``repositories``  — concrete implementations of the domain repository interfaces.
- ``unit_of_work``  — :class:`SqlAlchemyUnitOfWork`, the transaction boundary the
  application's ``UnitOfWork`` port declares.
- ``outbox``        — the transactional outbox: the single source of integration events.
- ``contracts``     — the persistence-layer seams (mapper, cache, outbox, tracking).
- ``migrations``    — Alembic migrations (PostgreSQL).

Dependency direction (CLAUDE.md §6): this package depends on ``grc_domain`` and
``grc_services`` (the ports it implements) — never the other way around.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .unit_of_work import SqlAlchemyUnitOfWork

__all__ = ["SqlAlchemyUnitOfWork"]


def __getattr__(name: str) -> Any:
    # Lazy export so importing the package never forces the full ORM/engine stack.
    if name == "SqlAlchemyUnitOfWork":
        from .unit_of_work import SqlAlchemyUnitOfWork

        return SqlAlchemyUnitOfWork
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
