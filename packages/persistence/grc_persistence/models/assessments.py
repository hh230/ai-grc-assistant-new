"""ORM model for the Assessments context."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import AggregateRootMixin, Base
from ..db.types import JSONColumn


class AssessmentModel(AggregateRootMixin, Base):
    __tablename__ = "assessments"

    organization_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("organizations.id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    framework_id: Mapped[str] = mapped_column(String(255), nullable=False)
    framework_version_label: Mapped[str] = mapped_column(String(64), nullable=False)
    assessment_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    results: Mapped[list[dict]] = mapped_column(JSONColumn, nullable=False, default=list)
    summary: Mapped[dict | None] = mapped_column(JSONColumn, nullable=True)
