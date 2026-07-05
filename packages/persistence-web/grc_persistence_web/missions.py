"""The lightweight Mission record for Policy Intelligence runs (`policy_missions` +
`policy_mission_steps` — see `apps/web/lib/db/migrations/0015_policy_missions.sql`). Makes a
Policy Hunter/Analyst/Builder run visible, steerable, and auditable (CLAUDE.md §8) without the
full generic Workflow Engine (`apps/workflow` stays out of scope for now).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from .pool import Database


@dataclass(frozen=True)
class MissionStepRecord:
    id: str
    position: int
    step: str
    detail: str
    citations: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True)
class MissionRecord:
    id: str
    tenant_id: str
    agent: str
    goal: str
    status: str
    awaiting_approval: bool
    created_by_user_id: str
    created_by_name: str
    created_at: datetime
    updated_at: datetime
    steps: tuple[MissionStepRecord, ...] = ()


class PolicyMissionStore:
    """Tenant-scoped create/append/read access to Policy Intelligence mission runs."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def create(
        self,
        *,
        tenant_id: str,
        agent: str,
        goal: str,
        created_by_user_id: str,
        created_by_name: str,
        status: str = "executing",
    ) -> MissionRecord:
        now = datetime.now(timezone.utc)
        mission_id = str(uuid.uuid4())
        async with self._database.pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO policy_missions (
                  id, tenant_id, agent, goal, status, awaiting_approval,
                  created_by_user_id, created_by_name, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, false, $6, $7, $8, $8)
                """,
                mission_id,
                tenant_id,
                agent,
                goal,
                status,
                created_by_user_id,
                created_by_name,
                now,
            )
        return MissionRecord(
            id=mission_id,
            tenant_id=tenant_id,
            agent=agent,
            goal=goal,
            status=status,
            awaiting_approval=False,
            created_by_user_id=created_by_user_id,
            created_by_name=created_by_name,
            created_at=now,
            updated_at=now,
        )

    async def add_step(
        self,
        mission_id: str,
        *,
        position: int,
        step: str,
        detail: str,
        citations: tuple[str, ...] = (),
    ) -> None:
        async with self._database.pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO policy_mission_steps (id, mission_id, position, step, detail, citations)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                """,
                str(uuid.uuid4()),
                mission_id,
                position,
                step,
                detail,
                json.dumps(list(citations)),
            )

    async def set_status(
        self, tenant_id: str, mission_id: str, *, status: str, awaiting_approval: bool
    ) -> None:
        async with self._database.pool.acquire() as connection:
            await connection.execute(
                """
                UPDATE policy_missions
                SET status = $3, awaiting_approval = $4, updated_at = $5
                WHERE tenant_id = $1 AND id = $2
                """,
                tenant_id,
                mission_id,
                status,
                awaiting_approval,
                datetime.now(timezone.utc),
            )

    async def get(self, tenant_id: str, mission_id: str) -> MissionRecord | None:
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                "SELECT * FROM policy_missions WHERE tenant_id = $1 AND id = $2",
                tenant_id,
                mission_id,
            )
            if row is None:
                return None
            step_rows = await connection.fetch(
                "SELECT * FROM policy_mission_steps WHERE mission_id = $1 ORDER BY position",
                mission_id,
            )
        steps = tuple(
            MissionStepRecord(
                id=step_row["id"],
                position=step_row["position"],
                step=step_row["step"],
                detail=step_row["detail"],
                citations=tuple(json.loads(step_row["citations"])),
                created_at=step_row["created_at"],
            )
            for step_row in step_rows
        )
        return MissionRecord(
            id=row["id"],
            tenant_id=row["tenant_id"],
            agent=row["agent"],
            goal=row["goal"],
            status=row["status"],
            awaiting_approval=row["awaiting_approval"],
            created_by_user_id=row["created_by_user_id"],
            created_by_name=row["created_by_name"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            steps=steps,
        )

    async def list(self, tenant_id: str) -> list[MissionRecord]:
        async with self._database.pool.acquire() as connection:
            rows = await connection.fetch(
                "SELECT * FROM policy_missions WHERE tenant_id = $1 ORDER BY created_at DESC",
                tenant_id,
            )
        return [
            MissionRecord(
                id=row["id"],
                tenant_id=row["tenant_id"],
                agent=row["agent"],
                goal=row["goal"],
                status=row["status"],
                awaiting_approval=row["awaiting_approval"],
                created_by_user_id=row["created_by_user_id"],
                created_by_name=row["created_by_name"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]
