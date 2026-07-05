"""Structural storage ports (CLAUDE.md §5: outer orchestration, not core).

These ``Protocol``s match ``grc_persistence_web``'s existing repository shapes exactly
(``RegulatoryObligationRepository``, ``RegulatoryRawDocumentRepository``) so the Tool in
``tools.py`` can depend on them without this package importing ``grc_persistence_web`` (or
any database library) at all — the same decoupling pattern ``grc_policy_hunter`` (ADR-0020)
and ``grc_policy_analyst`` (ADR-0021) established. Policy Builder deliberately has no
``PolicyStore`` port at all: it never reads a tenant's existing policies (ADR-0024) — that
question belongs to Policy Hunter, not this package.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class ObligationRecord(Protocol):
    """Matches ``grc_persistence_web.RegulatoryObligationRecord`` structurally (read-only:
    a ``Protocol`` declared via ``@property`` so a frozen dataclass satisfies it — the same
    fix ADR-0022 applied to ``grc_policy_hunter``/``grc_policy_analyst``'s own ports)."""

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
    async def get(self, obligation_id: str) -> ObligationRecord | None: ...


class RawDocumentRecord(Protocol):
    """Matches ``grc_persistence_web.RegulatoryRawDocumentRecord`` structurally (read-only,
    see ``ObligationRecord``)."""

    @property
    def source_id(self) -> str: ...
    @property
    def url(self) -> str: ...
    @property
    def fetched_at(self) -> datetime: ...


class RawDocumentStore(Protocol):
    async def get(self, document_id: str) -> RawDocumentRecord | None: ...
