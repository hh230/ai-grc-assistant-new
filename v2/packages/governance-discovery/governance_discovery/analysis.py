"""Tier B — one-shot holistic analysis (ADR 0066 §2, §2.5, §4).

Runs exactly once, when a session concludes: every rule contributed by every currently-active
Knowledge Pack fires (or doesn't) against the FINAL, complete SignalSet in a single batch pass.
Never incremental, never partially visible during the interview. Produces the one atomic
`Applicability` result the `generate_governance_plan` Mission later reads — the Mission never
re-evaluates rules itself.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from governance_discovery.capacity import compute_capacity
from governance_discovery.engine import REQUIRED_PRIORITY_THRESHOLD, DiscoveryEngine
from governance_discovery.pack import KnowledgePack, PlanSeed
from governance_discovery.predicate import evaluate, referenced_signals
from governance_discovery.scheduler import schedule
from governance_discovery.signal import DEFAULT_MATURITY_SCALE, Signal, SignalSet, ValueType

# Five report-facing dimensions (ADR 0066 §4 "Current Maturity") — "policy" folds into
# "governance" (policies are a governance artifact) and "operational" is renamed "cyber" (what it
# actually measured); "leadership" is new, fed by board/compliance-ownership/execution-capacity
# signals rather than a single question.
MATURITY_DIMENSIONS: tuple[str, ...] = ("governance", "risk", "compliance", "cyber", "leadership")

# Star rating (0-5) derived from the 0-10 raw score, with a matching label — both shown together
# (ADR 0066 §4: "the stars alone don't carry enough meaning"). 6-point scale, index == star count.
MATURITY_LABELS_BY_STAR: tuple[str, ...] = (
    "none", "limited", "initial", "developing", "established", "optimized",
)

_LOW_CONFIDENCE_SEED = PlanSeed(
    id="seed:confirm_basics_with_advisor",
    pillar="governance",
    title_key="plan.seed.confirm_basics_with_advisor.title",
    rationale_key="plan.seed.confirm_basics_with_advisor.rationale",
    urgency="high",
    effort_size="small",
)

# Signals a "best case, plan fully executed" projection upgrades (ADR 0066 §4 "Governance
# Vision") — every ordered maturity-scale signal goes to its top value; every named
# accountability/function boolean flips to True. Structural facts (sector, headcount, execution
# capacity) are left untouched: completing a governance plan doesn't change what industry you're
# in or how many people you employ.
_VISION_BOOLEAN_UPGRADES: tuple[str, ...] = (
    "has_compliance_officer",
    "has_legal_team",
    "has_it_team",
    "has_board",
)


def stars_and_label(score: int) -> tuple[int, str]:
    stars = max(0, min(5, round(score / 2)))
    return stars, MATURITY_LABELS_BY_STAR[stars]


def rate_maturity_scores(scores: dict[str, int]) -> dict[str, dict]:
    """`{dimension: raw_score}` -> `{dimension: {"score", "stars", "label"}}` — public so Plan
    Execution (ADR 0066 §5.3) can rate a *recalculated* maturity snapshot the same way `analyze()`
    rates the original one, without needing a full `Applicability`."""
    return {dim: dict(zip(("score", "stars", "label"), (score, *stars_and_label(score))))
            for dim, score in scores.items()}


@dataclass(frozen=True)
class Applicability:
    frameworks: tuple[dict, ...]  # [{framework_id, confidence, rationale_key}]
    maturity: dict[str, dict]  # dimension -> {"score", "stars", "label"}
    maturity_vision: dict[str, dict]  # dimension -> {"score", "stars", "label"}, plan fully executed
    capacity: dict  # {score, tier, per_period_budget}
    gaps: tuple[dict, ...]  # [{gap_id, severity, rationale_key}]
    plan_items: tuple[dict, ...]  # scheduled items, output of the Scheduler
    confidence_score: float
    confidence: str  # "normal" | "low"


def score_maturity(signals: SignalSet, active_packs: list[KnowledgePack]) -> dict[str, int]:
    """The deterministic scoring pass alone (no frameworks/gaps/plan_seeds) — shared by the real
    analysis, the hypothetical "vision" projection, and Plan Execution's recalculation after a
    task completes (ADR 0066 §5.3), so all three use one definition of how a dimension's score is
    computed. Public: Plan Execution calls this directly, outside any `analyze()` pass."""
    scores: dict[str, int] = {dim: 0 for dim in MATURITY_DIMENSIONS}
    for pack in active_packs:
        for rule in pack.rules:
            effect = rule.effect
            if not effect.maturity_dimension_score:
                continue
            if not evaluate(rule.predicate, signals):
                continue
            dim_score = effect.maturity_dimension_score
            scores[dim_score.dimension] = max(
                0, min(10, scores.get(dim_score.dimension, 0) + dim_score.delta)
            )
    return scores


def _best_case_signals(signals: SignalSet) -> SignalSet:
    upgraded = signals
    for key in signals.keys():
        signal = signals.get(key)
        if signal.value_type == ValueType.ENUM and signal.value in DEFAULT_MATURITY_SCALE:
            upgraded = upgraded.with_signal(replace(signal, value=DEFAULT_MATURITY_SCALE[-1]))
    for key in _VISION_BOOLEAN_UPGRADES:
        upgraded = upgraded.with_signal(
            Signal(key=key, value_type=ValueType.BOOLEAN, value=True)
        )
    return upgraded


def _signal_support(signals: SignalSet, keys: frozenset[str]) -> float:
    """Mean `Signal.confidence` across the signals a rule's predicate actually reads (ADR 0066
    §5.6) — how much of THIS conclusion rests on clearly-stated facts. `1.0` for a rule that reads
    no signal at all (shouldn't happen in practice, but never divides by zero)."""
    confidences = [s.confidence for s in (signals.get(k) for k in keys) if s is not None]
    return sum(confidences) / len(confidences) if confidences else 1.0


def analyze(signals: SignalSet, engine: DiscoveryEngine) -> Applicability:
    active_packs: list[KnowledgePack] = engine.active_packs(signals)

    frameworks: dict[str, dict] = {}
    gaps: list[dict] = []
    plan_seeds: list[PlanSeed] = []
    # Per-seed provenance for §5.6 Confidence and traceability (CLAUDE.md §19) — keyed by
    # plan_seed.id, filled in as each firing rule is processed below.
    seed_signal_keys: dict[str, frozenset[str]] = {}
    seed_signal_support: dict[str, float] = {}

    for pack in active_packs:
        for rule in pack.rules:
            if not evaluate(rule.predicate, signals):
                continue
            effect = rule.effect
            if effect.recommends_framework:
                fw = effect.recommends_framework
                existing = frameworks.get(fw.framework_id)
                if existing is None or fw.confidence > existing["confidence"]:
                    frameworks[fw.framework_id] = {
                        "framework_id": fw.framework_id,
                        "confidence": fw.confidence,
                        "rationale_key": fw.rationale_key,
                    }
            if effect.flags_gap:
                gap = effect.flags_gap
                gaps.append(
                    {"gap_id": gap.gap_id, "severity": gap.severity, "rationale_key": gap.rationale_key}
                )
            if effect.plan_seed:
                seed = effect.plan_seed
                plan_seeds.append(seed)
                keys = referenced_signals(rule.predicate)
                seed_signal_keys[seed.id] = keys
                seed_signal_support[seed.id] = _signal_support(signals, keys)

    answered_required, total_required = engine.required_question_coverage(signals)
    confidence_score = answered_required / total_required if total_required else 1.0
    confidence = "low" if confidence_score < 0.8 else "normal"

    if confidence == "low" and not plan_seeds:
        plan_seeds = [_LOW_CONFIDENCE_SEED]
        seed_signal_keys[_LOW_CONFIDENCE_SEED.id] = frozenset()
        seed_signal_support[_LOW_CONFIDENCE_SEED.id] = confidence_score

    capacity = compute_capacity(signals)
    scheduled = schedule(plan_seeds, capacity)
    plan_items = tuple(
        {
            **item,
            "source_signal_keys": sorted(seed_signal_keys.get(item["id"], frozenset())),
            "confidence": round(seed_signal_support.get(item["id"], 1.0) * confidence_score, 3),
        }
        for item in scheduled
    )

    current_scores = score_maturity(signals, active_packs)
    vision_scores = score_maturity(_best_case_signals(signals), active_packs)

    return Applicability(
        frameworks=tuple(frameworks.values()),
        maturity=rate_maturity_scores(current_scores),
        maturity_vision=rate_maturity_scores(vision_scores),
        capacity=capacity,
        gaps=tuple(gaps),
        plan_items=plan_items,
        confidence_score=round(confidence_score, 3),
        confidence=confidence,
    )


__all__ = [
    "Applicability",
    "analyze",
    "MATURITY_DIMENSIONS",
    "MATURITY_LABELS_BY_STAR",
    "stars_and_label",
    "rate_maturity_scores",
    "score_maturity",
    "REQUIRED_PRIORITY_THRESHOLD",
]
