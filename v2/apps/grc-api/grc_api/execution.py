"""The production `ExecutionPort` — the Wave 1 executor wiring (ADR 0066 §3).

Until now `create_app` defaulted to `EchoExecutor`, so every mission step returned
`"echo: <input>"`. The Governance Plan Mission's third step is supposed to emit a JSON draft, so
the whole Discovery → Report → Plan journey ended at *"The governance plan draft was not valid
JSON."* The tools, the registry and the executor all existed and were proven end-to-end by
`tests/production/test_governance_plan_e2e.py`; only this composition was missing.

**Composition only.** No new domain, no new port, no new tool — the four tools, the frozen
`ToolRegistry` and the frozen `RegistryExecutor` are used exactly as they are. Each step resolves
to its own tool via `PlanStep.tool` (ADR 0048), so this file never branches on step identity.

**Why the registry is built per step rather than once at startup.** `PostgresGovernanceStore`
opens a connection in its constructor and holds it for its lifetime, so a registry built once at
app construction would share a single connection across every concurrent request — and ADR 0055 is
explicit that no durable store lives at app scope ("what is long-lived is configuration, never a
store"). `create_app` already draws governance stores from a per-request `discovery_store_factory`
for exactly this reason; this executor draws from the same seam and closes what it opens. Building
four small tool objects per step is negligible next to the LLM call inside one of them.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from framework_library import ControlLibraryTool, FrameworkLibrary
from governance_discovery.engine import DiscoveryEngine
from governance_plan_tools.applicability_tool import OrgApplicabilityTool
from governance_plan_tools.draft_tool import PlanDraftTool
from governance_plan_tools.finalize_tool import PlanFinalizeTool
from mission_engine import StepRequest, StepResult
from pipeline_tool import RegistryExecutor
from tool_registry import ToolRegistry


class _Store(Protocol):
    def close(self) -> None: ...


class GovernancePlanExecutor:
    """Runs a Governance Plan Mission step against the real tools.

    Holds only configuration: a store *factory*, the stateless discovery engine, the bundled
    framework library, and the generation provider. Nothing per-request survives a call.
    """

    def __init__(
        self,
        *,
        store_factory: Callable[[], Any],
        discovery_engine: DiscoveryEngine,
        generation_provider: Any,
        frameworks: FrameworkLibrary | None = None,
    ) -> None:
        self._store_factory = store_factory
        self._discovery_engine = discovery_engine
        self._generation_provider = generation_provider
        # Pure data, loaded once — the library is immutable and shared safely (the same reason
        # `create_app` builds one DiscoveryEngine for every request).
        self._frameworks = frameworks if frameworks is not None else FrameworkLibrary.from_bundled()

    def _registry(self, store: Any) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(OrgApplicabilityTool(store))
        registry.register(ControlLibraryTool(self._frameworks))
        # `now` / `new_id` are left at their real defaults (time.time / uuid4). The E2E suite pins
        # them to fixed values through its own construction; production must not.
        registry.register(PlanDraftTool(store, self._generation_provider))
        registry.register(PlanFinalizeTool(store, self._discovery_engine))
        return registry

    def execute(self, request: StepRequest) -> StepResult:
        store: Any = self._store_factory()
        try:
            return RegistryExecutor(self._registry(store)).execute(request)
        finally:
            # The store owns a connection; leaking one per step exhausts a managed Postgres long
            # before CPU becomes the ceiling (the same reasoning behind the B3 pool).
            close = getattr(store, "close", None)
            if callable(close):
                close()
