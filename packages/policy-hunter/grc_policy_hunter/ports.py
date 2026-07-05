"""Structural storage ports (CLAUDE.md §5: outer orchestration, not core).

These ``Protocol``s match ``grc_persistence_web``'s existing repository shapes exactly
(``RegulatoryObligationRepository``, ``RegulatoryRawDocumentRepository``, ``PolicyRepository``)
so the Tools in ``tools.py`` can depend on them without this package importing
``grc_persistence_web`` (or any database library) at all — the same decoupling pattern
``grc_regulatory_crawlers.runner`` established in ADR-0019.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class ObligationRecord(Protocol):
    """Matches ``grc_persistence_web.RegulatoryObligationRecord`` structurally."""

    id: str
    raw_document_id: str
    obligation_text: str
    obligation_type: str
    control_domain: str
    suggested_policy_title: str
    severity: str
    confidence: float
    classification_status: str


class ObligationStore(Protocol):
    async def list_by_status(self, classification_status: str) -> list[ObligationRecord]: ...


class RawDocumentRecord(Protocol):
    """Matches ``grc_persistence_web.RegulatoryRawDocumentRecord`` structurally."""

    source_id: str
    url: str
    fetched_at: datetime


class RawDocumentStore(Protocol):
    async def get(self, document_id: str) -> RawDocumentRecord | None: ...


class PolicyRecord(Protocol):
    """Matches ``grc_persistence_web.PolicyRecord`` structurally."""

    id: str
    title: str
    summary: str | None
    status: str
    updated_at: datetime


class PolicyStore(Protocol):
    async def list(self, tenant_id: str) -> list[PolicyRecord]: ...
