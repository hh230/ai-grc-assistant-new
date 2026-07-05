"""Integration tests for ReviewPolicyQualityTool through the real Tool Registry: audit
logging, read-only enforcement, unknown-policy handling, and the PolicyAnalystAgent wiring —
against in-memory fake stores, no real database."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from grc_policy_analyst import (
    PolicyAnalystAgent,
    ReviewPolicyQualityOutput,
    ReviewPolicyQualityTool,
)
from grc_policy_analyst.exceptions import PolicyNotFoundError
from grc_tools import (
    ToolCaller,
    ToolContext,
    ToolInvocationRecord,
    ToolInvocationRecorder,
    ToolPermissionDeniedError,
    ToolRegistry,
)


@dataclass(frozen=True)
class _FakePolicyRecord:
    id: str
    title: str
    summary: str | None
    body: str | None
    status: str
    owner_name: str
    updated_at: datetime


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


class FakePolicyStore:
    def __init__(self, policies: dict[tuple[str, str], _FakePolicyRecord]) -> None:
        self._policies = policies

    async def get(self, tenant_id: str, policy_id: str) -> _FakePolicyRecord | None:
        return self._policies.get((tenant_id, policy_id))


class FakeObligationStore:
    def __init__(self, records: list[_FakeObligationRecord]) -> None:
        self._records = records

    async def list_by_status(self, classification_status: str) -> list[_FakeObligationRecord]:
        return [r for r in self._records if r.classification_status == classification_status]


class FakeRawDocumentStore:
    def __init__(self, documents: dict[str, _FakeRawDocumentRecord]) -> None:
        self._documents = documents

    async def get(self, document_id: str) -> _FakeRawDocumentRecord | None:
        return self._documents.get(document_id)


class RecordingRecorder(ToolInvocationRecorder):
    def __init__(self) -> None:
        self.entries: list[ToolInvocationRecord] = []

    async def record(self, entry: ToolInvocationRecord) -> None:
        self.entries.append(entry)


def _context() -> ToolContext:
    return ToolContext(
        caller=ToolCaller.TEST,
        tenant_id="tenant-1",
        user_id="dev-user",
        roles=frozenset({"policy_analyst"}),
        agent="policy_analyst_agent",
    )


_COMPLETE_BODY = """
Purpose: This policy establishes requirements for access control.
Scope: Applies to all employees and systems.
Ownership: The CISO owns this policy.
Responsibilities: Managers approve access. IT provisions accounts.
Controls: Multi-factor authentication is required for all privileged accounts.
Review cycle: This policy is reviewed annually by the security team.
Exceptions: Exceptions must be approved in writing by the CISO.
""".strip()


def _fixture() -> tuple[FakePolicyStore, FakeObligationStore, FakeRawDocumentStore]:
    policies = FakePolicyStore(
        {
            ("tenant-1", "pol-1"): _FakePolicyRecord(
                id="pol-1",
                title="Access Control Policy",
                summary="Defines access control requirements.",
                body=_COMPLETE_BODY,
                status="published",
                owner_name="CISO",
                updated_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
            )
        }
    )
    obligations = FakeObligationStore(
        [
            _FakeObligationRecord(
                id="ob-1",
                raw_document_id="doc-1",
                obligation_text=(
                    "Entities shall implement multi-factor authentication for privileged accounts."
                ),
                control_domain="access_control",
                suggested_policy_title="Access Control Policy",
                classification_status="confirmed",
            ),
            _FakeObligationRecord(
                id="ob-2",
                raw_document_id="doc-1",
                obligation_text="Entities shall encrypt data at rest.",
                control_domain="data_protection",
                suggested_policy_title="Data Encryption Policy",
                classification_status="pending_review",
            ),
        ]
    )
    raw_documents = FakeRawDocumentStore(
        {
            "doc-1": _FakeRawDocumentRecord(
                source_id="sa-sama",
                url="https://www.sama.gov.sa/c/1",
                fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        }
    )
    return policies, obligations, raw_documents


def _fixed_clock() -> datetime:
    return datetime(2026, 7, 1, tzinfo=timezone.utc)


async def test_review_policy_quality_reports_no_findings_for_a_complete_covered_policy() -> None:
    policies, obligations, raw_documents = _fixture()
    recorder = RecordingRecorder()
    registry = ToolRegistry(recorder=recorder)
    registry.register(
        ReviewPolicyQualityTool(
            policies=policies,
            obligations=obligations,
            raw_documents=raw_documents,
            clock=_fixed_clock,
        )
    )

    output = await registry.invoke(
        "review_policy_quality",
        "1.0.0",
        {"tenant_id": "tenant-1", "policy_id": "pol-1"},
        _context(),
    )

    assert isinstance(output, ReviewPolicyQualityOutput)
    assert output.policy_id == "pol-1"
    assert output.findings == []
    assert output.obligations_considered == 1  # only the confirmed obligation
    assert len(recorder.entries) == 1
    assert recorder.entries[0].status.value == "succeeded"
    assert recorder.entries[0].requires_human_approval is False  # read-only, never gated


async def test_review_policy_quality_only_considers_confirmed_obligations() -> None:
    policies, obligations, raw_documents = _fixture()
    registry = ToolRegistry(recorder=RecordingRecorder())
    registry.register(
        ReviewPolicyQualityTool(
            policies=policies,
            obligations=obligations,
            raw_documents=raw_documents,
            clock=_fixed_clock,
        )
    )

    output = await registry.invoke(
        "review_policy_quality",
        "1.0.0",
        {"tenant_id": "tenant-1", "policy_id": "pol-1"},
        _context(),
    )

    assert isinstance(output, ReviewPolicyQualityOutput)
    assert output.obligations_considered == 1  # ob-2 is pending_review and excluded


async def test_review_policy_quality_raises_for_unknown_policy_and_is_audited_as_failed() -> None:
    policies, obligations, raw_documents = _fixture()
    recorder = RecordingRecorder()
    registry = ToolRegistry(recorder=recorder)
    registry.register(
        ReviewPolicyQualityTool(
            policies=policies,
            obligations=obligations,
            raw_documents=raw_documents,
            clock=_fixed_clock,
        )
    )

    with pytest.raises(PolicyNotFoundError):
        await registry.invoke(
            "review_policy_quality",
            "1.0.0",
            {"tenant_id": "tenant-1", "policy_id": "does-not-exist"},
            _context(),
        )

    assert recorder.entries[0].status.value == "failed"


async def test_missing_permission_is_denied_and_audited() -> None:
    policies, obligations, raw_documents = _fixture()
    recorder = RecordingRecorder()
    registry = ToolRegistry(recorder=recorder)
    registry.register(
        ReviewPolicyQualityTool(
            policies=policies,
            obligations=obligations,
            raw_documents=raw_documents,
            clock=_fixed_clock,
        )
    )
    no_permission_context = ToolContext(
        caller=ToolCaller.TEST, tenant_id="tenant-1", user_id="dev-user", roles=frozenset()
    )

    with pytest.raises(ToolPermissionDeniedError):
        await registry.invoke(
            "review_policy_quality",
            "1.0.0",
            {"tenant_id": "tenant-1", "policy_id": "pol-1"},
            no_permission_context,
        )

    assert recorder.entries[0].status.value == "denied"


async def test_policy_analyst_agent_reviews_via_the_registry() -> None:
    policies, obligations, raw_documents = _fixture()
    recorder = RecordingRecorder()
    registry = ToolRegistry(recorder=recorder)
    registry.register(
        ReviewPolicyQualityTool(
            policies=policies,
            obligations=obligations,
            raw_documents=raw_documents,
            clock=_fixed_clock,
        )
    )
    agent = PolicyAnalystAgent(registry)

    output = await agent.review_policy_quality(
        tenant_id="tenant-1", policy_id="pol-1", context=_context()
    )

    assert output.policy_id == "pol-1"
    assert len(recorder.entries) == 1


def test_tool_is_read_only_and_never_requires_approval() -> None:
    policies, obligations, raw_documents = _fixture()
    tool = ReviewPolicyQualityTool(
        policies=policies, obligations=obligations, raw_documents=raw_documents
    )
    assert tool.descriptor.side_effect.value == "read_only"
    assert tool.descriptor.requires_approval is False
