"""ORM model for the Risks context."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import AggregateRootMixin, Base
from ..db.types import JSONColumn


class RiskModel(AggregateRootMixin, Base):
    __tablename__ = "risks"

    organization_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("organizations.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[dict | None] = mapped_column(JSONColumn, nullable=True)
    treatment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    accepted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    acceptance_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    mitigating_control_ids: Mapped[list[str]] = mapped_column(
        JSONColumn, nullable=False, default=list
    )
    evidence_ids: Mapped[list[str]] = mapped_column(JSONColumn, nullable=False, default=list)
