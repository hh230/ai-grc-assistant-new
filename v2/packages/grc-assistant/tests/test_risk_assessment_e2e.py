"""Risk Assessment E2E — **real, coherent, over the customer's own data** (P1 + ADR 0051):
`collect_context` (local_search) retrieves the tenant's ingested evidence; the two synthesis steps
(generate_text) build *from* it. Proven by the gather returning the ingested chunk and the synthesis
output reflecting it.
"""

from __future__ import annotations

from assistant_runtime.builtin import build_risk_assessment_plan
from assistant_runtime.builtin.risk_assessment import GENERATE_TEXT_TOOL as CAPABILITY_GENERATE_TOOL
from assistant_runtime.builtin.risk_assessment import LOCAL_SEARCH_TOOL as CAPABILITY_SEARCH_TOOL
from event_bus.bus import RecordingEventBus
from grc_assistant import build_grc_orchestrator, build_grc_tool_registry
from knowledge_runtime import TenantKnowledgeBase, ingest_document
from llm_tools import GENERATE_TEXT_TOOL
from mission_engine import InMemoryMissionStore, MissionEngine, MissionStatus
from pipeline_contracts import TenantContext
from pipeline_tool import RegistryExecutor
from search_tools import LOCAL_SEARCH_TOOL

_ACME = TenantContext(tenant_id="org_acme", principal_id="u1", roles=("analyst",))
_EVIDENCE = (
    "Acme remote access standard: privileged VPN sessions require hardware security keys and are "
    "logged. No shared administrator accounts are permitted."
)


def test_capability_tool_names_match_the_registered_tools() -> None:
    assert CAPABILITY_SEARCH_TOOL == LOCAL_SEARCH_TOOL
    assert CAPABILITY_GENERATE_TOOL == GENERATE_TEXT_TOOL


def test_risk_assessment_reads_customer_data_then_synthesises(generation_provider) -> None:
    kb = TenantKnowledgeBase()
    chunks = ingest_document(
        kb, _EVIDENCE, tenant=_ACME, document_id="d1", source_filename="remote-access.txt"
    )
    orchestrator = build_grc_orchestrator(kb.keyword_provider(), generation_provider)
    registry = build_grc_tool_registry(orchestrator, generation_provider, kb.keyword_provider())
    engine = MissionEngine(
        InMemoryMissionStore(), RegistryExecutor(registry), events=RecordingEventBus()
    )

    goal, plan = build_risk_assessment_plan({"request": "hardware security keys"}, _ACME)
    mission = engine.create(goal, _ACME)
    engine.plan(mission, plan)
    engine.execute(mission)

    assert mission.status is MissionStatus.COMPLETED
    collect, assess, report = mission.step_results

    # step 1 — gathered the CUSTOMER's own ingested evidence (tenant-scoped search)
    assert collect.ok
    assert {c.chunk_id for c in chunks} & set(collect.source_ids)
    assert "hardware security keys" in collect.output

    # step 2 — the assessment, generated FROM the gathered evidence (coherence)
    assert assess.output.startswith("SYNTHESIS[")
    assert collect.output in assess.output

    # step 3 — the report, generated FROM the evidence AND the assessment
    assert collect.output in report.output
    assert assess.output in report.output
