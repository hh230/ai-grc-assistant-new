"""The codec is the crux: it must round-trip the `Mission` aggregate through a plain row with zero
loss — including the full plan-version history that `Mission.to_dict()` does not expose — and it
must carry and honour `payload_schema_version`. No database needed."""

from __future__ import annotations

import pytest
from mission_engine import ExecutionProfile, Mission, MissionStatus, Plan, PlanStep
from mission_store.codec import COLUMNS, CURRENT_PAYLOAD_VERSION, mission_from_row, mission_to_row
from mission_store.errors import (
    MissionStoreError,
    SerializationError,
    UnsupportedPayloadSchemaVersion,
)
from pipeline_contracts import TenantContext


def _assert_equivalent(original: Mission, restored: Mission) -> None:
    assert restored.to_dict() == original.to_dict()
    assert [p.to_dict() for p in restored.plan_versions] == [
        p.to_dict() for p in original.plan_versions
    ]


def test_row_has_exactly_the_declared_columns(rich_mission: Mission) -> None:
    assert tuple(mission_to_row(rich_mission).keys()) == COLUMNS


def test_row_carries_the_current_payload_version(rich_mission: Mission) -> None:
    assert mission_to_row(rich_mission)["payload_schema_version"] == CURRENT_PAYLOAD_VERSION


def test_rich_mission_round_trips_without_loss(rich_mission: Mission) -> None:
    restored = mission_from_row(mission_to_row(rich_mission))
    _assert_equivalent(rich_mission, restored)
    assert restored.status is MissionStatus.PLANNED
    assert restored.execution_profile is ExecutionProfile.COMPOSITE
    assert restored.plan_version == 2
    assert len(restored.plan_versions) == 2
    assert restored.idempotency_key == "k-rich"
    step = restored.step_results[0]
    assert step.citations == ("nca_ecc:2-3-1",)
    assert step.confidence == 0.87
    assert step.source_ids == ("src_1", "src_2")
    assert step.estimated_cost == 0.0031
    assert step.warnings == ("thin evidence",)


def test_simple_completed_mission_round_trips(simple_mission: Mission) -> None:
    restored = mission_from_row(mission_to_row(simple_mission))
    _assert_equivalent(simple_mission, restored)
    assert restored.status is MissionStatus.COMPLETED
    assert restored.execution_profile is ExecutionProfile.SIMPLE
    assert len(restored.step_results) == 1


def test_freshly_created_mission_has_no_plan(tenant: TenantContext) -> None:
    mission = Mission.create(goal="just born", tenant=tenant)
    row = mission_to_row(mission)
    assert row["plan"] is None and row["plan_versions"] == []
    restored = mission_from_row(row)
    assert restored.plan is None
    assert restored.execution_profile is None
    assert restored.status is MissionStatus.CREATED
    _assert_equivalent(mission, restored)


def test_tenant_fields_survive_the_round_trip(rich_mission: Mission) -> None:
    restored = mission_from_row(mission_to_row(rich_mission))
    assert restored.tenant.tenant_id == "org_acme"
    assert restored.tenant.principal_id == "u_owner"
    assert restored.tenant.roles == ("owner", "admin")
    assert restored.tenant.region == "ksa"


def test_unknown_payload_version_fails_loud(rich_mission: Mission) -> None:
    row = mission_to_row(rich_mission)
    row["payload_schema_version"] = CURRENT_PAYLOAD_VERSION + 1
    with pytest.raises(UnsupportedPayloadSchemaVersion) as exc_info:
        mission_from_row(row)
    err = exc_info.value
    assert err.found == CURRENT_PAYLOAD_VERSION + 1
    assert err.supported == CURRENT_PAYLOAD_VERSION
    assert err.mission_id == rich_mission.id


def test_unsupported_payload_version_is_a_serialization_error() -> None:
    # the taxonomy: UnsupportedPayloadSchemaVersion → SerializationError → MissionStoreError
    assert issubclass(UnsupportedPayloadSchemaVersion, SerializationError)
    assert issubclass(SerializationError, MissionStoreError)


# --- ADR 0048: per-step tool selection round-trips through the plan codec ----------------

def test_per_step_tool_survives_the_round_trip(tenant: TenantContext) -> None:
    mission = Mission.create(goal="multi-tool", tenant=tenant)
    mission.set_plan(
        Plan(
            steps=(
                PlanStep(description="collect_context", instruction="gather", tool="collect"),
                PlanStep(description="assess_risk", instruction="score", tool="assess"),
            )
        )
    )
    restored = mission_from_row(mission_to_row(mission))
    assert restored.plan is not None
    assert tuple(s.tool for s in restored.plan.steps) == ("collect", "assess")
    _assert_equivalent(mission, restored)


def test_legacy_plan_without_tool_reads_as_empty_without_a_version_bump(
    tenant: TenantContext,
) -> None:
    # A plan JSON written before ADR 0048 has no "tool" key on its steps; it must deserialize as
    # tool="" at the CURRENT payload version — no version bump, no migration (ADR 0048 §4).
    mission = Mission.create(goal="legacy", tenant=tenant)
    mission.set_plan(Plan(steps=(PlanStep(description="s", instruction="i", tool="x"),)))
    row = mission_to_row(mission)
    for step in row["plan"]["steps"]:  # simulate an old row: strip the field the codec now writes
        del step["tool"]
    row["payload_schema_version"] = CURRENT_PAYLOAD_VERSION  # still current — no bump required

    restored = mission_from_row(row)
    assert restored.plan is not None
    assert restored.plan.steps[0].tool == ""
