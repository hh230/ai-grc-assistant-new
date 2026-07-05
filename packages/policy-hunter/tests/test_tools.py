"""Integration tests for the two Policy Hunter Tools through the real Tool Registry: audit
logging, read-only enforcement, and the PolicyHunterAgent wiring — against in-memory fake
stores, no real database."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from grc_policy_hunter import (
    ListApplicableObligationsTool,
    PolicyHunterAgent,
    ScanPolicyCoverageGapsTool,
)
from grc_tools import (
    ToolCaller,
    ToolContext,
    ToolInvocationRecord,
    ToolInvocationRecorder,
    ToolRegistry,
)


@dataclass(frozen=True)
class _FakeObligationRecord:
    id: str
    raw_document_id: str
    obligation_text: str
    obligation_type: str
    control_domain: str
    suggested_policy_title: str
    severity: str
    confidence: float
    classification_status: str


@dataclass(frozen=True)
class _FakeRawDocumentRecord:
    source_id: str
    url: str
    fetched_at: datetime


@dataclass(frozen=True)
class _FakePolicyRecord:
    id: str
    title: str
    summary: str | None
    status: str
    updated_at: datetime


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


class FakePolicyStore:
    def __init__(self, policies: dict[str, list[_FakePolicyRecord]]) -> None:
        self._policies = policies

    async def list(self, tenant_id: str) -> list[_FakePolicyRecord]:
        return self._policies.get(tenant_id, [])


class RecordingRecorder(ToolInvocationRecorder):
    def __init__(self) -> None:
        self.entries: list[ToolInvocationRecord] = []

    async def record(self, entry: ToolInvocationRecord) -> None:
        self.entries.append(entry)


def _context(tenant_id: str | None = "tenant-1") -> ToolContext:
    return ToolContext(
        caller=ToolCaller.TEST,
        tenant_id=tenant_id,
        user_id="dev-user",
        roles=frozenset({"policy_hunter"}),
        agent="policy_hunter_agent",
    )


def _fixture() -> tuple[FakeObligationStore, FakeRawDocumentStore, FakePolicyStore]:
    fetched_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    obligations = FakeObligationStore(
        [
            _FakeObligationRecord(
                id="ob-1",
                raw_document_id="doc-1",
                obligation_text=(
                    "Entities shall implement multi-factor authentication for privileged accounts."
                ),
                obligation_type="requirement",
                control_domain="access_control",
                suggested_policy_title="Access Control Policy",
                severity="high",
                confidence=0.9,
                classification_status="confirmed",
            ),
            _FakeObligationRecord(
                id="ob-2",
                raw_document_id="doc-1",
                obligation_text="Entities shall encrypt data at rest.",
                obligation_type="requirement",
                control_domain="data_protection",
                suggested_policy_title="Data Encryption Policy",
                severity="high",
                confidence=0.4,
                classification_status="pending_review",
            ),
        ]
    )
    raw_documents = FakeRawDocumentStore(
        {
            "doc-1": _FakeRawDocumentRecord(
                source_id="sa-sama", url="https://www.sama.gov.sa/c/1", fetched_at=fetched_at
            )
        }
    )
    policies = FakePolicyStore(
        {
            "tenant-1": [
                _FakePolicyRecord(
                    id="pol-1",
                    title="Access Control Policy",
                    summary=(
                        "Defines access control requirements including MFA for privileged "
                        "accounts."
                    ),
                    status="published",
                    updated_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
                )
            ]
        }
    )
    return obligations, raw_documents, policies


async def test_list_applicable_obligations_only_returns_confirmed_and_is_audited() -> None:
    obligations, raw_documents, policies = _fixture()
    recorder = RecordingRecorder()
    registry = ToolRegistry(recorder=recorder)
    registry.register(
        ListApplicableObligationsTool(obligations=obligations, raw_documents=raw_documents)
    )

    output = await registry.invoke(
        "list_applicable_obligations", "1.0.0", {"control_domain": None}, _context()
    )

    assert [o.obligation_id for o in output.obligations] == ["ob-1"]  # ob-2 is pending_review
    assert output.obligations[0].citation == "sa-sama#ob-1"
    assert len(recorder.entries) == 1
    assert recorder.entries[0].status.value == "succeeded"
    assert recorder.entries[0].requires_human_approval is False  # read-only, never gated


async def test_list_applicable_obligations_filters_by_control_domain() -> None:
    obligations, raw_documents, policies = _fixture()
    registry = ToolRegistry(recorder=RecordingRecorder())
    registry.register(
        ListApplicableObligationsTool(obligations=obligations, raw_documents=raw_documents)
    )

    output = await registry.invoke(
        "list_applicable_obligations", "1.0.0", {"control_domain": "data_protection"}, _context()
    )

    assert output.obligations == []  # ob-2 matches the domain but isn't confirmed


async def test_scan_policy_coverage_gaps_reports_only_gaps_and_is_audited() -> None:
    obligations, raw_documents, policies = _fixture()
    recorder = RecordingRecorder()
    registry = ToolRegistry(recorder=recorder)
    registry.register(
        ScanPolicyCoverageGapsTool(
            obligations=obligations, raw_documents=raw_documents, policies=policies
        )
    )

    output = await registry.invoke(
        "scan_policy_coverage_gaps",
        "1.0.0",
        {"tenant_id": "tenant-1", "control_domain": None},
        _context(),
    )

    assert output.obligations_scanned == 1  # only the confirmed one
    assert output.findings == []  # the one confirmed obligation is covered by pol-1
    assert len(recorder.entries) == 1
    assert recorder.entries[0].tenant_id == "tenant-1"


async def test_scan_policy_coverage_gaps_for_a_tenant_with_no_policies_reports_a_gap() -> None:
    obligations, raw_documents, policies = _fixture()
    registry = ToolRegistry(recorder=RecordingRecorder())
    registry.register(
        ScanPolicyCoverageGapsTool(
            obligations=obligations, raw_documents=raw_documents, policies=policies
        )
    )

    output = await registry.invoke(
        "scan_policy_coverage_gaps",
        "1.0.0",
        {"tenant_id": "tenant-with-no-policies", "control_domain": None},
        _context(tenant_id="tenant-with-no-policies"),
    )

    assert output.policies_considered == 0
    assert len(output.findings) == 1
    assert output.findings[0].gap_category == "unmapped_regulatory_obligation"
    assert output.findings[0].source_id == "sa-sama"
    assert output.findings[0].citation == "sa-sama#ob-1"


async def test_policy_hunter_agent_scans_via_the_registry() -> None:
    obligations, raw_documents, policies = _fixture()
    recorder = RecordingRecorder()
    registry = ToolRegistry(recorder=recorder)
    registry.register(
        ScanPolicyCoverageGapsTool(
            obligations=obligations, raw_documents=raw_documents, policies=policies
        )
    )
    registry.register(
        ListApplicableObligationsTool(obligations=obligations, raw_documents=raw_documents)
    )
    agent = PolicyHunterAgent(registry)

    listed = await agent.list_applicable_obligations(control_domain=None, context=_context())
    scanned = await agent.scan_policy_coverage_gaps(
        tenant_id="tenant-1", control_domain=None, context=_context()
    )

    assert len(listed.obligations) == 1
    assert scanned.findings == []
    assert len(recorder.entries) == 2  # both Tool calls audited


def test_both_tools_are_read_only_and_never_require_approval() -> None:
    obligations, raw_documents, policies = _fixture()
    list_tool = ListApplicableObligationsTool(obligations=obligations, raw_documents=raw_documents)
    scan_tool = ScanPolicyCoverageGapsTool(
        obligations=obligations, raw_documents=raw_documents, policies=policies
    )

    assert list_tool.descriptor.side_effect.value == "read_only"
    assert list_tool.descriptor.requires_approval is False
    assert scan_tool.descriptor.side_effect.value == "read_only"
    assert scan_tool.descriptor.requires_approval is False
