"""Shared codecs: Domain value objects ↔ JSON-safe primitives.

Every nested value object that is persisted inside a JSON(B) column is encoded/decoded
here, so the per-aggregate mappers stay focused on assembling rows. Sets are encoded as
**sorted** lists for deterministic, diff-friendly storage.
"""

from __future__ import annotations

from datetime import datetime, timezone

from grc_domain.assessments.enums import CoverageLevel
from grc_domain.assessments.value_objects import ControlAssessmentResult, CoverageSummary
from grc_domain.audit.value_objects import AiCallTrace
from grc_domain.frameworks.enums import MappingRelation
from grc_domain.frameworks.value_objects import (
    ControlCorrespondence,
    EvidenceExpectation,
    FrameworkControl,
    FrameworkControlRef,
    Requirement,
)
from grc_domain.missions.value_objects import ProposedAction
from grc_domain.platform.value_objects import Permission, SchemaRef, VersionRange
from grc_domain.reporting.value_objects import ReportSection
from grc_domain.risks.enums import RiskImpact, RiskLevel, RiskLikelihood
from grc_domain.risks.value_objects import RiskScore
from grc_domain.shared.identifiers import (
    ControlId,
    FrameworkControlId,
    FrameworkId,
    KnowledgeSourceId,
)
from grc_domain.shared.value_objects import (
    Actor,
    ActorKind,
    Citation,
    Confidence,
    SemanticVersion,
    TraceContext,
)

# --- primitives ---------------------------------------------------------------------


def aware(value: datetime) -> datetime:
    """Coerce a datetime to timezone-aware UTC (SQLite hands back naive datetimes)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def encode_id_set(values: set) -> list[str]:
    """Encode a set of typed ids as a sorted list of strings (deterministic)."""
    return sorted(str(value) for value in values)


# --- Citation -----------------------------------------------------------------------


def encode_citation(citation: Citation) -> dict:
    return {
        "source_id": str(citation.source_id),
        "locator": citation.locator,
        "snippet": citation.snippet,
    }


def decode_citation(data: dict) -> Citation:
    return Citation(
        source_id=KnowledgeSourceId(data["source_id"]),
        locator=data["locator"],
        snippet=data.get("snippet"),
    )


def encode_citations(citations: tuple[Citation, ...]) -> list[dict]:
    return [encode_citation(citation) for citation in citations]


def decode_citations(data: list[dict]) -> tuple[Citation, ...]:
    return tuple(decode_citation(item) for item in data)


# --- SemanticVersion / SchemaRef / VersionRange / Permission ------------------------


def encode_schema_ref(ref: SchemaRef | None) -> dict | None:
    if ref is None:
        return None
    return {"name": ref.name, "version": str(ref.version)}


def decode_schema_ref(data: dict | None) -> SchemaRef | None:
    if data is None:
        return None
    return SchemaRef(name=data["name"], version=SemanticVersion.parse(data["version"]))


def encode_version_range(value: VersionRange | None) -> dict | None:
    if value is None:
        return None
    return {
        "minimum": str(value.minimum),
        "maximum": str(value.maximum) if value.maximum is not None else None,
    }


def decode_version_range(data: dict | None) -> VersionRange | None:
    if data is None:
        return None
    maximum = data.get("maximum")
    return VersionRange(
        minimum=SemanticVersion.parse(data["minimum"]),
        maximum=SemanticVersion.parse(maximum) if maximum is not None else None,
    )


def encode_permissions(permissions: frozenset[Permission]) -> list[str]:
    return sorted(permission.name for permission in permissions)


def decode_permissions(data: list[str]) -> frozenset[Permission]:
    return frozenset(Permission(name) for name in data)


# --- FrameworkControlRef ------------------------------------------------------------


def encode_framework_control_ref(ref: FrameworkControlRef) -> dict:
    return {
        "framework_id": str(ref.framework_id),
        "framework_control_id": str(ref.framework_control_id),
    }


def decode_framework_control_ref(data: dict) -> FrameworkControlRef:
    return FrameworkControlRef(
        framework_id=FrameworkId(data["framework_id"]),
        framework_control_id=FrameworkControlId(data["framework_control_id"]),
    )


def encode_framework_control_refs(refs: set[FrameworkControlRef]) -> list[dict]:
    return sorted(
        (encode_framework_control_ref(ref) for ref in refs),
        key=lambda item: (item["framework_id"], item["framework_control_id"]),
    )


def decode_framework_control_refs(data: list[dict]) -> set[FrameworkControlRef]:
    return {decode_framework_control_ref(item) for item in data}


# --- FrameworkControl (definition data) ---------------------------------------------


def encode_framework_control(control: FrameworkControl) -> dict:
    return {
        "id": str(control.id),
        "code": control.code,
        "title": control.title,
        "domain": control.domain,
        "requirements": [{"code": req.code, "text": req.text} for req in control.requirements],
        "evidence_expectations": [
            {"description": exp.description} for exp in control.evidence_expectations
        ],
    }


def decode_framework_control(data: dict) -> FrameworkControl:
    return FrameworkControl(
        id=FrameworkControlId(data["id"]),
        code=data["code"],
        title=data["title"],
        domain=data["domain"],
        requirements=tuple(
            Requirement(code=req["code"], text=req["text"]) for req in data["requirements"]
        ),
        evidence_expectations=tuple(
            EvidenceExpectation(description=exp["description"])
            for exp in data["evidence_expectations"]
        ),
    )


# --- ControlCorrespondence ----------------------------------------------------------


def encode_correspondence(correspondence: ControlCorrespondence) -> dict:
    return {
        "source": encode_framework_control_ref(correspondence.source),
        "target": encode_framework_control_ref(correspondence.target),
        "relation": correspondence.relation.value,
    }


def decode_correspondence(data: dict) -> ControlCorrespondence:
    return ControlCorrespondence(
        source=decode_framework_control_ref(data["source"]),
        target=decode_framework_control_ref(data["target"]),
        relation=MappingRelation(data["relation"]),
    )


# --- RiskScore ----------------------------------------------------------------------


def encode_risk_score(score: RiskScore | None) -> dict | None:
    if score is None:
        return None
    return {
        "value": score.value,
        "level": score.level.value,
        "likelihood": score.likelihood.value,
        "impact": score.impact.value,
    }


def decode_risk_score(data: dict | None) -> RiskScore | None:
    if data is None:
        return None
    return RiskScore(
        value=data["value"],
        level=RiskLevel(data["level"]),
        likelihood=RiskLikelihood(data["likelihood"]),
        impact=RiskImpact(data["impact"]),
    )


# --- Assessment value objects -------------------------------------------------------


def encode_assessment_result(result: ControlAssessmentResult) -> dict:
    return {
        "framework_control_id": str(result.framework_control_id),
        "coverage": result.coverage.value,
        "satisfied_by_control_id": (
            str(result.satisfied_by_control_id)
            if result.satisfied_by_control_id is not None
            else None
        ),
        "confidence": result.confidence.score if result.confidence is not None else None,
        "citations": encode_citations(result.citations),
        "notes": result.notes,
    }


def decode_assessment_result(data: dict) -> ControlAssessmentResult:
    satisfied = data.get("satisfied_by_control_id")
    confidence = data.get("confidence")
    return ControlAssessmentResult(
        framework_control_id=FrameworkControlId(data["framework_control_id"]),
        coverage=CoverageLevel(data["coverage"]),
        satisfied_by_control_id=ControlId(satisfied) if satisfied is not None else None,
        confidence=Confidence(score=confidence) if confidence is not None else None,
        citations=decode_citations(data.get("citations", [])),
        notes=data.get("notes"),
    )


def encode_coverage_summary(summary: CoverageSummary | None) -> dict | None:
    if summary is None:
        return None
    return {
        "total": summary.total,
        "covered": summary.covered,
        "partially_covered": summary.partially_covered,
        "not_covered": summary.not_covered,
        "not_applicable": summary.not_applicable,
    }


def decode_coverage_summary(data: dict | None) -> CoverageSummary | None:
    if data is None:
        return None
    return CoverageSummary(
        total=data["total"],
        covered=data["covered"],
        partially_covered=data["partially_covered"],
        not_covered=data["not_covered"],
        not_applicable=data["not_applicable"],
    )


# --- ReportSection ------------------------------------------------------------------


def encode_report_section(section: ReportSection) -> dict:
    return {
        "heading": section.heading,
        "body": section.body,
        "citations": encode_citations(section.citations),
    }


def decode_report_section(data: dict) -> ReportSection:
    return ReportSection(
        heading=data["heading"],
        body=data["body"],
        citations=decode_citations(data.get("citations", [])),
    )


# --- ProposedAction (mission gate) --------------------------------------------------


def encode_proposed_action(action: ProposedAction) -> dict:
    return {
        "description": action.description,
        "citations": encode_citations(action.citations),
    }


def decode_proposed_action(data: dict) -> ProposedAction:
    return ProposedAction(
        description=data["description"],
        citations=decode_citations(data.get("citations", [])),
    )


# --- Audit value objects ------------------------------------------------------------


def encode_actor(actor: Actor) -> dict:
    return {
        "kind": actor.kind.value,
        "reference": actor.reference,
        "display_name": actor.display_name,
    }


def decode_actor(data: dict) -> Actor:
    return Actor(
        kind=ActorKind(data["kind"]),
        reference=data.get("reference"),
        display_name=data.get("display_name"),
    )


def encode_trace(trace: TraceContext | None) -> dict | None:
    if trace is None:
        return None
    return {"trace_id": trace.trace_id, "span_id": trace.span_id}


def decode_trace(data: dict | None) -> TraceContext | None:
    if data is None:
        return None
    return TraceContext(trace_id=data["trace_id"], span_id=data.get("span_id"))


def encode_ai_call(trace: AiCallTrace | None) -> dict | None:
    if trace is None:
        return None
    return {
        "provider": trace.provider,
        "model": trace.model,
        "model_version": trace.model_version,
        "prompt_version": trace.prompt_version,
        "input_tokens": trace.input_tokens,
        "output_tokens": trace.output_tokens,
        "latency_ms": trace.latency_ms,
        "cost_usd": trace.cost_usd,
    }


def decode_ai_call(data: dict | None) -> AiCallTrace | None:
    if data is None:
        return None
    return AiCallTrace(
        provider=data["provider"],
        model=data["model"],
        model_version=data["model_version"],
        prompt_version=data["prompt_version"],
        input_tokens=data["input_tokens"],
        output_tokens=data["output_tokens"],
        latency_ms=data["latency_ms"],
        cost_usd=data["cost_usd"],
    )
