"""ORM model for the Evidence context.

Table name ``evidence`` is intentionally the uncountable mass noun (there is no natural
``evidences`` plural); it nonetheless reads as a collection of evidence rows.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import AggregateRootMixin, Base
from ..db.types import JSONColumn


class EvidenceModel(AggregateRootMixin, Base):
    __tablename__ = "evidence"

    organization_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("organizations.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(32), nullable=False)
    knowledge_source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validity_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validity_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    linked_control_ids: Mapped[list[str]] = mapped_column(JSONColumn, nullable=False, default=list)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
