"""Policy Generator, end to end — real, coherent, over the customer's own data (P1 + ADR 0051): it
gathers the ISO controls (framework library) and the tenant's ingested guidance (local_search), then
drafts the policy (generate_text) *from* both.
"""

from __future__ import annotations

from assistant_runtime.builtin import build_policy_generator_plan
from event_bus.bus import RecordingEventBus
from grc_assistant import build_grc_orchestrator, build_grc_tool_registry
from knowledge_runtime import TenantKnowledgeBase, ingest_document
from mission_engine import InMemoryMissionStore, MissionEngine, MissionStatus
from pipeline_contracts import TenantContext
from pipeline_tool import RegistryExecutor

_ACME = TenantContext(tenant_id="org_acme", principal_id="u1", roles=("analyst",))
_GUIDANCE = (
    "Acme access control guidance: least-privilege by default; quarterly access reviews; "
    "joiner-mover-leaver process enforced for all systems."
)


def test_policy_generator_reads_customer_data_then_drafts(generation_provider) -> None:
    kb = TenantKnowledgeBase()
    ingest_document(
        kb, _GUIDANCE, tenant=_ACME, document_id="d1", source_filename="ac-guidance.txt"
    )
    orchestrator = build_grc_orchestrator(kb.keyword_provider(), generation_provider)
    registry = build_grc_tool_registry(orchestrator, generation_provider, kb.keyword_provider())
    engine = MissionEngine(
        InMemoryMissionStore(), RegistryExecutor(registry), events=RecordingEventBus()
    )

    goal, plan = build_policy_generator_plan({"request": "access control"}, _ACME)
    mission = engine.create(goal, _ACME)
    engine.plan(mission, plan)
    engine.execute(mission)

    assert mission.status is MissionStatus.COMPLETED
    controls, guidance, draft = mission.step_results

    # step 1 — real ISO controls from the framework library
    assert controls.ok and "A.5.15 Access control" in controls.output
    # step 2 — the tenant's own ingested guidance (search)
    assert guidance.ok and "least-privilege" in guidance.output
    # step 3 — the draft, synthesised FROM the controls AND the customer's guidance (coherence)
    assert draft.output.startswith("SYNTHESIS[")
    assert "A.5.15 Access control" in draft.output
    assert "least-privilege" in draft.output
