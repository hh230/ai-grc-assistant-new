"""ORM models for the Frameworks context.

A framework is identified by ``(id, version_label)`` — assessments pin the version they ran
against — so :class:`FrameworkModel` uses a composite primary key rather than the standard
single-id aggregate mixin. ``row_version`` is the optimistic-concurrency token (distinct
from the framework's domain ``version_label``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import AggregateRootMixin, Base
from ..db.types import JSONColumn


class FrameworkModel(Base):
    __tablename__ = "frameworks"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    version_label: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    region: Mapped[str | None] = mapped_column(String(16), nullable=True)
    languages: Mapped[list[str]] = mapped_column(JSONColumn, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    controls: Mapped[list[dict[str, Any]]] = mapped_column(JSONColumn, nullable=False, default=list)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __mapper_args__ = {"version_id_col": row_version}


class FrameworkMappingSetModel(AggregateRootMixin, Base):
    __tablename__ = "framework_mapping_sets"

    source_framework_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    target_framework_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    correspondences: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONColumn, nullable=False, default=list
    )
