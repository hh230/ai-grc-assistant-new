"""ORM model for the Controls context."""

from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import AggregateRootMixin, Base
from ..db.types import JSONColumn


class ControlModel(AggregateRootMixin, Base):
    __tablename__ = "controls"

    organization_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("organizations.id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    implementation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    framework_controls: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONColumn, nullable=False, default=list
    )
    evidence_ids: Mapped[list[str]] = mapped_column(JSONColumn, nullable=False, default=list)
