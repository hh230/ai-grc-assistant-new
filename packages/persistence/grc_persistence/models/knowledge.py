"""ORM model for the Knowledge (RAG source) context."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import AggregateRootMixin, Base


class KnowledgeSourceModel(AggregateRootMixin, Base):
    __tablename__ = "knowledge_sources"

    organization_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("organizations.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    locator_uri: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    classification: Mapped[str] = mapped_column(String(32), nullable=False)
    ingestion_status: Mapped[str] = mapped_column(String(32), nullable=False)
    checksum_algorithm: Mapped[str | None] = mapped_column(String(64), nullable=True)
    checksum_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
