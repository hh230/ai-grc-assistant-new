"""The `MissionCatalog` — the execution registry (ADR 0046 §4).

A **Mission type is exactly a plan factory** `(inputs, tenant) → (goal, Plan)` (ADR 0042 §11:
missions differ by their plan, not by a class/store/execution path). The catalog registers those
factories by id and builds a `(goal, Plan)` on demand, reusing the **frozen** `mission-engine` plan
types. It holds **no** other logic: it does not select capabilities, run missions, or persist
anything.

The plan factory is where a Mission *type* declares its shape (its steps, and which are
`consequential`/human-gated). In Slice 2 factories build plan *structure* only — the steps are run
by whatever `ExecutionPort` backs the injected Mission Engine (the reference `EchoExecutor` until
the real Pipeline-Tool executor lands). No tools, no real work here.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from mission_engine import Plan
from pipeline_contracts import TenantContext

from assistant_runtime.errors import UnknownMissionType

# A plan factory: turns inputs + the tenant into the mission's goal and its Plan. Pure w.r.t. the
# Core — it constructs frozen `mission-engine` plan objects and returns them; it never touches a
# store, a bus, or an LLM.
PlanFactory = Callable[[Mapping[str, Any], TenantContext], "tuple[str, Plan]"]


@dataclass(frozen=True)
class MissionType:
    """A registered Mission type: an id + its plan factory. Nothing more (ADR 0046 §4)."""

    id: str
    plan_factory: PlanFactory


class MissionCatalog:
    """A registry of `MissionType` by id, with a `build` that invokes the factory."""

    def __init__(self, mission_types: Iterable[MissionType] = ()) -> None:
        self._by_id: dict[str, MissionType] = {}
        for mission_type in mission_types:
            self.register(mission_type)

    def register(self, mission_type: MissionType) -> None:
        if mission_type.id in self._by_id:
            raise ValueError(f"mission type {mission_type.id!r} is already registered")
        self._by_id[mission_type.id] = mission_type

    def get(self, mission_type_id: str) -> MissionType | None:
        return self._by_id.get(mission_type_id)

    def __contains__(self, mission_type_id: object) -> bool:
        return mission_type_id in self._by_id

    def build(
        self, mission_type_id: str, inputs: Mapping[str, Any], tenant: TenantContext
    ) -> tuple[str, Plan]:
        """Build `(goal, Plan)` for a Mission type. Raises `UnknownMissionType` loudly if the id is
        not registered — a capability that resolves to a missing Mission type is a catalog wiring
        bug, never a silent miss."""
        mission_type = self._by_id.get(mission_type_id)
        if mission_type is None:
            raise UnknownMissionType(mission_type_id)
        return mission_type.plan_factory(inputs, tenant)
