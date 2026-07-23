"""Gap Assessment, end to end — the flagship: **the framework's required controls next to the
customer's own evidence → a gap** (P1 integration + ADR 0051). Proven by the gap synthesis output
containing both the real ISO controls and the customer's ingested evidence.
"""

from __future__ import annotations

from assistant_runtime.builtin import build_gap_assessment_plan
from event_bus.bus import RecordingEventBus
from grc_assistant import build_grc_orchestrator, build_grc_tool_registry
from knowledge_runtime import TenantKnowledgeBase, ingest_document
from mission_engine import InMemoryMissionStore, MissionEngine, MissionStatus
from pipeline_contracts import TenantContext
from pipeline_tool import RegistryExecutor

_ACME = TenantContext(tenant_id="org_acme", principal_id="u1", roles=("analyst",))
_EVIDENCE = (
    "Acme security controls implemented: secure authentication uses hardware keys; data is "
    "encrypted at rest and in transit; centralized logging is enabled for all systems."
)


def test_gap_assessment_puts_controls_next_to_evidence(generation_provider) -> None:
    kb = TenantKnowledgeBase()
    ingest_document(
        kb, _EVIDENCE, tenant=_ACME, document_id="d1", source_filename="acme-controls.txt"
    )
    orchestrator = build_grc_orchestrator(kb.keyword_provider(), generation_provider)
    registry = build_grc_tool_registry(orchestrator, generation_provider, kb.keyword_provider())
    engine = MissionEngine(
        InMemoryMissionStore(), RegistryExecutor(registry), events=RecordingEventBus()
    )

    goal, plan = build_gap_assessment_plan({"request": "Technological"}, _ACME)
    mission = engine.create(goal, _ACME)
    engine.plan(mission, plan)
    engine.execute(mission)

    assert mission.status is MissionStatus.COMPLETED
    controls, evidence, gap = mission.step_results

    # step 1 — what the framework REQUIRES: the real ISO Technological controls
    assert controls.ok
    assert "A.8.5 Secure authentication" in controls.output
    assert "iso_27001:A.8.5" in controls.source_ids

    # step 2 — what the customer ACTUALLY HAS: their own ingested evidence
    assert evidence.ok
    assert "implemented" in evidence.output

    # step 3 — the gap: the synthesis reads BOTH the required controls and the customer's evidence
    assert gap.output.startswith("SYNTHESIS[")
    assert "A.8.5 Secure authentication" in gap.output      # a required control fed the gap
    assert "hardware keys" in gap.output                    # the customer's evidence fed it too
