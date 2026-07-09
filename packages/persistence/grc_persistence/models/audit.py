"""ORM model for the Audit context.

Audit records are append-only (CLAUDE.md §19): there is no ``version`` column and the
repository exposes no update or delete path.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base, TimestampMixin
from ..db.types import JSONColumn


class AuditRecordModel(TimestampMixin, Base):
    __tablename__ = "audit_records"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("organizations.id"), nullable=False, index=True
    )
    actor: Mapped[dict[str, Any]] = mapped_column(JSONColumn, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    object_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    object_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    trace: Mapped[dict[str, Any] | None] = mapped_column(JSONColumn, nullable=True)
    ai_call: Mapped[dict[str, Any] | None] = mapped_column(JSONColumn, nullable=True)
    payload_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_ids: Mapped[list[str]] = mapped_column(JSONColumn, nullable=False, default=list)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
