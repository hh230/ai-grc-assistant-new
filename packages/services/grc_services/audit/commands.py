"""Commands for the Audit capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.audit.enums import AuditCategory

from ..shared.messages import Command


@dataclass(frozen=True, kw_only=True)
class RecordAuditEntry(Command):
    category: AuditCategory
    action: str
    object_type: str
    object_id: str
    outcome: str | None = None
    payload_hash: str | None = None
