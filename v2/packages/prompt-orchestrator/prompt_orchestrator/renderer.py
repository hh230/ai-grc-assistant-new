"""Rendering — turn the structured inputs into the text of each prompt segment.

The important one is `render_context`: it walks the `ContextPackage` and assigns every block
a stable citation marker ([S1], [S2], …), emitting both the cited context body and a Sources
legend. Assigning a marker to *every* block is what guarantees no citation is dropped between
the Context Builder and the prompt — validation later checks that the marker count equals the
block count and that every source appears.

Pure functions only — no selection logic (that's the orchestrator), no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pipeline_contracts import Citation, ContextPackage

from prompt_orchestrator.models import Language, ResponseContract
from prompt_orchestrator.policies import PromptPolicy


@dataclass
class RenderedContext:
    text: str
    markers: list[tuple[str, Citation]] = field(default_factory=list)

    @property
    def block_count(self) -> int:
        return len(self.markers)


def render_context(package: ContextPackage | None) -> RenderedContext:
    if package is None or not package.sections:
        return RenderedContext(
            text="# Context\n\n(No supporting evidence was retrieved for this request.)",
            markers=[],
        )

    lines: list[str] = ["# Context", ""]
    legend: list[str] = []
    markers: list[tuple[str, Citation]] = []
    n = 0
    for section in package.sections:
        lines.append(f"## {section.title}")
        for block in section.blocks:
            n += 1
            marker = f"S{n}"
            markers.append((marker, block.citation))
            lines.append(f"[{marker}] {block.citation.formatted}")
            lines.append(block.text.strip())
            lines.append("")
            legend.append(f"[{marker}] {block.citation.formatted}")

    lines.append("## Sources")
    lines.extend(legend)
    return RenderedContext(text="\n".join(lines), markers=markers)


def render_policies(policies: list[PromptPolicy], language: Language) -> str:
    if not policies:
        return ""
    body = "\n".join(f"- {p.render(language)}" for p in policies)
    return f"# Policies\n{body}"


def render_contract(contract: ResponseContract) -> str:
    lines = ["# Expected Response", "Produce your answer with exactly these sections:"]
    lines += [f"  {i}. {s}" for i, s in enumerate(contract.required_sections, 1)]
    if contract.required_citations:
        lines.append(f"Citations: required — {contract.citation_style}.")
    else:
        lines.append("Citations: not required for this response.")
    if contract.required_formatting:
        lines.append("Formatting: " + "; ".join(contract.required_formatting) + ".")
    if contract.required_confidence:
        lines.append("Confidence: include an explicit confidence level (high/medium/low) with its basis.")
    if contract.forbidden_outputs:
        lines.append("Do NOT produce: " + "; ".join(contract.forbidden_outputs) + ".")
    return "\n".join(lines)


def render_developer_instructions(plan_reason: str, workflow: str, language: Language) -> str:
    return (
        "# Developer Instructions\n"
        f"This is a '{workflow}' request routed by the Decision Engine ({plan_reason}). "
        "Follow the system rules, the task below, and the policies. Use only the Context for "
        "factual GRC claims, and honour the Expected Response section exactly."
    )


def render_user_request(query: str, has_document: bool, language: Language) -> str:
    note = "\n\n(An attached document accompanies this request; it appears in the Context.)" if has_document else ""
    return f"# User Request\n{query.strip()}{note}"
