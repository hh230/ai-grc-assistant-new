"""`AssistantRuntime` — the thin product-layer composition root (ADR 0046 §7).

It wires the two catalogs, the intent recognizer, the selector, and the injected `MissionDriver`,
exposing one Slice-2 entry point: `handle`. It is deliberately **very thin** — it holds no business
logic, no SQL, no tools, no LLM, no session/conversation state (those are later slices). `handle` is
five steps:

    request → intent (LLM suggests) → capability (selector decides) → (goal, Plan) → Mission

and it calls the Core **exactly once** (`MissionDriver.run_transition`). Turning a request into work
is *only* selecting the capability, building the plan, and handing it to the frozen Core.
"""

from __future__ import annotations

from dataclasses import dataclass

from mission_engine import Mission, MissionEngine, MissionStatus, Plan
from pipeline_contracts import TenantContext

from assistant_runtime.capability_catalog import CapabilityCatalog
from assistant_runtime.intent import IntentRecognizer
from assistant_runtime.mission_catalog import MissionCatalog
from assistant_runtime.ports import MissionDriver
from assistant_runtime.selector import CapabilitySelector


@dataclass(frozen=True)
class AssistantResponse:
    """What `handle` returns: which capability was chosen and the Mission it produced. The Mission
    is the source of truth (ADR 0046 §6) — status/progress are read from it, never stored here."""

    capability_id: str
    mission: Mission

    @property
    def mission_id(self) -> str:
        return self.mission.id

    @property
    def status(self) -> MissionStatus:
        return self.mission.status


def _drive(engine: MissionEngine, goal: str, plan: Plan, tenant: TenantContext) -> Mission:
    """Create → plan → execute the mission in one transition. A composite plan with a consequential
    step pauses fail-safe at the gate (the Core's job); resolving that gate is a later slice."""
    mission = engine.create(goal, tenant)
    engine.plan(mission, plan)
    return engine.execute(mission)


class AssistantRuntime:
    """The gateway: request → the right Mission, driven through the frozen Core (ADR 0046)."""

    def __init__(
        self,
        *,
        missions: MissionDriver,
        capabilities: CapabilityCatalog,
        mission_catalog: MissionCatalog,
        intent: IntentRecognizer,
        fallback_capability_id: str = "simple_question",
    ) -> None:
        self._missions = missions
        self._capabilities = capabilities
        self._mission_catalog = mission_catalog
        self._intent = intent
        self._selector = CapabilitySelector(capabilities, fallback_id=fallback_capability_id)

    def handle(self, request: str, tenant: TenantContext) -> AssistantResponse:
        """Resolve a request to a Capability, build its Mission's plan, and drive it through the
        Core in a single `run_transition`. The LLM (intent) *suggests*; the selector *decides*; the
        Core *executes* — the Assistant only routes."""
        intent = self._intent.recognize(request, tenant)  # layer 1: LLM suggests (ref: keyword)
        capability = self._selector.select(intent)  # layer 2: deterministic decides
        goal, plan = self._mission_catalog.build(capability.resolver, intent.inputs, tenant)
        mission = self._missions.run_transition(
            lambda engine: _drive(engine, goal, plan, tenant)
        )
        return AssistantResponse(capability_id=capability.id, mission=mission)
