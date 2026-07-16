"""Tenant threading through the pipeline (ADR 0040 §4): the request's tenant becomes the
retrieval scope, and every emitted event/audit record is stamped with tenant + mission."""

from __future__ import annotations

from ai_orchestrator import AIOrchestrator
from context_builder import ContextBuilder
from decision_engine import DecisionEngine
from event_bus.bus import RecordingEventBus
from pipeline_contracts import Filter, KnowledgeScope, TenantContext, UserRequest
from prompt_orchestrator import PromptOrchestrator
from retrieval_engine import RetrievalEngine

from tests.conftest import FakeGenerationProvider

_LOOKUP = "What are the security controls required for personal data?"  # routes to retrieval


class _RecordingSearch:
    def __init__(self) -> None:
        self.filters: list[Filter] = []

    def search(self, query: str, filter: Filter, top_k: int):
        self.filters.append(filter)
        return []


def _orchestrator(bus: RecordingEventBus, recorder: _RecordingSearch) -> AIOrchestrator:
    return AIOrchestrator(
        decision_engine=DecisionEngine(),
        retrieval_engine=RetrievalEngine(recorder, _RecordingSearch()),
        context_builder=ContextBuilder(),
        prompt_orchestrator=PromptOrchestrator(),
        generation_provider=FakeGenerationProvider(),
        event_bus=bus,
    )


def test_request_tenant_becomes_the_retrieval_scope():
    recorder = _RecordingSearch()
    orch = _orchestrator(RecordingEventBus(), recorder)
    orch.run(
        UserRequest(tenant=TenantContext(tenant_id="org_acme"), query=_LOOKUP),
        mission_id="mis_1",
    )
    assert recorder.filters, "retrieval must have run for a lookup query"
    scope = recorder.filters[0].scope
    assert scope is not None
    assert scope.kind is KnowledgeScope.ORGANIZATION
    assert scope.tenant_id == "org_acme"     # the request's tenant, threaded through


def test_every_event_is_stamped_with_tenant_and_mission():
    bus = RecordingEventBus()
    orch = _orchestrator(bus, _RecordingSearch())
    orch.run(
        UserRequest(tenant=TenantContext(tenant_id="org_acme"), query=_LOOKUP),
        mission_id="mis_42",
    )
    assert bus.events, "the run must emit events"
    for event in bus.events:
        assert event.tenant_id == "org_acme"
        assert event.mission_id == "mis_42"
