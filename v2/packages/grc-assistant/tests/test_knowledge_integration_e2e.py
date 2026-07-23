"""Runtime Knowledge Integration (product roadmap P1) — the value inflection: a capability now
answers over the **customer's own ingested data**, not the global library alone.

    ingest customer doc → TenantKnowledgeBase → build_grc_orchestrator(kb) → run_pipeline (in a
    capability) retrieves the customer's content, tenant-scoped.

Proven by the capability's grounded gather step returning the ingested chunk's id in its provenance;
and a different tenant's run cannot reach that data (fail-closed).
"""

from __future__ import annotations

from assistant_runtime.builtin import build_risk_assessment_plan
from event_bus.bus import RecordingEventBus
from grc_assistant import build_grc_orchestrator, build_grc_tool_registry
from knowledge_runtime import TenantKnowledgeBase, ingest_document
from mission_engine import InMemoryMissionStore, MissionEngine, MissionStatus
from pipeline_contracts import TenantContext
from pipeline_tool import RegistryExecutor

_ACME = TenantContext(tenant_id="org_acme", principal_id="u1", roles=("analyst",))
_GLOBEX = TenantContext(tenant_id="org_globex", principal_id="u9", roles=("analyst",))

_POLICY = (
    "Acme access control policy. All administrator accounts must use hardware security keys for "
    "multi-factor authentication. Shared administrator credentials are prohibited."
)


def _engine(kb: TenantKnowledgeBase, generation_provider) -> MissionEngine:
    orchestrator = build_grc_orchestrator(kb.keyword_provider(), generation_provider)
    registry = build_grc_tool_registry(orchestrator, generation_provider, kb.keyword_provider())
    return MissionEngine(
        InMemoryMissionStore(), RegistryExecutor(registry), events=RecordingEventBus()
    )


def test_a_capability_answers_over_the_tenants_ingested_data(generation_provider) -> None:
    kb = TenantKnowledgeBase()
    chunks = ingest_document(
        kb, _POLICY, tenant=_ACME, document_id="doc-acme-1", source_filename="acme-policy.txt"
    )
    engine = _engine(kb, generation_provider)

    goal, plan = build_risk_assessment_plan({"request": "hardware security keys"}, _ACME)
    mission = engine.create(goal, _ACME)
    engine.plan(mission, plan)
    engine.execute(mission)

    assert mission.status is MissionStatus.COMPLETED
    collect_context = mission.step_results[0]           # the grounded gather step (run_pipeline)
    ingested_ids = {c.chunk_id for c in chunks}
    # the capability retrieved the CUSTOMER's own document, not just the global library
    assert ingested_ids & set(collect_context.source_ids)


def test_another_tenant_cannot_read_the_first_tenants_data(generation_provider) -> None:
    kb = TenantKnowledgeBase()
    ingest_document(
        kb, _POLICY, tenant=_ACME, document_id="doc-acme-1", source_filename="acme-policy.txt"
    )
    engine = _engine(kb, generation_provider)

    # org_globex runs the same capability; its query matches acme's out-of-scope chunk → the
    # engine's defence-in-depth refuses, the step fails, and the mission fails safe. Never a leak.
    goal, plan = build_risk_assessment_plan({"request": "hardware security keys"}, _GLOBEX)
    mission = engine.create(goal, _GLOBEX)
    engine.plan(mission, plan)
    engine.execute(mission)

    assert mission.status is MissionStatus.FAILED
    assert mission.step_results == []                   # nothing from acme's data was recorded
