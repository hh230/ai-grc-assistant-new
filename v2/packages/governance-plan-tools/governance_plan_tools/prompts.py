"""Named, versioned prompt content for the Governance Plan drafting role (ADR 0066 §4/§5.2;
CLAUDE.md: "Prompts...named and versioned artifacts, never hardcoded inline"). Deliberately plain
f-string templates — matching the convention every existing `generate_text`-using capability
follows today (`gap_assessment.py`, `risk_assessment.py`: inline instruction strings, no separate
template package). `prompt-orchestrator`'s heavier `PromptTemplate` machinery backs the
retrieve-then-generate pipeline (`run_pipeline`); no existing builtin routes a raw `generate_text`
step through it, so this doesn't invent a second convention — it names and versions what's already
the de facto shape.

Hard rule enforced by `SYSTEM_PROMPT` itself, not just by convention: the LLM never names a
specific standard (ADR 0066 §4 "Methodology & Standards is the only place a framework is ever
named") and never invents a fact — every prompt hands it already-decided structure and asks only
for wording.
"""

from __future__ import annotations

SYSTEM_PROMPT_ID = "governance_plan.system.v1"
SYSTEM_PROMPT = (
    "You are a governance, risk, and compliance advisor writing for a business owner who does not "
    "know GRC terminology. Write in plain, direct, professional language — the register of a "
    "consulting deliverable, not a technical checklist. NEVER name a specific regulatory framework "
    "or standard by name (e.g. ISO 27001, NIST, PDPL, CIS, SOC 2) — describe outcomes and "
    "practices instead; the standards themselves are disclosed elsewhere, not in this text. Base "
    "every claim STRICTLY on the facts given to you in the request — never invent a fact, a "
    "number, or a finding that is not present in the provided context."
)

EXECUTIVE_BRIEF_PROMPT_ID = "governance_plan.executive_brief.v1"


def executive_brief_prompt(context: str) -> str:
    return (
        "Given the following structured assessment of an organization (maturity per dimension, "
        "and the gaps identified), write a 2-4 sentence executive brief — a consultant's opening "
        "assessment, not a summary. If the data clearly points to one root cause behind several "
        "symptoms, say so explicitly (e.g. 'the underlying issue is X, which is driving Y and Z') "
        "rather than listing findings side by side. End with one sentence recommending what to "
        "focus on first.\n\n"
        f"{context}"
    )


GAP_PROMPT_ID = "governance_plan.gap.v1"


def gap_prompt(gap_context: str) -> str:
    return (
        "Given this specific governance/compliance gap, respond in EXACTLY this two-line format "
        "(no extra text before or after):\n"
        "DESCRIPTION: <one sentence stating plainly what is missing>\n"
        "IMPACT: <one to two sentences on the concrete business consequence of leaving it "
        "unaddressed — not what it is, what could go wrong>\n\n"
        f"{gap_context}"
    )


PLAN_ITEM_PROMPT_ID = "governance_plan.item_prose.v1"


def plan_item_prompt(item_context: str) -> str:
    return (
        "Given this recommendation and the specific facts that triggered it, respond in EXACTLY "
        "this four-line format (no extra text before or after):\n"
        "RATIONALE: <1-2 sentences: why this was recommended, referencing the specific facts>\n"
        "OBJECTIVE: <one sentence: what this action sets out to achieve>\n"
        "EXPECTED_OUTCOME: <one sentence: what will be true once it is done>\n"
        "RISK_IF_SKIPPED: <1-2 sentences: the concrete consequence of not doing this>\n\n"
        f"{item_context}"
    )


__all__ = [
    "SYSTEM_PROMPT_ID",
    "SYSTEM_PROMPT",
    "EXECUTIVE_BRIEF_PROMPT_ID",
    "executive_brief_prompt",
    "GAP_PROMPT_ID",
    "gap_prompt",
    "PLAN_ITEM_PROMPT_ID",
    "plan_item_prompt",
]
