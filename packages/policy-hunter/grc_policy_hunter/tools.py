"""Policy Hunter's two Tools (CLAUDE.md §9-10): ``list_applicable_obligations.v1`` and
``scan_policy_coverage_gaps.v1``. Both are read-only (``ToolSideEffect.READ_ONLY``, which
structurally sets ``requires_approval=False``) — Policy Hunter never writes, and there is
nothing here that could be "approved" into existing; it only reports.

Each Tool is the anti-corruption boundary (CLAUDE.md §15): it fetches concrete records via the
storage ports in ``ports.py``, translates them into ``models.py``'s plain value objects, and
only then calls the pure ``matching`` engine — the engine itself never sees a database record.
"""

from __future__ import annotations

from grc_domain.platform import Permission, ToolDescriptor, ToolSideEffect
from grc_domain.shared.identifiers import ToolId
from grc_domain.shared.value_objects import SemanticVersion
from grc_tools import Tool, ToolContext, ToolOutcome
from pydantic import BaseModel

from .matching import scan_coverage
from .models import ObligationSummary, PolicySummary
from .ports import ObligationStore, PolicyStore, RawDocumentStore

_CONFIRMED_STATUS = "confirmed"

LIST_APPLICABLE_OBLIGATIONS_TOOL_NAME = "list_applicable_obligations"
LIST_APPLICABLE_OBLIGATIONS_TOOL_VERSION = "1.0.0"
SCAN_POLICY_COVERAGE_GAPS_TOOL_NAME = "scan_policy_coverage_gaps"
SCAN_POLICY_COVERAGE_GAPS_TOOL_VERSION = "1.0.0"


class ObligationEvidence(BaseModel):
    """One confirmed obligation, with the citation evidence CLAUDE.md §19 requires."""

    obligation_id: str
    obligation_text: str
    obligation_type: str
    control_domain: str
    severity: str
    suggested_policy_title: str
    classification_confidence: float
    source_id: str
    source_url: str
    citation: str


class ListApplicableObligationsInput(BaseModel):
    control_domain: str | None = None


class ListApplicableObligationsOutput(BaseModel):
    obligations: list[ObligationEvidence]


class GapFindingEvidence(BaseModel):
    """One coverage gap, with its full evidence: source regulation, citation, confidence,
    and the matched policy (if any)."""

    obligation_id: str
    gap_category: str
    source_id: str
    source_url: str
    citation: str
    confidence: float
    matched_policy_id: str | None
    matched_policy_title: str | None
    rationale: str


class ScanPolicyCoverageGapsInput(BaseModel):
    tenant_id: str
    control_domain: str | None = None


class ScanPolicyCoverageGapsOutput(BaseModel):
    findings: list[GapFindingEvidence]
    obligations_scanned: int
    policies_considered: int


async def _load_obligation_summaries(
    *,
    obligations: ObligationStore,
    raw_documents: RawDocumentStore,
    control_domain: str | None,
) -> list[ObligationSummary]:
    """Fetch every confirmed obligation and join in its source document's provenance — the
    one place this package translates concrete records into ``ObligationSummary``."""
    records = await obligations.list_by_status(_CONFIRMED_STATUS)
    if control_domain is not None:
        records = [record for record in records if record.control_domain == control_domain]

    summaries: list[ObligationSummary] = []
    for record in records:
        raw_document = await raw_documents.get(record.raw_document_id)
        if raw_document is None:  # pragma: no cover - defensive; the FK constraint prevents this
            continue
        summaries.append(
            ObligationSummary(
                obligation_id=record.id,
                obligation_text=record.obligation_text,
                obligation_type=record.obligation_type,
                control_domain=record.control_domain,
                severity=record.severity,
                suggested_policy_title=record.suggested_policy_title,
                classification_confidence=record.confidence,
                source_id=raw_document.source_id,
                source_url=raw_document.url,
                source_document_fetched_at=raw_document.fetched_at,
            )
        )
    return summaries


def _citation(obligation: ObligationSummary) -> str:
    return f"{obligation.source_id}#{obligation.obligation_id}"


class ListApplicableObligationsTool(
    Tool[ListApplicableObligationsInput, ListApplicableObligationsOutput]
):
    """Lists every confirmed regulatory obligation (optionally filtered by control domain),
    with its source citation. Platform-scope, read-only — no tenant data is touched."""

    def __init__(self, *, obligations: ObligationStore, raw_documents: RawDocumentStore) -> None:
        self._obligations = obligations
        self._raw_documents = raw_documents
        self._descriptor = ToolDescriptor.register(
            id=ToolId("list-applicable-obligations"),
            name=LIST_APPLICABLE_OBLIGATIONS_TOOL_NAME,
            version=SemanticVersion.parse(LIST_APPLICABLE_OBLIGATIONS_TOOL_VERSION),
            description=(
                "Lists confirmed regulatory obligations, optionally filtered by control domain."
            ),
            side_effect=ToolSideEffect.READ_ONLY,
            required_permissions=frozenset({Permission("policy_hunter")}),
        )

    @property
    def descriptor(self) -> ToolDescriptor:
        return self._descriptor

    @property
    def input_model(self) -> type[ListApplicableObligationsInput]:
        return ListApplicableObligationsInput

    @property
    def output_model(self) -> type[ListApplicableObligationsOutput]:
        return ListApplicableObligationsOutput

    async def run(
        self, input: ListApplicableObligationsInput, context: ToolContext
    ) -> ToolOutcome[ListApplicableObligationsOutput]:
        summaries = await _load_obligation_summaries(
            obligations=self._obligations,
            raw_documents=self._raw_documents,
            control_domain=input.control_domain,
        )
        evidence = [
            ObligationEvidence(
                obligation_id=o.obligation_id,
                obligation_text=o.obligation_text,
                obligation_type=o.obligation_type,
                control_domain=o.control_domain,
                severity=o.severity,
                suggested_policy_title=o.suggested_policy_title,
                classification_confidence=o.classification_confidence,
                source_id=o.source_id,
                source_url=o.source_url,
                citation=_citation(o),
            )
            for o in summaries
        ]
        return ToolOutcome(
            output=ListApplicableObligationsOutput(obligations=evidence),
            citations=tuple(item.citation for item in evidence),
        )


class ScanPolicyCoverageGapsTool(Tool[ScanPolicyCoverageGapsInput, ScanPolicyCoverageGapsOutput]):
    """Compares confirmed regulatory obligations against one tenant's policies and reports
    coverage gaps. Read-only: it only reports findings, it never drafts or changes a policy."""

    def __init__(
        self,
        *,
        obligations: ObligationStore,
        raw_documents: RawDocumentStore,
        policies: PolicyStore,
    ) -> None:
        self._obligations = obligations
        self._raw_documents = raw_documents
        self._policies = policies
        self._descriptor = ToolDescriptor.register(
            id=ToolId("scan-policy-coverage-gaps"),
            name=SCAN_POLICY_COVERAGE_GAPS_TOOL_NAME,
            version=SemanticVersion.parse(SCAN_POLICY_COVERAGE_GAPS_TOOL_VERSION),
            description=(
                "Compares confirmed regulatory obligations against a tenant's policies and "
                "reports coverage gaps with evidence. Read-only; never creates or edits a policy."
            ),
            side_effect=ToolSideEffect.READ_ONLY,
            required_permissions=frozenset({Permission("policy_hunter")}),
        )

    @property
    def descriptor(self) -> ToolDescriptor:
        return self._descriptor

    @property
    def input_model(self) -> type[ScanPolicyCoverageGapsInput]:
        return ScanPolicyCoverageGapsInput

    @property
    def output_model(self) -> type[ScanPolicyCoverageGapsOutput]:
        return ScanPolicyCoverageGapsOutput

    async def run(
        self, input: ScanPolicyCoverageGapsInput, context: ToolContext
    ) -> ToolOutcome[ScanPolicyCoverageGapsOutput]:
        obligation_summaries = await _load_obligation_summaries(
            obligations=self._obligations,
            raw_documents=self._raw_documents,
            control_domain=input.control_domain,
        )
        policy_records = await self._policies.list(input.tenant_id)
        policy_summaries = [
            PolicySummary(
                policy_id=record.id,
                title=record.title,
                summary=record.summary,
                status=record.status,
                updated_at=record.updated_at,
            )
            for record in policy_records
        ]

        result = scan_coverage(obligation_summaries, policy_summaries)
        findings = [
            GapFindingEvidence(
                obligation_id=f.obligation_id,
                gap_category=f.gap_category.value,
                source_id=f.source_id,
                source_url=f.source_url,
                citation=f.citation,
                confidence=f.confidence,
                matched_policy_id=f.matched_policy_id,
                matched_policy_title=f.matched_policy_title,
                rationale=f.rationale,
            )
            for f in result.findings
        ]
        return ToolOutcome(
            output=ScanPolicyCoverageGapsOutput(
                findings=findings,
                obligations_scanned=result.obligations_scanned,
                policies_considered=result.policies_considered,
            ),
            citations=tuple(finding.citation for finding in findings),
        )
