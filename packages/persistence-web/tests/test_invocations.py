"""Integration tests for PostgresToolInvocationRecorder against `ai_tool_invocations`."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from grc_persistence_web import Database, PostgresToolInvocationRecorder
from grc_tools import InvocationStatus, ToolInvocationRecord


async def test_record_writes_a_row(database: Database) -> None:
    recorder = PostgresToolInvocationRecorder(database)
    tenant_id = f"test-tenant-{uuid.uuid4()}"
    invocation_id = str(uuid.uuid4())
    entry = ToolInvocationRecord(
        id=invocation_id,
        tenant_id=tenant_id,
        tool_name="scan_policy_coverage_gaps",
        tool_version="1.0.0",
        caller="orchestrator",
        status=InvocationStatus.SUCCEEDED,
        requires_human_approval=False,
        agent="policy_hunter_agent",
        model="gpt-4o-mini",
        prompt_version="scan_policy_coverage_gaps.v1",
        inputs_hash="deadbeef",
        confidence=0.75,
        citations=("framework:iso_27001:A.5.15",),
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        latency_ms=42,
        cost_usd=0.001,
        created_at=datetime.now(timezone.utc),
    )
    try:
        await recorder.record(entry)
        async with database.pool.acquire() as connection:
            row = await connection.fetchrow(
                "SELECT * FROM ai_tool_invocations WHERE id = $1", invocation_id
            )
        assert row is not None
        assert row["tool_name"] == "scan_policy_coverage_gaps"
        assert row["status"] == "succeeded"
        assert row["confidence"] == 0.75
        assert row["agent"] == "policy_hunter_agent"
    finally:
        async with database.pool.acquire() as connection:
            await connection.execute(
                "DELETE FROM ai_tool_invocations WHERE tenant_id = $1", tenant_id
            )
