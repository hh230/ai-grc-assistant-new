"""Vendor Review, end to end — real, coherent, over the customer's own data (P1 + ADR 0051): it
gathers the ISO supplier controls (framework library) and the vendor's ingested evidence
(local_search), then assesses the vendor (generate_text) *from* both.
"""

from __future__ import annotations

from assistant_runtime.builtin import build_vendor_review_plan
from event_bus.bus import RecordingEventBus
from grc_assistant import build_grc_orchestrator, build_grc_tool_registry
from knowledge_runtime import TenantKnowledgeBase, ingest_document
from mission_engine import InMemoryMissionStore, MissionEngine, MissionStatus
from pipeline_contracts import TenantContext
from pipeline_tool import RegistryExecutor

_ACME = TenantContext(tenant_id="org_acme", principal_id="u1", roles=("analyst",))
_VENDOR_DOC = (
    "Acme Cloud SOC 2 report summary: encryption at rest and in transit; annual penetration "
    "testing; a documented incident response plan; sub-processors are disclosed."
)


def test_vendor_review_reads_vendor_evidence_then_assesses(generation_provider) -> None:
    kb = TenantKnowledgeBase()
    ingest_document(
        kb, _VENDOR_DOC, tenant=_ACME, document_id="d1", source_filename="acme-cloud-soc2.txt"
    )
    orchestrator = build_grc_orchestrator(kb.keyword_provider(), generation_provider)
    registry = build_grc_tool_registry(orchestrator, generation_provider, kb.keyword_provider())
    engine = MissionEngine(
        InMemoryMissionStore(), RegistryExecutor(registry), events=RecordingEventBus()
    )

    goal, plan = build_vendor_review_plan({"request": "Acme Cloud"}, _ACME)
    mission = engine.create(goal, _ACME)
    engine.plan(mission, plan)
    engine.execute(mission)

    assert mission.status is MissionStatus.COMPLETED
    controls, evidence, assessment = mission.step_results

    # step 1 — real ISO supplier controls (A.5.19–A.5.23) from the framework library
    assert controls.ok and "iso_27001:A.5.19" in controls.source_ids
    # step 2 — the vendor's own ingested evidence (search)
    assert evidence.ok and "penetration" in evidence.output
    # step 3 — the assessment, synthesised FROM the supplier controls AND the vendor evidence
    assert assessment.output.startswith("SYNTHESIS[")
    assert "penetration" in assessment.output
