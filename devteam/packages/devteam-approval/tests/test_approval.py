"""The Approval Domain (S5) — the aggregate's event-sourced lifecycle, the Store, the Service.

These lock the owner's refinements: the decision is a separate object appended to an event log; the
request binds to a generic ``target_ref`` (not a problem); the lifecycle has CANCELLED so no gate
hangs; and the Store is pure persistence while all logic lives in ``ApprovalService``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from devteam_approval import (
    Actor,
    ApprovalDecision,
    ApprovalError,
    ApprovalOutcome,
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalService,
    ApprovalStatus,
    FileApprovalStore,
    InMemoryApprovalStore,
)

_ALICE = Actor(actor_id="alice", name="Alice", role="ceo")
_BOB = Actor(actor_id="bob", name="Bob", role="policy_owner")


class _Clock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def _counter() -> Callable[[], str]:
    box = {"n": 0}

    def _next() -> str:
        box["n"] += 1
        return str(box["n"])

    return _next


def _request(**kw: object) -> ApprovalRequest:
    base: dict[str, object] = {
        "target_ref": "mission:m1",  # a generic resumable target, not a problem
        "resume_token": "tok-1",
        "policy": ApprovalPolicy(requirement="standard", required_role="ceo", reason="prod merge"),
    }
    base.update(kw)
    return ApprovalRequest(**base)  # type: ignore[arg-type]


def _service(now: float = 1000.0) -> ApprovalService:
    return ApprovalService(new_id=_counter(), clock=_Clock(now))


# --- the aggregate: an event-sourced lifecycle over an immutable value ---


def test_decide_appends_to_the_log_and_current_decision_derives_from_it() -> None:
    request = _request()
    decision = ApprovalDecision(ApprovalOutcome.GRANTED, actor=_ALICE, comment="ok", at=1234.0)
    granted = request.decide(decision)
    assert granted.status is ApprovalStatus.GRANTED
    assert granted.decisions == (decision,)  # the decision is an event in the append-only log
    assert granted.current_decision is decision  # current state derives from the log
    assert granted.current_decision.actor.role == "ceo"  # full audit identity travels with it
    assert request.status is ApprovalStatus.PENDING and request.decisions == ()  # unchanged


def test_reject_expire_and_cancel_reach_their_states() -> None:
    rejected = _request().decide(ApprovalDecision(ApprovalOutcome.REJECTED, actor=_BOB))
    assert rejected.status is ApprovalStatus.REJECTED and rejected.current_decision is not None
    assert _request().expire().status is ApprovalStatus.EXPIRED  # no decision, just a status
    cancelled = _request().cancel()
    assert cancelled.status is ApprovalStatus.CANCELLED and cancelled.current_decision is None


def test_a_terminal_request_cannot_transition_again() -> None:
    granted = _request().decide(ApprovalDecision(ApprovalOutcome.GRANTED, actor=_ALICE))
    actions: tuple[Callable[[], ApprovalRequest], ...] = (
        lambda: granted.decide(ApprovalDecision(ApprovalOutcome.REJECTED, actor=_BOB)),
        granted.expire,
        granted.cancel,
    )
    for action in actions:
        with pytest.raises(ApprovalError):
            action()


def test_is_expired_only_when_pending_and_past_the_deadline() -> None:
    request = _request(expires_at=2000.0)
    assert request.is_expired(now=1999.0) is False
    assert request.is_expired(now=2000.0) is True
    assert _request(expires_at=0.0).is_expired(now=9e9) is False  # 0.0 = never expires
    assert request.cancel().is_expired(now=9e9) is False  # terminal never "expires"


# --- the Store: pure persistence, no logic ---


def test_store_is_persistence_only() -> None:
    store = InMemoryApprovalStore()
    request = _request()
    store.save(request)
    assert store.load(request.id) is request
    assert store.list() == (request,)
    store.delete(request.id)
    assert store.load(request.id) is None and store.list() == ()


# --- the Service: all logic, deterministic ids + clock ---


def test_service_create_approve_and_pending() -> None:
    service = _service(now=1000.0)
    request = service.create(
        target_ref="mission:m1",
        resume_token="tok-1",
        policy=ApprovalPolicy(requirement="executive", required_role="ceo"),
    )
    assert request.id == "apr_1" and request.is_pending
    assert service.pending_for_target("mission:m1") is request

    decided = service.approve(request.id, actor=_ALICE, comment="ship it")
    assert decided.status is ApprovalStatus.GRANTED
    assert decided.current_decision is not None
    assert decided.current_decision.actor == _ALICE and decided.current_decision.at == 1000.0
    assert service.pending() == ()  # no longer pending


def test_service_cancel_for_target_prevents_a_hanging_gate() -> None:
    service = ApprovalService(new_id=_counter())
    service.create(target_ref="problem:x", resume_token="t", policy=ApprovalPolicy("standard"))
    cancelled = service.cancel_for_target("problem:x")  # the target closed before a decision
    assert cancelled is not None and cancelled.status is ApprovalStatus.CANCELLED
    assert service.cancel_for_target("problem:x") is None  # nothing pending now


def test_service_expire_due_expires_only_overdue_pending() -> None:
    clock = _Clock(1000.0)
    service = ApprovalService(new_id=_counter(), clock=clock)
    overdue = service.create(
        target_ref="a", resume_token="t", policy=ApprovalPolicy("s"), expires_at=1500.0
    )
    service.create(target_ref="b", resume_token="t", policy=ApprovalPolicy("s"), expires_at=9000.0)
    clock.now = 1600.0

    expired = service.expire_due()
    assert [r.id for r in expired] == [overdue.id]  # only the overdue one
    assert {r.status for r in service.pending()} == {ApprovalStatus.PENDING}  # the other stays


def test_service_raises_for_an_unknown_request() -> None:
    with pytest.raises(ApprovalError):
        ApprovalService().approve("nope", actor=_ALICE)


# --- the durable file store: cross-process persistence, round-trips the full aggregate ---


def test_file_store_round_trips_requests_and_decisions(tmp_path: Path) -> None:
    path = tmp_path / "approvals.json"
    service = ApprovalService(FileApprovalStore(path), new_id=_counter(), clock=_Clock(1000.0))
    request = service.create(
        target_ref="problem:web", resume_token="tok", policy=ApprovalPolicy("standard", "ceo", "x")
    )
    service.approve(request.id, actor=_ALICE, comment="ship")

    reloaded = ApprovalService(FileApprovalStore(path))  # a fresh process reading the same file
    decided = reloaded.get(request.id)
    assert decided is not None and decided.status is ApprovalStatus.GRANTED
    assert decided.policy.required_role == "ceo"
    assert decided.current_decision is not None and decided.current_decision.actor == _ALICE


def test_file_store_delete_and_missing_file_are_safe(tmp_path: Path) -> None:
    path = tmp_path / "approvals.json"
    store = FileApprovalStore(path)
    assert store.list() == () and store.load("nope") is None  # missing file → empty, never raises
    request = _request()
    store.save(request)
    assert store.load(request.id) is not None
    store.delete(request.id)
    assert store.list() == ()
