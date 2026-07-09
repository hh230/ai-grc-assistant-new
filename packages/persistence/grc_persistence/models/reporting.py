"""ORM model for the Reporting context."""

from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import AggregateRootMixin, Base
from ..db.types import JSONColumn


class ReportModel(AggregateRootMixin, Base):
    __tablename__ = "reports"

    organization_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("organizations.id"), nullable=False, index=True
    )
    report_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_mission_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_assessment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sections: Mapped[list[dict[str, Any]]] = mapped_column(JSONColumn, nullable=False, default=list)
