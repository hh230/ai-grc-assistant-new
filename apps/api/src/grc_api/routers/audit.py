"""Audit router — the append-only, tenant-scoped audit trail (CLAUDE.md §19, ADR-0015).

There is no update or delete path: the trail is tamper-evident by construction. Reads are
restricted to roles that may inspect the audit log (auditor / admin / managers).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query, status
from grc_domain.audit.enums import AuditCategory
from grc_domain.shared.identifiers import AuditRecordId
from grc_services.audit import commands as c
from grc_services.audit import queries as q
from pydantic import Field

from ..schemas.common import ApiModel, problem_responses, unwrap
from ..security.dependencies import Commands, Context, Queries

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditRecordResponse(ApiModel):
    id: str
    organization_id: str
    actor_kind: str
    actor_reference: str | None
    category: str
    action: str
    object_type: str
    object_id: str
    occurred_at: str
    outcome: str | None


class RecordAuditEntryRequest(ApiModel):
    category: AuditCategory
    action: str = Field(min_length=1)
    object_type: str = Field(min_length=1)
    object_id: str = Field(min_length=1)
    outcome: str | None = None
    payload_hash: str | None = None


@router.post(
    "",
    response_model=AuditRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Append an audit entry",
    responses=problem_responses(403, 422),
)
async def record_entry(
    body: RecordAuditEntryRequest, commands: Commands, context: Context
) -> object:
    command = c.RecordAuditEntry(
        category=body.category,
        action=body.action,
        object_type=body.object_type,
        object_id=body.object_id,
        outcome=body.outcome,
        payload_hash=body.payload_hash,
    )
    return unwrap(await commands.dispatch(command, context))


@router.get(
    "",
    response_model=list[AuditRecordResponse],
    summary="Query the audit trail",
    responses=problem_responses(403),
)
async def query_trail(
    queries: Queries,
    context: Context,
    object_type: str | None = Query(default=None),
    object_id: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
) -> object:
    query = q.QueryAuditTrail(
        object_type=object_type, object_id=object_id, since=since, until=until
    )
    return unwrap(await queries.ask(query, context))


@router.get(
    "/{record_id}",
    response_model=AuditRecordResponse,
    summary="Get an audit record",
    responses=problem_responses(403, 404),
)
async def get_record(record_id: str, queries: Queries, context: Context) -> object:
    return unwrap(await queries.ask(q.GetAuditRecord(record_id=AuditRecordId(record_id)), context))
