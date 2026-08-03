"""The deterministic Scheduler (ADR 0066 §2.5) — turns capacity-agnostic `plan_seed`s (urgency +
effort + dependencies, no timing) into time-bucketed plan items, sized to what the organization
can actually execute. Never an LLM decision: a plain, auditable, greedy bin-packing algorithm over
the capacity tier's per-period item budget (`capacity.py`), so a small organization is never
handed an unexecutable week and a large one is never under-scheduled relative to what fired.
"""

from __future__ import annotations

from governance_discovery.pack import PlanSeed

BUCKET_ORDER: tuple[str, ...] = (
    "week_1", "week_2", "month_1", "month_3", "month_6", "year_1",
)
_URGENCY_RANK: dict[str, int] = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# Fixed, deterministic offsets from plan-creation time — what "Create Tasks" (ADR 0066 §3.1) uses
# to give every item a real `due_at`, not a null one. Seconds, not calendar months, so this needs
# no timezone/calendar library: a plain offset from a Unix timestamp.
_DAY_SECONDS = 86_400
DUE_AT_OFFSET_SECONDS: dict[str, int] = {
    "week_1": 7 * _DAY_SECONDS,
    "week_2": 14 * _DAY_SECONDS,
    "month_1": 30 * _DAY_SECONDS,
    "month_3": 90 * _DAY_SECONDS,
    "month_6": 180 * _DAY_SECONDS,
    "year_1": 365 * _DAY_SECONDS,
}


def compute_due_at(created_at: float, bucket: str) -> float:
    return created_at + DUE_AT_OFFSET_SECONDS[bucket]


def _seed_key(seed: PlanSeed) -> tuple[int, str]:
    # urgency first (critical fills buckets before low), then id for a fully deterministic,
    # reproducible ordering independent of dict/set iteration order.
    return (_URGENCY_RANK.get(seed.urgency, 2), seed.id)


def schedule(plan_seeds: list[PlanSeed], capacity: dict) -> list[dict]:
    """Returns one dict per seed: `{**seed fields, "timeframe_bucket": bucket}`. `capacity` is the
    dict `compute_capacity()` returns (`{"tier", "score", "per_period_budget"}`)."""
    budget: dict[str, int] = dict(capacity["per_period_budget"])  # no key => unlimited (final)
    bucket_fill: dict[str, int] = dict.fromkeys(BUCKET_ORDER, 0)
    scheduled_bucket: dict[str, str] = {}
    known_ids = {seed.id for seed in plan_seeds}

    def earliest_allowed_index(seed: PlanSeed) -> int:
        earliest = 0
        for dep_id in seed.depends_on:
            dep_bucket = scheduled_bucket.get(dep_id)
            if dep_bucket is not None:
                earliest = max(earliest, BUCKET_ORDER.index(dep_bucket))
        return earliest

    def place(seed: PlanSeed) -> str:
        for index in range(earliest_allowed_index(seed), len(BUCKET_ORDER)):
            bucket = BUCKET_ORDER[index]
            cap = budget.get(bucket)
            if cap is None or bucket_fill[bucket] < cap:
                bucket_fill[bucket] += 1
                return bucket
        return BUCKET_ORDER[-1]  # the final bucket is uncapped; unreachable in practice

    pending = sorted(plan_seeds, key=_seed_key)
    placed: dict[str, PlanSeed] = {}
    result: list[dict] = []

    # Multiple passes so a seed whose dependency appears later in urgency order still resolves
    # once that dependency is placed. Bounded by len(pending) — no unbounded loop.
    for _ in range(len(pending) + 1):
        if not pending:
            break
        still_pending = []
        progressed = False
        for seed in pending:
            unmet = [d for d in seed.depends_on if d in known_ids and d not in placed]
            if unmet:
                still_pending.append(seed)
                continue
            bucket = place(seed)
            scheduled_bucket[seed.id] = bucket
            placed[seed.id] = seed
            result.append(_as_item(seed, bucket))
            progressed = True
        pending = still_pending
        if not progressed:
            break

    # Any seeds left (a dependency cycle, or a dependency that never resolves) fail safe into the
    # final, uncapped bucket rather than being silently dropped (CLAUDE.md §6 pillar 16).
    for seed in pending:
        result.append(_as_item(seed, BUCKET_ORDER[-1]))

    return result


def _as_item(seed: PlanSeed, bucket: str) -> dict:
    return {
        "id": seed.id,
        "pillar": seed.pillar,
        "title_key": seed.title_key,
        "rationale_key": seed.rationale_key,
        "priority": seed.urgency,
        "effort_size": seed.effort_size,
        "depends_on_item_ids": list(seed.depends_on),
        "timeframe_bucket": bucket,
        "resolves_signal": seed.resolves_signal,
    }
