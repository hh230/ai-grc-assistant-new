"""`PLAN_DRAFT_TOOL` — assembles the complete Governance Plan DRAFT (ADR 0066 §3, §4, §5.2):
computes due dates, and drafts the bounded LLM prose (Executive Brief, per-gap Business Impact,
per-item rationale/objective/expected-outcome/risk-if-skipped) grounded strictly in the
deterministic Tier B output — never deciding structure, priority, or timing, all of which are
already fixed. Produces the reviewable draft as structured JSON; nothing is persisted here — the
human reviews THIS before the approval-gated `finalize_plan` step runs (ADR 0066 §3, revised: the
draft/finalize split exists because the Mission Engine's approval gate pauses BEFORE a consequential
step runs, so the reviewable content must already exist by the time the gate is crossed).
"""

from __future__ import annotations

import json
import re
import time
from typing import Callable

from governance_discovery.scheduler import compute_due_at
from governance_store import PostgresGovernanceStore
from pipeline_contracts import (
    GenerationError,
    GenerationProvider,
    Language,
    LLMRequest,
    PromptFamily,
    PromptSegment,
    ResponseContract,
    SegmentKind,
    SegmentRole,
    TenantContext,
)
from tool_registry import PAYLOAD_INSTRUCTION, SideEffectProfile, ToolSpec, ToolStepResult

from governance_plan_tools import prompts

PLAN_DRAFT_TOOL = "governance_plan_draft"

_NO_CITATIONS_CONTRACT = ResponseContract(
    workflow="governance_plan_draft",
    required_sections=(),
    required_citations=False,
    citation_style="",
    required_formatting=(),
    required_confidence=False,
    forbidden_outputs=(),
)

_FALLBACK_RATIONALE = "This was identified as a gap during the assessment."
_FALLBACK_OBJECTIVE = "Address the identified gap."
_FALLBACK_OUTCOME = "The gap is resolved."
_FALLBACK_RISK = "The underlying gap remains unaddressed."
_FALLBACK_GAP_DESCRIPTION = "A gap was identified during the assessment."
_FALLBACK_GAP_IMPACT = "This gap may expose the organization to avoidable risk."
_FALLBACK_EXECUTIVE_BRIEF = (
    "This assessment identifies specific gaps in your current governance practices. "
    "The plan below addresses them in order of priority and executive capacity."
)


def _humanize(key: str) -> str:
    """A deterministic title fallback/seed from an i18n key like
    `plan.seed.establish_risk_register.title` -> `Establish Risk Register`. No LLM call — titles
    are short and literal, not worth the drafting role's grounding budget."""
    middle = re.sub(r"^plan\.(seed|gap)\.", "", key)
    middle = re.sub(r"\.(title|rationale)$", "", middle)
    return middle.replace("_", " ").replace(":", " ").strip().title()


class PlanDraftTool:
    def __init__(
        self,
        store: PostgresGovernanceStore,
        provider: GenerationProvider,
        *,
        version: int = 1,
        language: Language = Language.ENGLISH,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._store = store
        self._provider = provider
        self._language = language
        self._now = now
        self._spec = ToolSpec(
            name=PLAN_DRAFT_TOOL,
            version=version,
            description=(
                "Draft a complete Governance Plan (executive brief, business impact per gap, "
                "per-item prose, due dates) for human review before it is finalized."
            ),
            side_effect=SideEffectProfile.READ_ONLY,  # drafting persists nothing
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def invoke(self, payload: dict[str, object], tenant: TenantContext) -> dict[str, object]:
        session_id = str(payload.get(PAYLOAD_INSTRUCTION, "")).strip()
        if not session_id:
            return _fail("no discovery_session_id given")
        session = self._store.get_session(session_id, tenant.tenant_id)
        if session is None or session.status != "concluded" or session.applicability is None:
            return _fail("discovery session has not concluded yet")

        applicability = session.applicability
        now = self._now()
        warnings: list[str] = []

        executive_summary = self._draft_executive_brief(applicability, warnings)
        top_risks = [self._draft_gap(gap, warnings) for gap in applicability.gaps]
        items = [self._draft_item(item, now, warnings) for item in applicability.plan_items]

        draft = {
            "source_session_id": session.id,
            "inferred_frameworks": list(applicability.frameworks),
            "maturity_baseline": applicability.maturity,
            "maturity_vision": applicability.maturity_vision,
            "executive_summary": executive_summary,
            "top_risks": top_risks,
            "items": items,
            "drafted_at": now,
        }
        return ToolStepResult(
            ok=True, output=json.dumps(draft), warnings=tuple(warnings)
        ).as_payload()

    # --- LLM-drafted prose, each call bounded to wording over already-fixed facts -------------

    def _generate(self, prompt: str) -> str | None:
        request = LLMRequest(
            family=PromptFamily.TOOL,
            workflow="governance_plan_draft",
            language=self._language,
            segments=[
                PromptSegment(
                    role=SegmentRole.SYSTEM,
                    kind=SegmentKind.IDENTITY,
                    title="System",
                    content=prompts.SYSTEM_PROMPT,
                    source=prompts.SYSTEM_PROMPT_ID,
                ),
                PromptSegment(
                    role=SegmentRole.USER, kind=SegmentKind.USER_REQUEST, title="Request", content=prompt
                ),
            ],
            response_contract=_NO_CITATIONS_CONTRACT,
            params={"temperature": 0.3, "max_output_tokens": 400},
        )
        try:
            return self._provider.generate(request).text
        except GenerationError:
            return None

    def _draft_executive_brief(self, applicability, warnings: list[str]) -> str:
        context = json.dumps(
            {"maturity": applicability.maturity, "gaps": list(applicability.gaps), "capacity": applicability.capacity}
        )
        text = self._generate(prompts.executive_brief_prompt(context))
        if not text:
            warnings.append("executive_brief: generation unavailable, used fallback text")
            return _FALLBACK_EXECUTIVE_BRIEF
        return text.strip()

    def _draft_gap(self, gap: dict, warnings: list[str]) -> dict:
        description_seed = _humanize(gap.get("rationale_key", gap.get("gap_id", "")))
        context = f"Gap id: {gap.get('gap_id')}\nSeverity: {gap.get('severity')}\nContext: {description_seed}"
        text = self._generate(prompts.gap_prompt(context))
        description, impact = _FALLBACK_GAP_DESCRIPTION, _FALLBACK_GAP_IMPACT
        if text:
            parsed = _parse_labeled_lines(text, ("DESCRIPTION", "IMPACT"))
            description = parsed.get("DESCRIPTION") or description_seed or description
            impact = parsed.get("IMPACT") or impact
        else:
            warnings.append(f"gap {gap.get('gap_id')}: generation unavailable, used fallback text")
        return {
            "gap_id": gap.get("gap_id"),
            "severity": gap.get("severity"),
            "description": description,
            "impact": impact,
        }

    def _draft_item(self, item: dict, now: float, warnings: list[str]) -> dict:
        title = _humanize(item.get("title_key", item.get("id", "")))
        rationale_seed = _humanize(item.get("rationale_key", ""))
        context = (
            f"Recommendation: {title}\n"
            f"Pillar: {item.get('pillar')}\n"
            f"Urgency: {item.get('priority')}\n"
            f"Triggered by facts about: {', '.join(item.get('source_signal_keys', [])) or 'the organization'}\n"
            f"Context: {rationale_seed}"
        )
        text = self._generate(prompts.plan_item_prompt(context))
        rationale, objective, outcome, risk = (
            _FALLBACK_RATIONALE,
            _FALLBACK_OBJECTIVE,
            _FALLBACK_OUTCOME,
            _FALLBACK_RISK,
        )
        if text:
            parsed = _parse_labeled_lines(
                text, ("RATIONALE", "OBJECTIVE", "EXPECTED_OUTCOME", "RISK_IF_SKIPPED")
            )
            rationale = parsed.get("RATIONALE") or rationale_seed or rationale
            objective = parsed.get("OBJECTIVE") or objective
            outcome = parsed.get("EXPECTED_OUTCOME") or outcome
            risk = parsed.get("RISK_IF_SKIPPED") or risk
        else:
            warnings.append(f"item {item.get('id')}: generation unavailable, used fallback text")

        return {
            **item,
            "title": title,
            "rationale": rationale,
            "objective": objective,
            "expected_outcome": outcome,
            "risk_if_skipped": risk,
            "due_at": compute_due_at(now, item["timeframe_bucket"]),
        }


def _parse_labeled_lines(text: str, labels: tuple[str, ...]) -> dict[str, str]:
    """Parses the `LABEL: content` lines the drafting prompts require — deterministic string
    parsing, never a second LLM call and never `eval`/JSON-guessing (CLAUDE.md §6 pillar 8). A
    label the model omits or a differently-shaped response simply yields no entry for that key,
    and the caller falls back to its own default text — never a crash, never a guess."""
    result: dict[str, str] = {}
    pattern = "|".join(re.escape(label) for label in labels)
    matches = list(re.finditer(rf"(?:^|\n)({pattern}):\s*(.*?)(?=\n(?:{pattern}):|\Z)", text, re.DOTALL))
    for match in matches:
        label, content = match.group(1), match.group(2).strip()
        if content:
            result[label] = content
    return result


def _fail(reason: str) -> dict[str, object]:
    return ToolStepResult(ok=False, output="", warnings=(reason,)).as_payload()
