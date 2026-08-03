import pytest
from governance_discovery.engine import DiscoveryEngine
from governance_discovery.pack import load_bundled_packs
from governance_discovery.plan import PlanItem
from governance_discovery.signal import Signal, SignalSet, ValueType

from governance_plan_execution.errors import PlanItemConflict, PlanItemNotFound
from governance_plan_execution.service import PlanExecutionService
from tests.fake_store import FakePlanExecutionStore


def _service() -> tuple[PlanExecutionService, FakePlanExecutionStore]:
    counter = {"id": 0, "clock": 1000.0}

    def new_id() -> str:
        counter["id"] += 1
        return f"id_{counter['id']}"

    def now() -> float:
        counter["clock"] += 1.0
        return counter["clock"]

    store = FakePlanExecutionStore()
    engine = DiscoveryEngine(load_bundled_packs())
    return PlanExecutionService(engine, store, new_id=new_id, now=now), store


def _item(**overrides) -> PlanItem:
    base = PlanItem(
        id="item_1",
        plan_id="plan_1",
        tenant_id="tenant_a",
        pillar="risk",
        title="Establish a risk register",
        objective="Track operational risks",
        expected_outcome="Risks reviewed regularly",
        rationale="No risk register found",
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


def test_start_sets_in_progress_and_records_an_event() -> None:
    service, store = _service()
    store.seed_item(_item())
    started = service.start("item_1", "tenant_a", actor_id="user_1")
    assert started.status == "in_progress"
    assert started.completed_at is None
    assert store.events[-1]["event_type"] == "started"


def test_start_is_a_no_op_once_already_in_progress_or_done() -> None:
    service, store = _service()
    store.seed_item(_item())
    first = service.start("item_1", "tenant_a", actor_id="user_1")
    second = service.start("item_1", "tenant_a", actor_id="user_1")
    assert first.updated_at == second.updated_at
    assert len([e for e in store.events if e["event_type"] == "started"]) == 1

    service.mark_done("item_1", "tenant_a", actor_id="user_1")
    after_done = service.start("item_1", "tenant_a", actor_id="user_1")
    assert after_done.status == "done"  # starting a completed item is a no-op, not a regression


def test_mark_done_works_directly_from_not_started_without_an_explicit_start() -> None:
    """Jumping straight to done without ever calling `start` is a real, allowed workflow."""
    service, store = _service()
    store.seed_item(_item())
    done = service.mark_done("item_1", "tenant_a", actor_id="user_1")
    assert done.status == "done"


def test_mark_done_sets_status_and_records_an_event() -> None:
    service, store = _service()
    store.seed_item(_item())
    done = service.mark_done("item_1", "tenant_a", actor_id="user_1")
    assert done.status == "done"
    assert done.completed_at is not None
    assert store.events[-1]["event_type"] == "completed"


def test_mark_done_never_requires_evidence() -> None:
    service, store = _service()
    store.seed_item(_item())
    done = service.mark_done("item_1", "tenant_a", actor_id="user_1")
    assert done.status == "done"
    assert not done.is_evidence_backed


def test_mark_done_is_idempotent() -> None:
    service, store = _service()
    store.seed_item(_item())
    first = service.mark_done("item_1", "tenant_a", actor_id="user_1")
    second = service.mark_done("item_1", "tenant_a", actor_id="user_1")
    assert first.completed_at == second.completed_at  # no second event/re-stamp
    assert len([e for e in store.events if e["event_type"] == "completed"]) == 1


def test_reopen_clears_completion_and_records_an_event() -> None:
    service, store = _service()
    store.seed_item(_item())
    service.mark_done("item_1", "tenant_a", actor_id="user_1")
    reopened = service.reopen("item_1", "tenant_a", actor_id="user_1")
    assert reopened.status == "not_started"
    assert reopened.completed_at is None
    assert store.events[-1]["event_type"] == "reopened"


def test_attach_evidence_marks_it_evidence_backed() -> None:
    service, store = _service()
    store.seed_item(_item())
    updated = service.attach_evidence("item_1", "tenant_a", ("ev_1",), actor_id="user_1")
    assert updated.is_evidence_backed
    assert store.events[-1]["event_type"] == "evidence_attached"


def test_unknown_item_raises() -> None:
    service, _ = _service()
    with pytest.raises(PlanItemNotFound):
        service.mark_done("does-not-exist", "tenant_a", actor_id="user_1")


class _AlwaysLosesTheRaceStore(FakePlanExecutionStore):
    """A store whose `record_item_transition` always reports "someone else wrote first" — proves
    `PlanExecutionService` translates that refusal into `PlanItemConflict`, rather than swallowing
    it or reporting success (Phase 3 hardening)."""

    def record_item_transition(self, item, **kwargs) -> bool:  # noqa: ANN001
        return False


def test_a_lost_optimistic_lock_raises_plan_item_conflict() -> None:
    store = _AlwaysLosesTheRaceStore()
    store.seed_item(_item())
    engine = DiscoveryEngine(load_bundled_packs())
    service = PlanExecutionService(engine, store, new_id=lambda: "id_1", now=lambda: 2000.0)

    with pytest.raises(PlanItemConflict):
        service.mark_done("item_1", "tenant_a", actor_id="user_1")
    with pytest.raises(PlanItemConflict):
        service.attach_evidence("item_1", "tenant_a", ("ev_1",), actor_id="user_1")


def test_current_maturity_is_none_without_a_baseline() -> None:
    service, _ = _service()
    result = service.current_maturity("tenant_with_no_discovery")
    assert result.maturity is None


def test_current_maturity_reflects_a_completed_item_and_reverts_on_reopen() -> None:
    service, store = _service()
    baseline = SignalSet().with_signal(
        Signal(key="risk_register_state", value_type=ValueType.ENUM, value="absent")
    )
    store.seed_baseline("tenant_a", baseline, ("pack:core",))
    store.seed_item(_item())

    before = service.current_maturity("tenant_a")
    assert before.maturity is not None
    risk_before = before.maturity["risk"]["score"]

    service.mark_done("item_1", "tenant_a", actor_id="user_1")
    after = service.current_maturity("tenant_a")
    assert after.maturity["risk"]["score"] > risk_before

    service.reopen("item_1", "tenant_a", actor_id="user_1")
    reverted = service.current_maturity("tenant_a")
    assert reverted.maturity["risk"]["score"] == risk_before
