"""Prompt validation — the gate before an LLMRequest is considered production-ready.

Reject a request that:
  • misses the workflow (no workflow segment / no workflow id),
  • misses the response contract (no contract, or an empty one),
  • loses context (the ContextPackage had blocks, but they didn't all reach the prompt),
  • loses citations (a rendered block whose citation is incomplete or absent from the text),
  • was built from an invalid ContextPackage (we don't send unvalidated context to an LLM).

An absent-but-legitimately-empty context (a conversation, or a genuine "insufficient
evidence" retrieval) is not a loss — it is handled, not rejected.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pipeline_contracts import ContextPackage, citation_is_complete

from prompt_orchestrator.models import LLMRequest, SegmentKind
from prompt_orchestrator.renderer import RenderedContext


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    issues: list[str] = field(default_factory=list)


def validate(
    request: LLMRequest,
    context_package: ContextPackage | None,
    rendered: RenderedContext | None,
) -> ValidationResult:
    issues: list[str] = []

    # structural layers
    if not request.workflow or request.segment(SegmentKind.WORKFLOW) is None:
        issues.append("missing workflow")
    if request.segment(SegmentKind.IDENTITY) is None:
        issues.append("missing system prompt")
    if request.segment(SegmentKind.USER_REQUEST) is None:
        issues.append("missing user request")

    contract = request.response_contract
    if request.segment(SegmentKind.RESPONSE_CONTRACT) is None or contract is None or contract.is_empty():
        issues.append("missing response contract")

    # context integrity
    if context_package is not None and not context_package.valid:
        issues.append("context package is invalid")

    package_blocks = context_package.all_blocks() if context_package else []
    if package_blocks:
        context_segment = request.segment(SegmentKind.CONTEXT)
        if context_segment is None or rendered is None:
            issues.append("context lost: package had blocks but no context segment was rendered")
        else:
            if rendered.block_count != len(package_blocks):
                issues.append(
                    f"context lost: {len(package_blocks)} blocks in package but "
                    f"{rendered.block_count} rendered"
                )
            for marker, citation in rendered.markers:
                if not citation_is_complete(citation):
                    issues.append(f"citation lost: incomplete citation for marker [{marker}]")
                elif citation.formatted not in context_segment.content:
                    issues.append(f"citation lost: marker [{marker}] source not present in context")
            # if the workflow requires citations, they must actually be there
            if contract and contract.required_citations and rendered.block_count == 0:
                issues.append("citations required but none rendered")

    return ValidationResult(is_valid=not issues, issues=issues)
