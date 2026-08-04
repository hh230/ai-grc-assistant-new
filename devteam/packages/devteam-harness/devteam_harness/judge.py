"""The AI Judge — a second model asks "is this plan sensible?" and argues for its score.

The Decision Verifier encodes judgements we can state as rules. This layer exists for the ones we
cannot: a plan can satisfy every rule and still be tone-deaf, generic, mis-sequenced for this
particular organization, or obviously written for a different kind of company. Those are failures a
GRC professional would spot in seconds and no deterministic check will ever catch.

**It never gates a release, and that is a design decision, not a limitation.** An LLM verdict is
non-reproducible and cannot be argued with: the same plan can score 88 and then 74, and there is no
seed that makes it 88 again. A gate built on it would be a gate that fails for reasons nobody can
investigate — which is how a gate stops being believed. So:

    Decision Verifier  → deterministic, reproducible, BLOCKS a release
    AI Judge           → nuanced, advisory, TRACKS quality over time

Its real value is as a **trend**: a score that drifts down across releases is early warning that
plan quality is degrading, long before any rule notices. And its written reasons are where the next
deterministic rule comes from — every time the judge explains a defect the rules missed, that
explanation is a candidate for `decisions.py`, at which point it becomes reproducible and can gate.

The judge is given the interview, the plan and the reasoning, and must return a score with
per-dimension justification. It is told to be a critical reviewer, because a judge that praises
everything measures nothing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

# Scored separately so a single number cannot hide a specific failure — a plan can be well
# sequenced and still address the wrong things, and one blended score would mask that.
DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("relevance", "Does the plan address what THIS organization actually said, not generic advice?"),
    ("coherence", "Can a person execute it top to bottom without hitting a missing prerequisite?"),
    ("prioritisation", "Is the most dangerous gap addressed first?"),
    ("proportionality", "Is the amount of work realistic for this organization's size and capacity?"),
    ("completeness", "Is any obvious, material gap left unaddressed?"),
)

MAX_SCORE = 100
# Below this, the plan is advice we would not want a customer to act on. Advisory only — it is
# reported, never enforced.
CONCERN_THRESHOLD = 70

SYSTEM_PROMPT = """You are a senior GRC reviewer auditing an AI-generated governance plan.

You are reviewing the PLAN's quality as professional advice, not the software that produced it.

Be critical. A plan that merely avoids errors is not a good plan; it must be the right advice for
this specific organization. If it reads like generic compliance boilerplate that would suit any
company, say so and score it down — that is the most common and most damaging failure.

Score each dimension 0-20 and give a one-sentence reason for each. Then give the total 0-100 and a
short overall verdict. Cite the organization's own answers when you criticise, so the reasoning can
be checked rather than taken on trust.

Respond with JSON only:
{"dimensions": {"<name>": {"score": <0-20>, "reason": "<one sentence>"}}, "total": <0-100>,
 "verdict": "<two sentences>", "worst_problem": "<the single most important defect, or empty>"}"""


class LLMClient(Protocol):
    """The seam. Any callable that takes a prompt and returns text — so this module depends on no
    provider SDK, and a test can judge without a network or a key (CLAUDE.md §4)."""

    def complete(self, *, system: str, user: str) -> str: ...


@dataclass(frozen=True)
class DimensionScore:
    name: str
    score: int
    reason: str


@dataclass
class Judgement:
    """One plan's verdict. `parsed` is False when the model returned something unusable — recorded
    rather than raised, so one bad response does not end a run over hundreds of plans."""

    seed: int
    total: int = 0
    dimensions: list[DimensionScore] = field(default_factory=list)
    verdict: str = ""
    worst_problem: str = ""
    parsed: bool = True
    raw: str = ""

    @property
    def concerning(self) -> bool:
        return self.parsed and self.total < CONCERN_THRESHOLD

    def render(self) -> str:
        if not self.parsed:
            return f"seed {self.seed}: unparseable judgement"
        lines = [f"seed {self.seed}: {self.total}/{MAX_SCORE} — {self.verdict}"]
        for dimension in self.dimensions:
            lines.append(f"    {dimension.name:16} {dimension.score:>2}/20  {dimension.reason}")
        if self.worst_problem:
            lines.append(f"    worst problem: {self.worst_problem}")
        return "\n".join(lines)


def build_prompt(*, transcript: list[Any], plan_items: list[dict[str, Any]], reasoning: str) -> str:
    """Interview → plan → reasoning, as the judge sees it.

    The organization's OWN answers are included verbatim. Judging a plan without them would only
    ask "is this a reasonable plan in general", which is precisely the generic-advice failure this
    layer exists to catch.
    """
    answers = [
        f"  {turn.question_id.removeprefix('q:')}: {turn.answer!r}"
        for turn in transcript
        if not turn.skipped and turn.answer is not None
    ]
    tasks = [
        f"  - [{item.get('priority')}] {item['id'].removeprefix('seed:')} "
        f"(do by {item.get('timeframe_bucket')}, effort {item.get('effort_size')})"
        for item in plan_items
    ]
    return "\n".join(
        [
            "WHAT THE ORGANIZATION SAID:",
            *(answers or ["  (no answers recorded)"]),
            "",
            "THE PLAN IT WAS GIVEN:",
            *(tasks or ["  (the plan is EMPTY — no tasks at all)"]),
            "",
            "THE SYSTEM'S REASONING:",
            reasoning or "  (none recorded)",
            "",
            "Scored dimensions:",
            *(f"  {name}: {question}" for name, question in DIMENSIONS),
        ]
    )


def judge_plan(
    client: LLMClient,
    *,
    seed: int,
    transcript: list[Any],
    plan_items: list[dict[str, Any]],
    reasoning: str = "",
) -> Judgement:
    """Ask the judge about one plan. A malformed response is recorded, never raised."""
    raw = client.complete(
        system=SYSTEM_PROMPT,
        user=build_prompt(transcript=transcript, plan_items=plan_items, reasoning=reasoning),
    )
    return parse_judgement(seed, raw)


def parse_judgement(seed: int, raw: str) -> Judgement:
    """Parse the model's JSON defensively.

    LLM output is untrusted input (CLAUDE.md §19/§22): it is validated, never trusted, and a
    response that cannot be parsed is a recorded outcome rather than an exception that would end a
    run over hundreds of plans.
    """
    text = raw.strip()
    # Models routinely wrap JSON in a fenced block despite being told not to.
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text
        text = text.removeprefix("json").strip()

    try:
        payload = json.loads(text)
    except (ValueError, IndexError):
        return Judgement(seed=seed, parsed=False, raw=raw[:500])
    if not isinstance(payload, dict):
        return Judgement(seed=seed, parsed=False, raw=raw[:500])

    dimensions = []
    for name, _question in DIMENSIONS:
        entry = payload.get("dimensions", {}).get(name)
        if isinstance(entry, dict):
            dimensions.append(
                DimensionScore(
                    name=name,
                    score=_clamp(entry.get("score"), 0, 20),
                    reason=str(entry.get("reason", ""))[:300],
                )
            )

    return Judgement(
        seed=seed,
        total=_clamp(payload.get("total"), 0, MAX_SCORE),
        dimensions=dimensions,
        verdict=str(payload.get("verdict", ""))[:500],
        worst_problem=str(payload.get("worst_problem", ""))[:300],
        raw=raw[:500],
    )


def _clamp(value: Any, low: int, high: int) -> int:
    """A score outside its range is a model error, not a reason to crash — pull it back in."""
    try:
        return max(low, min(high, int(float(value))))
    except (TypeError, ValueError):
        return low


@dataclass
class JudgePanel:
    """Aggregate verdicts across a population — the trend, which is the point.

    A single score says little; the distribution and its movement across releases is what warns
    that plan quality is drifting before any rule notices.
    """

    judgements: list[Judgement] = field(default_factory=list)

    def add(self, judgement: Judgement) -> None:
        self.judgements.append(judgement)

    @property
    def scored(self) -> list[Judgement]:
        return [judgement for judgement in self.judgements if judgement.parsed]

    @property
    def average(self) -> float:
        scored = self.scored
        return round(sum(j.total for j in scored) / len(scored), 1) if scored else 0.0

    @property
    def concerning(self) -> list[Judgement]:
        return sorted(
            (j for j in self.scored if j.concerning), key=lambda judgement: judgement.total
        )

    def dimension_averages(self) -> dict[str, float]:
        """Where quality is actually weak. A blended total hides which dimension is dragging."""
        totals: dict[str, list[int]] = {name: [] for name, _ in DIMENSIONS}
        for judgement in self.scored:
            for dimension in judgement.dimensions:
                totals.setdefault(dimension.name, []).append(dimension.score)
        return {
            name: round(sum(scores) / len(scores), 1)
            for name, scores in totals.items()
            if scores
        }

    def render(self) -> str:
        if not self.scored:
            return "judge: no parseable judgements"
        lines = [
            f"judge: {self.average}/{MAX_SCORE} average over {len(self.scored)} plan(s)",
            "  by dimension: "
            + "  ".join(f"{name}={score}" for name, score in self.dimension_averages().items()),
        ]
        unparsed = len(self.judgements) - len(self.scored)
        if unparsed:
            # Reported, never silently dropped — the same rule the whole harness follows.
            lines.append(f"  {unparsed} response(s) could not be parsed and were NOT scored")
        if self.concerning:
            lines.append(f"  {len(self.concerning)} plan(s) below {CONCERN_THRESHOLD}:")
            lines.extend(f"    {j.render().splitlines()[0]}" for j in self.concerning[:5])
        return "\n".join(lines)
