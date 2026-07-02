"""Queries for the Audit capability."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from grc_domain.shared.identifiers import AuditRecordId

from ..shared.messages import Query


@dataclass(frozen=True, kw_only=True)
class GetAuditRecord(Query):
    record_id: AuditRecordId


@dataclass(frozen=True, kw_only=True)
class QueryAuditTrail(Query):
    object_type: str | None = None
    object_id: str | None = None
    since: datetime | None = None
    until: datetime | None = None
