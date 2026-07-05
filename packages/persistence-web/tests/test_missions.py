"""Integration tests for PolicyMissionStore against `policy_missions`/`policy_mission_steps`."""

from __future__ import annotations

import uuid

from grc_persistence_web import Database, PolicyMissionStore


async def test_create_add_step_and_get_round_trip(database: Database) -> None:
    tenant_id = f"test-tenant-{uuid.uuid4()}"
    store = PolicyMissionStore(database)
    try:
        mission = await store.create(
            tenant_id=tenant_id,
            agent="policy_hunter_agent",
            goal="Scan for policy coverage gaps against ISO 27001",
            created_by_user_id="user-compliance",
            created_by_name="Carla Compliance",
        )
        await store.add_step(
            mission.id,
            position=0,
            step="plan",
            detail="routed to policy_hunter_agent",
        )
        await store.add_step(
            mission.id,
            position=1,
            step="execute",
            detail="found 2 coverage gaps",
            citations=("framework:iso_27001:A.5.15",),
        )
        await store.set_status(tenant_id, mission.id, status="completed", awaiting_approval=False)

        fetched = await store.get(tenant_id, mission.id)
        assert fetched is not None
        assert fetched.status == "completed"
        assert [step.step for step in fetched.steps] == ["plan", "execute"]
        assert fetched.steps[1].citations == ("framework:iso_27001:A.5.15",)

        listed = await store.list(tenant_id)
        assert [record.id for record in listed] == [mission.id]
    finally:
        async with database.pool.acquire() as connection:
            await connection.execute("DELETE FROM policy_missions WHERE tenant_id = $1", tenant_id)
