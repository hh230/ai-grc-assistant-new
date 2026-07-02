"""ORM models for the Platform context (Tool / Agent / Plugin descriptors).

These are global catalog entries — not tenant-scoped — so they carry no ``organization_id``.
"""

from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import AggregateRootMixin, Base
from ..db.types import JSONColumn


class ToolDescriptorModel(AggregateRootMixin, Base):
    __tablename__ = "tool_descriptors"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version_label: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    side_effect: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    required_permissions: Mapped[list[str]] = mapped_column(
        JSONColumn, nullable=False, default=list
    )
    input_schema: Mapped[dict | None] = mapped_column(JSONColumn, nullable=True)
    output_schema: Mapped[dict | None] = mapped_column(JSONColumn, nullable=True)


class AgentDescriptorModel(AggregateRootMixin, Base):
    __tablename__ = "agent_descriptors"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    agent_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    allowed_tool_ids: Mapped[list[str]] = mapped_column(JSONColumn, nullable=False, default=list)
    data_scopes: Mapped[list[str]] = mapped_column(JSONColumn, nullable=False, default=list)


class PluginDescriptorModel(AggregateRootMixin, Base):
    __tablename__ = "plugin_descriptors"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version_label: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    provided_tool_ids: Mapped[list[str]] = mapped_column(JSONColumn, nullable=False, default=list)
    provided_agent_ids: Mapped[list[str]] = mapped_column(JSONColumn, nullable=False, default=list)
    required_permissions: Mapped[list[str]] = mapped_column(
        JSONColumn, nullable=False, default=list
    )
    compatibility: Mapped[dict | None] = mapped_column(JSONColumn, nullable=True)
