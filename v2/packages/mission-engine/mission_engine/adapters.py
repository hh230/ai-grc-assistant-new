"""Trivial reference adapters for the two ports (ADR 0042 §12.3).

These exist so the first package runs end-to-end and so the engine can be tested against real
port implementations. They are **explicitly not** the production implementations:

- `EchoExecutor` stands in for the Pipeline-Tool executor (step 3). It returns a `StepResult`
  that echoes the instruction, with no grounding, and performs no I/O and calls no tool. When
  the Pipeline Tool lands, it implements the same `ExecutionPort` and drops in unchanged.
- `InMemoryMissionStore` stands in for the Postgres Mission Store (step 4). It holds missions
  in a per-tenant dict — tenant isolation by construction: a mission is filed under its own
  tenant and a lookup from another tenant simply does not find it. It is **not persistence**;
  nothing survives the process. The real store (ADR 0012) lands later behind the same port.
"""

from __future__ import annotations

from pipeline_contracts import TenantContext

from mission_engine.mission import Mission
from mission_engine.ports import StepRequest, StepResult


class EchoExecutor:
    """A no-grounding `ExecutionPort`: echoes the step instruction back as output. Reference
    executor only — the Pipeline Tool replaces it in a later step."""

    def execute(self, request: StepRequest) -> StepResult:
        return StepResult(
            step_id=request.step_id,
            ok=True,
            output=f"echo: {request.instruction}",
            confidence=None,
        )


class InMemoryMissionStore:
    """A non-persistent reference `MissionStorePort`, tenant-scoped by construction. Missions
    live in `{tenant_id: {mission_id: Mission}}`, so a read for one tenant can never surface
    another tenant's mission (ADR 0040 §5). Not durable storage — a real sink arrives later."""

    def __init__(self) -> None:
        self._by_tenant: dict[str, dict[str, Mission]] = {}

    def _bucket(self, tenant_id: str) -> dict[str, Mission]:
        return self._by_tenant.setdefault(tenant_id, {})

    def save(self, mission: Mission) -> None:
        self._bucket(mission.tenant_id)[mission.id] = mission

    def get(self, mission_id: str, tenant: TenantContext) -> Mission | None:
        # Only ever look inside the caller's own tenant bucket — cross-tenant reads cannot
        # happen because we never consult another tenant's bucket.
        return self._by_tenant.get(tenant.tenant_id, {}).get(mission_id)

    def find_by_idempotency_key(self, tenant: TenantContext, key: str) -> Mission | None:
        if not key:
            return None
        for mission in self._by_tenant.get(tenant.tenant_id, {}).values():
            if mission.idempotency_key == key:
                return mission
        return None
