from governance_discovery.plan import GovernancePlan, PlanItem


def _item(**overrides) -> PlanItem:
    base = PlanItem(
        id="item_1",
        plan_id="plan_1",
        tenant_id="tenant_a",
        pillar="risk",
        title="Establish a risk register",
        objective="A living record of operational risks",
        expected_outcome="Risks are tracked and reviewed regularly",
        rationale="No risk register was found",
        timeframe_bucket="week_1",
        priority="high",
        effort_size="small",
        depends_on_item_ids=(),
        status="not_started",
        source_signal_keys=("risk_register_state",),
        source_framework_refs=(),
        created_at=1000.0,
        updated_at=1000.0,
        resolves_signal={"signal": "risk_register_state", "value": "approved"},
    )
    return base if not overrides else base.__class__(**{**base.__dict__, **overrides})


def test_marked_done_sets_status_and_completed_at() -> None:
    item = _item()
    done = item.marked_done(now=2000.0)
    assert done.status == "done"
    assert done.completed_at == 2000.0
    assert done.updated_at == 2000.0
    assert item.status == "not_started"  # original unchanged (frozen dataclass)


def test_reopened_clears_completed_at() -> None:
    item = _item().marked_done(now=2000.0)
    reopened = item.reopened(now=3000.0)
    assert reopened.status == "not_started"
    assert reopened.completed_at is None
    assert reopened.updated_at == 3000.0


def test_evidence_backed_reflects_whether_evidence_is_attached() -> None:
    item = _item()
    assert not item.is_evidence_backed
    with_evidence = item.with_evidence(("ev_1",), now=1500.0)
    assert with_evidence.is_evidence_backed
    assert with_evidence.updated_at == 1500.0


def test_evidence_is_never_required_to_mark_done() -> None:
    item = _item()
    done = item.marked_done(now=2000.0)  # no evidence attached at all
    assert done.status == "done"


def test_plan_superseded_by_next_version_stamps_maturity_snapshot() -> None:
    plan = GovernancePlan(
        id="plan_1",
        tenant_id="tenant_a",
        source_mission_id="mission_1",
        status="active",
        version=1,
        inferred_frameworks=(),
        maturity_baseline={"governance": {"score": 2, "stars": 1, "label": "limited"}},
        created_at=1000.0,
        updated_at=1000.0,
    )
    current = {"governance": {"score": 8, "stars": 4, "label": "established"}}
    superseded = plan.superseded_by_next_version(current, now=5000.0)
    assert superseded.status == "superseded"
    assert superseded.maturity_at_supersession == current
    assert superseded.maturity_baseline == plan.maturity_baseline  # baseline never changes
    assert plan.status == "active"  # original unchanged
