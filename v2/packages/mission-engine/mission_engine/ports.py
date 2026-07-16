"""The two ports the Mission Engine reaches the world through (ADR 0042 §12.3).

**Ports before adapters.** The engine depends only on these `Protocol`s, never on a concrete
tool, agent, database, or the pipeline. The first package ships trivial reference adapters
(`adapters.py`); later phases swap them — a Pipeline-Tool executor (step 3), a Postgres
Mission Store (step 4) — with **zero change** to the aggregate or the engine.

- `ExecutionPort` is the *single seam to all step execution* (§12.3). Tools, Agents, and the
  pipeline are all reached through it. The engine dispatches a `StepRequest` and records the
  returned `StepResult`; it never calls a tool or the Tool Registry itself (§3, §5).
- `MissionStorePort` is the *single persistence seam* (§11: every mission is stored). The
  engine holds no schema, SQL, or driver. Reads are tenant-scoped by construction: a store
  never returns a mission to a foreign tenant.

`StepRequest` / `StepResult` are the pure data crossing the execution seam. `StepResult`
mirrors what a `PipelineResult` maps down to (text, citations, confidence, cost), so the
engine can compose it into the mission record and, later, the audit narrative (§2.8) without
knowing anything about how the step ran.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pipeline_contracts import TenantContext, dataclass_dict

if TYPE_CHECKING:  # avoid a runtime import cycle: mission.py imports StepResult from here.
    from mission_engine.mission import Mission


@dataclass(frozen=True)
class StepRequest:
    """What the engine hands the executor for one step. It carries the mission's
    `TenantContext` **unchanged** (ADR 0040 §5): the executor runs *within* that tenant and
    cannot widen it. `instruction` is the opaque payload from the `PlanStep`."""

    mission_id: str
    step_id: str
    tenant: TenantContext
    instruction: str
    consequential: bool = False

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)


@dataclass(frozen=True)
class StepResult:
    """The outcome of one executed step, in the shape the Mission Engine composes into the
    mission record. `ok=False` marks a failed step — the engine then fails the mission safe
    (ADR 0042 §7). Citations/confidence/source_ids carry the grounding an audit needs; they
    are empty for a trivial echo step and populated once the Pipeline Tool backs the port."""

    step_id: str
    ok: bool = True
    output: str = ""
    citations: tuple[str, ...] = ()
    confidence: float | None = None
    source_ids: tuple[str, ...] = ()
    latency_ms: float = 0.0
    estimated_cost: float | None = None
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)


@runtime_checkable
class ExecutionPort(Protocol):
    """The single seam to all step execution (ADR 0042 §12.3). An implementation resolves the
    step to Tools / Agents / the pipeline and runs it; the Mission Engine only dispatches a
    `StepRequest` and records the `StepResult`."""

    def execute(self, request: StepRequest) -> StepResult: ...


@runtime_checkable
class MissionStorePort(Protocol):
    """The single persistence seam. The engine holds no schema, SQL, or driver (§3, §12.3);
    it calls only these three methods. Every read is tenant-scoped: `get` and
    `find_by_idempotency_key` take a `TenantContext` and never return another tenant's mission
    (ADR 0040 §5)."""

    def save(self, mission: Mission) -> None: ...

    def get(self, mission_id: str, tenant: TenantContext) -> Mission | None: ...

    def find_by_idempotency_key(self, tenant: TenantContext, key: str) -> Mission | None: ...
