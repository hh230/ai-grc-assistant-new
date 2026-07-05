"""The Policy Builder drafting engine — pure, deterministic, no LLM (the same design choice
ADR-0020/ADR-0021 made for Policy Hunter and Policy Analyst: CLAUDE.md §1 prefers a
reproducible, evidence-bound result over a model's free-form generation wherever one is
available and sufficient).

A template, not a generator: every section is either (a) grounded — quoting the obligation's
own text, with a citation, never paraphrased or embellished, or (b) an explicit
``[Human input required: ...]`` placeholder for anything that requires a person's specific
judgment (scope, ownership, responsibilities, the concrete controls, review cadence,
exceptions process). Nothing here is invented. The seven sections mirror
``grc_policy_analyst.quality_engine``'s own completeness check exactly (purpose, scope,
ownership, responsibilities, controls, review cycle, exceptions) — deliberately, so a human
who later saves this draft and runs Policy Analyst against it sees precisely the placeholders
still needing their attention, not a false "complete" signal.
"""

from __future__ import annotations

from .models import ObligationForDrafting, PolicyDraft

_PLACEHOLDER_SECTIONS: tuple[str, ...] = (
    "scope",
    "ownership",
    "responsibilities",
    "controls",
    "review cycle",
    "exceptions",
)


def _humanize(control_domain: str) -> str:
    return control_domain.replace("_", " ").capitalize()


def _citation(obligation: ObligationForDrafting) -> str:
    return f"{obligation.source_id}#{obligation.obligation_id}"


def draft_policy(obligation: ObligationForDrafting) -> PolicyDraft:
    """Draft a starter policy for one confirmed obligation. Deterministic: the same
    obligation always produces the same draft, byte for byte."""
    citation = _citation(obligation)
    control_domain_label = _humanize(obligation.control_domain)

    body = "\n\n".join(
        [
            f"Purpose: This policy establishes requirements to address the following "
            f'regulatory obligation: "{obligation.obligation_text}" ({citation}).',
            "Scope: [Human input required: define the systems, data, and personnel this "
            "policy covers.]",
            "Ownership: [Human input required: assign an accountable policy owner.]",
            "Responsibilities: [Human input required: define who implements and maintains "
            "compliance with this policy.]",
            "Controls: [Human input required: specify the technical and procedural controls "
            f"that satisfy this obligation. Suggested control domain: {control_domain_label}.]",
            "Review Cycle: [Human input required: define how often this policy is reviewed.]",
            "Exceptions: [Human input required: define the process for requesting and "
            "approving exceptions to this policy.]",
        ]
    )

    return PolicyDraft(
        obligation_id=obligation.obligation_id,
        title=obligation.suggested_policy_title,
        body=body,
        citation=citation,
        sections_requiring_human_input=_PLACEHOLDER_SECTIONS,
    )
