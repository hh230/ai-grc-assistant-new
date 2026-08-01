"""End to end: a Mission reads a real document through the real `RegistryExecutor`, the step routing
to `read_pdf` via `PlanStep.tool` (ADR 0048) — proof a document tool plugs into the frozen execution
path with no Core change. In-memory store, so it runs anywhere."""

from __future__ import annotations

from pathlib import Path

from document_tools import READ_PDF_TOOL, build_pdf_reader
from event_bus.bus import RecordingEventBus
from mission_engine import InMemoryMissionStore, MissionEngine, MissionStatus, Plan, PlanStep
from pipeline_contracts import TenantContext
from pipeline_tool import RegistryExecutor
from tool_registry import ToolRegistry


def test_a_mission_reads_a_real_pdf_through_the_executor(doc_root: Path) -> None:
    registry = ToolRegistry()
    registry.register(build_pdf_reader(doc_root))
    engine = MissionEngine(
        InMemoryMissionStore(),
        RegistryExecutor(registry, tool_name=READ_PDF_TOOL),
        events=RecordingEventBus(),
    )
    tenant = TenantContext(tenant_id="org_acme", principal_id="u1")

    mission = engine.create("read evidence", tenant)
    engine.plan(
        mission,
        Plan(steps=(PlanStep(description="read pdf", instruction="confidentiality.pdf",
                             tool=READ_PDF_TOOL),)),
    )
    engine.execute(mission)

    assert mission.status is MissionStatus.COMPLETED
    step = mission.step_results[0]
    assert step.ok
    assert "Confidentiality Policy" in step.output          # real extracted text flowed back
    assert step.source_ids == ("confidentiality.pdf",)


def test_a_mission_fails_safe_when_the_document_is_missing(doc_root: Path) -> None:
    registry = ToolRegistry()
    registry.register(build_pdf_reader(doc_root))
    engine = MissionEngine(
        InMemoryMissionStore(),
        RegistryExecutor(registry, tool_name=READ_PDF_TOOL),
        events=RecordingEventBus(),
    )
    tenant = TenantContext(tenant_id="org_acme", principal_id="u1")

    mission = engine.run_simple("read missing", tenant, "does-not-exist.pdf")
    assert mission.status is MissionStatus.FAILED   # ok=False step → mission fails safe (§7)
