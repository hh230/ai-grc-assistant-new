from governance_discovery.capacity import compute_capacity
from governance_discovery.pack import PlanSeed
from governance_discovery.scheduler import BUCKET_ORDER, schedule

from tests.helpers import make_signals


def _seed(
    id_: str, urgency: str = "high", effort: str = "medium", depends_on: tuple = ()
) -> PlanSeed:
    return PlanSeed(
        id=id_,
        pillar="organization",
        title_key=f"{id_}.title",
        rationale_key=f"{id_}.rationale",
        urgency=urgency,
        effort_size=effort,
        depends_on=depends_on,
    )


def test_dependency_is_never_scheduled_before_what_it_depends_on() -> None:
    seeds = [_seed("a"), _seed("b", depends_on=("a",))]
    # ample capacity, not the constraint here
    capacity = compute_capacity(make_signals(employee_count=3000))
    items = schedule(seeds, capacity)
    by_id = {item["id"]: item for item in items}
    a_index = BUCKET_ORDER.index(by_id["a"]["timeframe_bucket"])
    b_index = BUCKET_ORDER.index(by_id["b"]["timeframe_bucket"])
    assert b_index >= a_index


def test_small_org_gets_far_fewer_items_per_period_than_an_enterprise() -> None:
    """The concrete case the owner flagged: a 3-person firm cannot absorb 18 tasks in a week, a
    3,000-person enterprise can absorb far more (ADR 0066 §2.5)."""
    seeds = [_seed(f"item_{i}", urgency="critical") for i in range(20)]

    micro_capacity = compute_capacity(make_signals(employee_count=3))
    enterprise_capacity = compute_capacity(
        make_signals(
            employee_count=3000,
            has_legal_team=True,
            has_it_team=True,
            has_compliance_officer=True,
            execution_capacity="dedicated_team_and_budget",
        )
    )
    assert micro_capacity["tier"] == "micro"
    assert enterprise_capacity["tier"] == "enterprise"

    micro_items = schedule(seeds, micro_capacity)
    enterprise_items = schedule(seeds, enterprise_capacity)

    micro_week1 = sum(1 for item in micro_items if item["timeframe_bucket"] == "week_1")
    enterprise_week1 = sum(1 for item in enterprise_items if item["timeframe_bucket"] == "week_1")

    assert micro_week1 == micro_capacity["per_period_budget"]["week_1"]
    assert enterprise_week1 == enterprise_capacity["per_period_budget"]["week_1"]
    assert enterprise_week1 > micro_week1
    assert micro_week1 <= 3  # never an unexecutable week for a 3-person firm


def test_overflow_beyond_month_6_lands_in_year_1_not_dropped() -> None:
    seeds = [_seed(f"item_{i}", urgency="low") for i in range(50)]
    capacity = compute_capacity(make_signals(employee_count=3))  # micro: small per-period budget
    items = schedule(seeds, capacity)
    assert len(items) == 50  # nothing silently dropped (CLAUDE.md §6 pillar 16)
    assert any(item["timeframe_bucket"] == "year_1" for item in items)


def test_urgency_fills_buckets_before_lower_urgency_items() -> None:
    seeds = [
        _seed("critical_a", urgency="critical"),
        _seed("critical_b", urgency="critical"),
        _seed("low_item", urgency="low"),
    ]
    # micro: week_1 budget = 2, exactly full
    capacity = compute_capacity(make_signals(employee_count=3))
    items = schedule(seeds, capacity)
    by_id = {item["id"]: item for item in items}
    assert by_id["critical_a"]["timeframe_bucket"] == "week_1"
    assert by_id["critical_b"]["timeframe_bucket"] == "week_1"
    assert by_id["low_item"]["timeframe_bucket"] != "week_1"  # bumped out by higher-urgency items
