"""ORM model for the Policies context."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import AggregateRootMixin, Base
from ..db.types import JSONColumn


class PolicyModel(AggregateRootMixin, Base):
    __tablename__ = "policies"

    organization_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("organizations.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linked_control_ids: Mapped[list[str]] = mapped_column(JSONColumn, nullable=False, default=list)
    framework_controls: Mapped[list[dict]] = mapped_column(JSONColumn, nullable=False, default=list)
    citations: Mapped[list[dict]] = mapped_column(JSONColumn, nullable=False, default=list)
