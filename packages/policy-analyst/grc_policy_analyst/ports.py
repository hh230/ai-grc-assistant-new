"""Structural storage ports (CLAUDE.md §5: outer orchestration, not core).

These ``Protocol``s match ``grc_persistence_web``'s existing repository shapes exactly
(``PolicyRepository``, ``RegulatoryObligationRepository``, ``RegulatoryRawDocumentRepository``)
so the Tool in ``tools.py`` can depend on them without this package importing
``grc_persistence_web`` (or any database library) at all — the same decoupling pattern
``grc_regulatory_crawlers.runner`` (ADR-0019) and ``grc_policy_hunter`` (ADR-0020) established.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol


class PolicyRecord(Protocol):
    """Matches ``grc_persistence_web.PolicyRecord`` structurally.

    Declared as read-only ``@property`` members, not plain attributes: every concrete
    implementation (``grc_persistence_web``'s records, and this suite's test fakes) is a
    frozen dataclass, and mypy only accepts a frozen (read-only) attribute as satisfying a
    ``Protocol`` member that is itself declared read-only.
    """

    @property
    def id(self) -> str: ...
    @property
    def title(self) -> str: ...
    @property
    def summary(self) -> str | None: ...
    @property
    def body(self) -> str | None: ...
    @property
    def status(self) -> str: ...
    @property
    def owner_name(self) -> str: ...
    @property
    def updated_at(self) -> datetime: ...


class PolicyStore(Protocol):
    async def get(self, tenant_id: str, policy_id: str) -> PolicyRecord | None: ...


class ObligationRecord(Protocol):
    """Matches ``grc_persistence_web.RegulatoryObligationRecord`` structurally (read-only,
    see ``PolicyRecord``)."""

    @property
    def id(self) -> str: ...
    @property
    def raw_document_id(self) -> str: ...
    @property
    def obligation_text(self) -> str: ...
    @property
    def control_domain(self) -> str: ...
    @property
    def suggested_policy_title(self) -> str: ...
    @property
    def classification_status(self) -> str: ...


class ObligationStore(Protocol):
    async def list_by_status(self, classification_status: str) -> Sequence[ObligationRecord]: ...


class RawDocumentRecord(Protocol):
    """Matches ``grc_persistence_web.RegulatoryRawDocumentRecord`` structurally (read-only,
    see ``PolicyRecord``)."""

    @property
    def source_id(self) -> str: ...
    @property
    def url(self) -> str: ...
    @property
    def fetched_at(self) -> datetime: ...


class RawDocumentStore(Protocol):
    async def get(self, document_id: str) -> RawDocumentRecord | None: ...
