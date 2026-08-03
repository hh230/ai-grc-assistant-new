"""Execution-capacity scoring (ADR 0066 §2.5) — a core, pack-independent Tier B computation,
alongside maturity. Deterministic and auditable: a weighted function of `core` signals, never an
LLM guess. Its output — a capacity *tier* and a per-period item budget — is what the Scheduler
(`scheduler.py`) uses to size the plan to what the organization can actually execute, instead of
handing a 3-person firm and a 3,000-person enterprise the same template.
"""

from __future__ import annotations

import math

from governance_discovery.signal import SignalSet

# Ordered, custom scale (not the default maturity scale) for the self-reported capacity question.
EXECUTION_CAPACITY_SCALE: tuple[str, ...] = (
    "none",
    "ad_hoc",
    "allocated_time",
    "dedicated_budget",
    "dedicated_team_and_budget",
)

CAPACITY_TIERS: tuple[str, ...] = ("micro", "small", "mid", "large", "enterprise")

# Per-period item budget by tier: how many plan items the Scheduler may place in each bucket
# before spilling to the next. `year_1` is deliberately unbounded (no cap key = unlimited) — the
# final catch-all, matching the report's six-period timeline (ADR 0066 §4: Week 1, Week 2, Month
# 1, Month 3, Month 6, Year 1).
PER_PERIOD_BUDGET: dict[str, dict[str, int]] = {
    "micro": {"week_1": 2, "week_2": 2, "month_1": 4, "month_3": 4, "month_6": 4},
    "small": {"week_1": 3, "week_2": 3, "month_1": 6, "month_3": 6, "month_6": 6},
    "mid": {"week_1": 5, "week_2": 5, "month_1": 10, "month_3": 10, "month_6": 10},
    "large": {"week_1": 8, "week_2": 8, "month_1": 16, "month_3": 16, "month_6": 16},
    "enterprise": {"week_1": 12, "week_2": 12, "month_1": 24, "month_3": 24, "month_6": 24},
}

_TIER_SCORE_FLOORS: tuple[tuple[int, str], ...] = (
    (70, "enterprise"),
    (50, "large"),
    (30, "mid"),
    (15, "small"),
    (0, "micro"),
)


def _tier_for_score(score: float) -> str:
    for floor, tier in _TIER_SCORE_FLOORS:
        if score >= floor:
            return tier
    return "micro"  # pragma: no cover - unreachable, floors bottom out at 0


def compute_capacity(signals: SignalSet) -> dict:
    """Weighted, deterministic, and intentionally simple: log-scaled headcount (so capacity grows
    sub-linearly with size, not 1:1) plus fixed bonuses for each dedicated function actually in
    place, plus the org's own self-reported execution capacity. Every weight here is a tunable
    constant, not a hidden model — that is the point (CLAUDE.md §6 pillar 8)."""
    employee_count = signals.value("employee_count", 1) or 1
    score = min(40.0, math.log2(max(employee_count, 1) + 1) * 6)

    if signals.value("has_legal_team") is True:
        score += 10
    if signals.value("has_it_team") is True:
        score += 10
    if signals.value("has_compliance_officer") is True:
        score += 15

    execution_capacity = signals.value("execution_capacity")
    if execution_capacity in EXECUTION_CAPACITY_SCALE:
        score += EXECUTION_CAPACITY_SCALE.index(execution_capacity) * 6

    tier = _tier_for_score(score)
    return {
        "score": round(score, 1),
        "tier": tier,
        "per_period_budget": dict(PER_PERIOD_BUDGET[tier]),
    }
