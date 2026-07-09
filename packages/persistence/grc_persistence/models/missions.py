"""ORM models for the Missions context — the one aggregate with child tables.

A mission owns ordered collections of steps and approval gates. They live in their own
tables (``mission_steps``, ``mission_approval_gates``) and are kept in sync by the
repository's diff algorithm keyed on each child's stable id. ``position`` preserves the
domain ordering of each collection.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import AggregateRootMixin, Base, TimestampMixin
from ..db.types import JSONColumn


class MissionModel(AggregateRootMixin, Base):
    __tablename__ = "missions"

    organization_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("organizations.id"), nullable=False, index=True
    )
    workspace_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    steps: Mapped[list[MissionStepModel]] = relationship(
        back_populates="mission",
        cascade="all, delete-orphan",
        order_by="MissionStepModel.position",
        lazy="selectin",
    )
    gates: Mapped[list[MissionApprovalGateModel]] = relationship(
        back_populates="mission",
        cascade="all, delete-orphan",
        order_by="MissionApprovalGateModel.position",
        lazy="selectin",
    )


class MissionStepModel(TimestampMixin, Base):
    __tablename__ = "mission_steps"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    mission_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("missions.id"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    side_effect: Mapped[str] = mapped_column(String(32), nullable=False)
    agent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tool_ids: Mapped[list[str]] = mapped_column(JSONColumn, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    output_ref: Mapped[str | None] = mapped_column(Text, nullable=True)

    mission: Mapped[MissionModel] = relationship(back_populates="steps")


class MissionApprovalGateModel(TimestampMixin, Base):
    __tablename__ = "mission_approval_gates"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    mission_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("missions.id"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    step_id: Mapped[str] = mapped_column(String(255), nullable=False)
    proposed_action: Mapped[dict[str, Any]] = mapped_column(JSONColumn, nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    decided_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    mission: Mapped[MissionModel] = relationship(back_populates="gates")
