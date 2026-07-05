"""Integration tests for Policy Builder's one Tool through the real Tool Registry: audit
logging, read-only enforcement, the confirmed-obligation gate, and the PolicyBuilderAgent
wiring — against in-memory fake stores, no real database."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from grc_policy_builder import (
    DRAFT_POLICY_FROM_OBLIGATION_TOOL_NAME,
    DRAFT_POLICY_FROM_OBLIGATION_TOOL_VERSION,
    DraftPolicyFromObligationOutput,
    DraftPolicyFromObligationTool,
    ObligationNotFoundError,
    PolicyBuilderAgent,
)
from grc_tools import (
    ToolCaller,
    ToolContext,
    ToolInvocationRecord,
    ToolInvocationRecorder,
    ToolPermissionDeniedError,
    ToolRegistry,
)


@dataclass(frozen=True)
class _FakeObligationRecord:
    id: str
    raw_document_id: str
    obligation_text: str
    control_domain: str
    suggested_policy_title: str
    classification_status: str


@dataclass(frozen=True)
class _FakeRawDocumentRecord:
    source_id: str
    url: str
    fetched_at: datetime


class FakeObligationStore:
    def __init__(self, records: list[_FakeObligationRecord]) -> None:
        self._records = {r.id: r for r in records}

    async def get(self, obligation_id: str) -> _FakeObligationRecord | None:
        return self._records.get(obligation_id)


class FakeRawDocumentStore:
    def __init__(self, records: dict[str, _FakeRawDocumentRecord]) -> None:
        self._records = records

    async def get(self, document_id: str) -> _FakeRawDocumentRecord | None:
        return self._records.get(document_id)


class RecordingRecorder(ToolInvocationRecorder):
    def __init__(self) -> None:
        self.entries: list[ToolInvocationRecord] = []

    async def record(self, entry: ToolInvocationRecord) -> None:
        self.entries.append(entry)


def _context(*, roles: frozenset[str] = frozenset({"policy_builder"})) -> ToolContext:
    return ToolContext(
        caller=ToolCaller.TEST,
        tenant_id=None,
        user_id="dev-user",
        roles=roles,
        agent="policy_builder_agent",
    )


def _fixture() -> tuple[FakeObligationStore, FakeRawDocumentStore]:
    fetched_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    obligations = FakeObligationStore(
        [
            _FakeObligationRecord(
                id="ob-1",
                raw_document_id="doc-1",
                obligation_text="Entities shall encrypt data at rest.",
                control_domain="data_protection",
                suggested_policy_title="Encryption Policy",
                classification_status="confirmed",
            ),
            _FakeObligationRecord(
                id="ob-2",
                raw_document_id="doc-1",
                obligation_text="Entities shall log every access attempt.",
                control_domain="incident_management",
                suggested_policy_title="Logging Policy",
                classification_status="pending_review",
            ),
        ]
    )
    raw_documents = FakeRawDocumentStore(
        {
            "doc-1": _FakeRawDocumentRecord(
                source_id="sa-sama",
                url="https://www.sama.gov.sa/circulars/1",
                fetched_at=fetched_at,
            ),
        }
    )
    return obligations, raw_documents


async def test_draft_policy_from_obligation_succeeds_and_is_audited() -> None:
    obligations, raw_documents = _fixture()
    recorder = RecordingRecorder()
    registry = ToolRegistry(recorder=recorder)
    registry.register(
        DraftPolicyFromObligationTool(obligations=obligations, raw_documents=raw_documents)
    )

    output = await registry.invoke(
        DRAFT_POLICY_FROM_OBLIGATION_TOOL_NAME,
        DRAFT_POLICY_FROM_OBLIGATION_TOOL_VERSION,
        {"obligation_id": "ob-1"},
        _context(),
    )

    assert isinstance(output, DraftPolicyFromObligationOutput)
    assert output.draft.title == "Encryption Policy"
    assert output.draft.citation == "sa-sama#ob-1"
    assert "Entities shall encrypt data at rest." in output.draft.body
    assert output.draft.sections_requiring_human_input == [
        "scope",
        "ownership",
        "responsibilities",
        "controls",
        "review cycle",
        "exceptions",
    ]
    assert len(recorder.entries) == 1
    assert recorder.entries[0].status.value == "succeeded"
    assert recorder.entries[0].requires_human_approval is False  # read-only, never gated
    assert recorder.entries[0].citations == ("sa-sama#ob-1",)


async def test_draft_policy_from_obligation_raises_for_unconfirmed_obligation() -> None:
    obligations, raw_documents = _fixture()
    recorder = RecordingRecorder()
    registry = ToolRegistry(recorder=recorder)
    registry.register(
        DraftPolicyFromObligationTool(obligations=obligations, raw_documents=raw_documents)
    )

    with pytest.raises(ObligationNotFoundError):
        await registry.invoke(
            DRAFT_POLICY_FROM_OBLIGATION_TOOL_NAME,
            DRAFT_POLICY_FROM_OBLIGATION_TOOL_VERSION,
            {"obligation_id": "ob-2"},  # pending_review, not confirmed
            _context(),
        )

    assert recorder.entries[0].status.value == "failed"


async def test_draft_policy_from_obligation_raises_for_unknown_obligation_id() -> None:
    obligations, raw_documents = _fixture()
    registry = ToolRegistry(recorder=RecordingRecorder())
    registry.register(
        DraftPolicyFromObligationTool(obligations=obligations, raw_documents=raw_documents)
    )

    with pytest.raises(ObligationNotFoundError):
        await registry.invoke(
            DRAFT_POLICY_FROM_OBLIGATION_TOOL_NAME,
            DRAFT_POLICY_FROM_OBLIGATION_TOOL_VERSION,
            {"obligation_id": "does-not-exist"},
            _context(),
        )


async def test_missing_permission_is_denied_and_audited() -> None:
    obligations, raw_documents = _fixture()
    recorder = RecordingRecorder()
    registry = ToolRegistry(recorder=recorder)
    registry.register(
        DraftPolicyFromObligationTool(obligations=obligations, raw_documents=raw_documents)
    )
    no_permission_context = _context(roles=frozenset())

    with pytest.raises(ToolPermissionDeniedError):
        await registry.invoke(
            DRAFT_POLICY_FROM_OBLIGATION_TOOL_NAME,
            DRAFT_POLICY_FROM_OBLIGATION_TOOL_VERSION,
            {"obligation_id": "ob-1"},
            no_permission_context,
        )

    assert recorder.entries[0].status.value == "denied"


async def test_policy_builder_agent_drafts_via_the_registry() -> None:
    obligations, raw_documents = _fixture()
    registry = ToolRegistry(recorder=RecordingRecorder())
    registry.register(
        DraftPolicyFromObligationTool(obligations=obligations, raw_documents=raw_documents)
    )
    agent = PolicyBuilderAgent(registry)

    output = await agent.draft_policy_from_obligation(obligation_id="ob-1", context=_context())

    assert output.draft.obligation_id == "ob-1"
    assert output.draft.title == "Encryption Policy"
