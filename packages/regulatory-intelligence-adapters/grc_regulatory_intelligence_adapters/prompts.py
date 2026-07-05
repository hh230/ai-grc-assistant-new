"""Versioned prompt artifact for the classifier Tool (CLAUDE.md §22: prompts are versioned
files, never inline in business logic). Recorded with every Tool invocation via
``ToolOutcome.prompt_version`` / ``ai_tool_invocations.prompt_version``.
"""

from __future__ import annotations

from grc_regulatory_intelligence import ControlDomain, ObligationType, Severity

CLASSIFY_REGULATORY_OBLIGATION_VERSION = "classify_regulatory_obligation.v1"

_OBLIGATION_TYPES = ", ".join(sorted(member.value for member in ObligationType))
_CONTROL_DOMAINS = ", ".join(sorted(member.value for member in ControlDomain))
_SEVERITIES = ", ".join(sorted(member.value for member in Severity))

CLASSIFY_REGULATORY_OBLIGATION_SYSTEM = (
    "You are a Governance, Risk & Compliance (GRC) regulatory classification assistant. "
    "Classify ONE regulatory obligation extracted from a source document. Use ONLY the "
    "obligation text given — do not invent context or assume facts not stated.\n"
    "Respond with a single JSON object with exactly these fields:\n"
    f'- "obligation_type": one of [{_OBLIGATION_TYPES}]\n'
    f'- "control_domain": one of [{_CONTROL_DOMAINS}]\n'
    '- "suggested_policy_title": a short (<= 120 character) human-readable title for an '
    "internal policy that would satisfy this obligation\n"
    f'- "severity": one of [{_SEVERITIES}]\n'
    '- "confidence": a number between 0 and 1 reflecting how certain you are\n'
    "If you are unsure, choose the closest bucket and lower your confidence rather than "
    "omitting a field or inventing a new category."
)


def build_user_prompt(obligation_text: str, *, source_id: str) -> str:
    return (
        f"Regulatory source: {source_id}\n"
        f"Obligation text:\n{obligation_text}\n\n"
        "Respond with the JSON object only."
    )
