"""ORM model for the Knowledge (RAG source) context.

``KnowledgeSource`` is scoped via the two-library model (CLAUDE.md's Framework Engine):
``scope_kind`` is ``"global"`` (platform-wide, shared) or ``"organization"`` (tenant-isolated),
in which case ``scope_organization_id`` carries the owning tenant. Content and lifecycle live
on the separate ``KnowledgeSourceVersion`` aggregate, tracked here only via
``current_version_id``.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import AggregateRootMixin, Base
from ..db.types import JSONColumn


class KnowledgeSourceModel(AggregateRootMixin, Base):
    __tablename__ = "knowledge_sources"

    scope_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    scope_organization_id: Mapped[str | None] = mapped_column(
        String(255), ForeignKey("organizations.id"), nullable=True, index=True
    )
    short_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[list[dict[str, str]]] = mapped_column(JSONColumn, nullable=False)
    authority: Mapped[str] = mapped_column(String(255), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(64), nullable=False)
    knowledge_domain: Mapped[str] = mapped_column(String(32), nullable=False)
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    classification: Mapped[str] = mapped_column(String(32), nullable=False)
    framework_refs: Mapped[list[str]] = mapped_column(JSONColumn, nullable=False, default=list)
    tags: Mapped[list[str]] = mapped_column(JSONColumn, nullable=False, default=list)
    canonical_languages: Mapped[list[str]] = mapped_column(
        JSONColumn, nullable=False, default=list
    )
    steward: Mapped[dict[str, Any] | None] = mapped_column(JSONColumn, nullable=True)
    current_version_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
