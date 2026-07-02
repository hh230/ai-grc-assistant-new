"""Declarative base, naming convention and reusable mapped mixins.

The naming convention makes every constraint/index name deterministic, which keeps Alembic
migrations stable and diffable (CLAUDE.md §23 — migrations are reviewed artifacts).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model in the persistence layer."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """``created_at`` / ``updated_at`` columns common to every persisted entity."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AggregateRootMixin(TimestampMixin):
    """A string primary key plus an optimistic-concurrency ``version`` column.

    ``version`` is wired as SQLAlchemy's ``version_id_col``: every UPDATE carries a
    ``WHERE version = :loaded`` guard and bumps the value, so a stale write affects zero
    rows and raises ``StaleDataError`` — which the Unit of Work translates into the
    application's ``ConcurrencyError``.
    """

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    @declared_attr.directive
    def __mapper_args__(cls) -> dict[str, object]:  # noqa: N805 - SQLAlchemy directive
        return {"version_id_col": cls.version}
