"""Read/write access to apps/web's `policies` table — the same table its Next.js
`lib/policies/repository.ts` already serves the workspace UI from. This adapter only adds an
insert path for AI-authored drafts (Policy Builder Agent); it never writes `in_review` or
`published` — those transitions stay exactly where they are today, gated by
`apps/web/lib/policies/service.ts`'s `publish` permission check.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from .pool import Database


@dataclass(frozen=True)
class PolicyRecord:
    id: str
    tenant_id: str
    title: str
    summary: str | None
    body: str | None
    status: str
    owner_name: str
    control_ids: tuple[str, ...]
    created_by_user_id: str
    created_by_name: str
    created_at: datetime
    updated_at: datetime
    approved_by_name: str | None
    approved_at: datetime | None
    ai_generated: bool
    generated_by_tool: str | None
    generation_metadata: dict[str, object] | None


def _to_record(row: object) -> PolicyRecord:
    metadata = row["generation_metadata"]  # type: ignore[index]
    return PolicyRecord(
        id=row["id"],  # type: ignore[index]
        tenant_id=row["tenant_id"],  # type: ignore[index]
        title=row["title"],  # type: ignore[index]
        summary=row["summary"],  # type: ignore[index]
        body=row["body"],  # type: ignore[index]
        status=row["status"],  # type: ignore[index]
        owner_name=row["owner_name"],  # type: ignore[index]
        control_ids=tuple(json.loads(row["control_ids"])),  # type: ignore[index]
        created_by_user_id=row["created_by_user_id"],  # type: ignore[index]
        created_by_name=row["created_by_name"],  # type: ignore[index]
        created_at=row["created_at"],  # type: ignore[index]
        updated_at=row["updated_at"],  # type: ignore[index]
        approved_by_name=row["approved_by_name"],  # type: ignore[index]
        approved_at=row["approved_at"],  # type: ignore[index]
        ai_generated=row["ai_generated"],  # type: ignore[index]
        generated_by_tool=row["generated_by_tool"],  # type: ignore[index]
        generation_metadata=json.loads(metadata) if metadata else None,
    )


_COLUMNS = """
  id, tenant_id, title, summary, body, status, owner_name, control_ids,
  created_by_user_id, created_by_name, created_at, updated_at, approved_by_name,
  approved_at, ai_generated, generated_by_tool, generation_metadata
"""


class PolicyRepository:
    """Tenant-scoped read/write access to `policies` (default deny: every query filters on
    `tenant_id`)."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def list(self, tenant_id: str) -> list[PolicyRecord]:
        async with self._database.pool.acquire() as connection:
            rows = await connection.fetch(
                f"SELECT {_COLUMNS} FROM policies WHERE tenant_id = $1 ORDER BY updated_at DESC",
                tenant_id,
            )
        return [_to_record(row) for row in rows]

    async def get(self, tenant_id: str, policy_id: str) -> PolicyRecord | None:
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                f"SELECT {_COLUMNS} FROM policies WHERE tenant_id = $1 AND id = $2",
                tenant_id,
                policy_id,
            )
        return _to_record(row) if row is not None else None

    async def insert_draft(
        self,
        *,
        tenant_id: str,
        title: str,
        summary: str | None,
        body: str | None,
        owner_name: str,
        control_ids: tuple[str, ...],
        created_by_user_id: str,
        created_by_name: str,
        generated_by_tool: str,
        generation_metadata: dict[str, object],
    ) -> PolicyRecord:
        """Insert a new AI-authored policy draft. Always `status='draft'` — publishing an
        AI-authored draft goes through the same human-gated workflow as any other policy."""
        now = datetime.now(timezone.utc)
        policy_id = str(uuid.uuid4())
        async with self._database.pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO policies (
                  id, tenant_id, title, summary, body, status, owner_name, control_ids,
                  created_by_user_id, created_by_name, created_at, updated_at,
                  ai_generated, generated_by_tool, generation_metadata
                ) VALUES (
                  $1, $2, $3, $4, $5, 'draft', $6, $7::jsonb, $8, $9, $10, $10, true, $11,
                  $12::jsonb
                )
                """,
                policy_id,
                tenant_id,
                title,
                summary,
                body,
                owner_name,
                json.dumps(list(control_ids)),
                created_by_user_id,
                created_by_name,
                now,
                generated_by_tool,
                json.dumps(generation_metadata),
            )
        record = await self.get(tenant_id, policy_id)
        assert record is not None  # noqa: S101 - just written in the same call, must exist
        return record
