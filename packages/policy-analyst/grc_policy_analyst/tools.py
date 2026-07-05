"""Policy Analyst's Tool (CLAUDE.md §9-10): ``review_policy_quality.v1``. Read-only
(``ToolSideEffect.READ_ONLY``, which structurally sets ``requires_approval=False``) — Policy
Analyst never edits, creates, or approves a policy; it only reports.

The Tool is the anti-corruption boundary (CLAUDE.md §15): it fetches concrete records via the
storage ports in ``ports.py``, translates them into ``models.py``'s plain value objects, and
only then calls the pure ``quality_engine.review_policy`` — the engine itself never sees a
database record.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from grc_domain.platform import Permission, ToolDescriptor, ToolSideEffect
from grc_domain.shared.identifiers import ToolId
from grc_domain.shared.value_objects import SemanticVersion
from grc_tools import Tool, ToolContext, ToolOutcome
from pydantic import BaseModel

from .exceptions import PolicyNotFoundError
from .models import PolicyDocument, RelatedObligation
from .ports import ObligationStore, PolicyStore, RawDocumentStore
from .quality_engine import review_policy

_CONFIRMED_STATUS = "confirmed"

REVIEW_POLICY_QUALITY_TOOL_NAME = "review_policy_quality"
REVIEW_POLICY_QUALITY_TOOL_VERSION = "1.0.0"


class ReviewPolicyQualityInput(BaseModel):
    tenant_id: str
    policy_id: str


class QualityFindingEvidence(BaseModel):
    """One finding, with the evidence CLAUDE.md §19 requires."""

    finding_type: str
    severity: str
    evidence: str
    citation: str
    recommendation: str
    confidence: float
    related_obligation_id: str | None


class ReviewPolicyQualityOutput(BaseModel):
    policy_id: str
    findings: list[QualityFindingEvidence]
    obligations_considered: int


async def _load_related_obligations(
    *, obligations: ObligationStore, raw_documents: RawDocumentStore
) -> list[RelatedObligation]:
    """Every confirmed obligation, joined with its source document's provenance. Relevance to
    the specific policy under review is decided by the pure engine, not here."""
    records = await obligations.list_by_status(_CONFIRMED_STATUS)
    related: list[RelatedObligation] = []
    for record in records:
        raw_document = await raw_documents.get(record.raw_document_id)
        if raw_document is None:  # pragma: no cover - defensive; the FK constraint prevents this
            continue
        related.append(
            RelatedObligation(
                obligation_id=record.id,
                obligation_text=record.obligation_text,
                suggested_policy_title=record.suggested_policy_title,
                control_domain=record.control_domain,
                source_id=raw_document.source_id,
                source_url=raw_document.url,
                source_document_fetched_at=raw_document.fetched_at,
            )
        )
    return related


class ReviewPolicyQualityTool(Tool[ReviewPolicyQualityInput, ReviewPolicyQualityOutput]):
    """Analyzes one tenant policy's completeness, regulatory alignment, internal
    consistency, and freshness, and reports findings with evidence. Read-only: it never
    drafts, edits, or approves a policy — there is no write path in this Tool at all.
    """

    def __init__(
        self,
        *,
        policies: PolicyStore,
        obligations: ObligationStore,
        raw_documents: RawDocumentStore,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._policies = policies
        self._obligations = obligations
        self._raw_documents = raw_documents
        self._clock = clock
        self._descriptor = ToolDescriptor.register(
            id=ToolId("review-policy-quality"),
            name=REVIEW_POLICY_QUALITY_TOOL_NAME,
            version=SemanticVersion.parse(REVIEW_POLICY_QUALITY_TOOL_VERSION),
            description=(
                "Analyzes one policy's completeness, regulatory alignment, internal "
                "consistency, and freshness, and reports findings with evidence."
            ),
            side_effect=ToolSideEffect.READ_ONLY,
            required_permissions=frozenset({Permission("policy_analyst")}),
        )

    @property
    def descriptor(self) -> ToolDescriptor:
        return self._descriptor

    @property
    def input_model(self) -> type[ReviewPolicyQualityInput]:
        return ReviewPolicyQualityInput

    @property
    def output_model(self) -> type[ReviewPolicyQualityOutput]:
        return ReviewPolicyQualityOutput

    async def run(
        self, input: ReviewPolicyQualityInput, context: ToolContext
    ) -> ToolOutcome[ReviewPolicyQualityOutput]:
        record = await self._policies.get(input.tenant_id, input.policy_id)
        if record is None:
            raise PolicyNotFoundError(
                f"no policy {input.policy_id!r} for tenant {input.tenant_id!r}"
            )

        policy = PolicyDocument(
            policy_id=record.id,
            title=record.title,
            summary=record.summary,
            body=record.body,
            status=record.status,
            owner_name=record.owner_name,
            updated_at=record.updated_at,
        )
        related_obligations = await _load_related_obligations(
            obligations=self._obligations, raw_documents=self._raw_documents
        )

        report = review_policy(policy, related_obligations, now=self._clock())

        findings = [
            QualityFindingEvidence(
                finding_type=f.finding_type.value,
                severity=f.severity.value,
                evidence=f.evidence,
                citation=f.citation,
                recommendation=f.recommendation,
                confidence=f.confidence,
                related_obligation_id=f.related_obligation_id,
            )
            for f in report.findings
        ]
        return ToolOutcome(
            output=ReviewPolicyQualityOutput(
                policy_id=report.policy_id,
                findings=findings,
                obligations_considered=report.obligations_considered,
            ),
            citations=tuple(finding.citation for finding in findings),
        )
