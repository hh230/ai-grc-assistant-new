"""Integration tests for PolicyRepository against apps/web's live `policies` table."""

from __future__ import annotations

import uuid

from grc_persistence_web import Database, PolicyRepository


async def test_insert_draft_round_trips_provenance(database: Database) -> None:
    tenant_id = f"test-tenant-{uuid.uuid4()}"
    repository = PolicyRepository(database)
    try:
        created = await repository.insert_draft(
            tenant_id=tenant_id,
            title="Access Control Policy",
            summary="Draft generated from a Policy Hunter finding.",
            body="1. Privileged access shall be reviewed quarterly.",
            owner_name="Policy Builder Agent",
            control_ids=("iso_27001:A.5.15",),
            created_by_user_id="agent:policy_builder",
            created_by_name="Policy Builder Agent",
            generated_by_tool="draft_policy.v1",
            generation_metadata={
                "model": "gpt-4o-mini",
                "promptVersion": "draft_policy.v1",
                "confidence": 0.82,
                "citations": ["framework:iso_27001:A.5.15"],
            },
        )

        assert created.status == "draft"
        assert created.ai_generated is True
        assert created.generated_by_tool == "draft_policy.v1"
        assert created.generation_metadata is not None
        assert created.generation_metadata["promptVersion"] == "draft_policy.v1"
        assert created.control_ids == ("iso_27001:A.5.15",)

        fetched = await repository.get(tenant_id, created.id)
        assert fetched is not None
        assert fetched.title == "Access Control Policy"

        listed = await repository.list(tenant_id)
        assert [record.id for record in listed] == [created.id]
    finally:
        async with database.pool.acquire() as connection:
            await connection.execute("DELETE FROM policies WHERE tenant_id = $1", tenant_id)


async def test_get_returns_none_for_unknown_policy(database: Database) -> None:
    repository = PolicyRepository(database)
    tenant_id = f"test-tenant-{uuid.uuid4()}"
    assert await repository.get(tenant_id, str(uuid.uuid4())) is None
