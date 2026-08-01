"""S6 acceptance for the Approval Queue Projection — "What decisions are waiting for me?".

Pins the projection on real awaiting-approval missions (driven through the engine) + the in-memory
read model, no HTTP: one Decision per waiting approval with the proposed action, mission context,
waiting-since, evidence count, and the reference to act on; longest-waiting first; tenant isolation;
and the fail-safe skip when a read-model snapshot says "awaiting" but the live mission does not.
"""

from __future__ import annotations

from typing import Any

from mission_application import ApprovalQueueProjection
from mission_engine import InMemoryMissionStore, MissionEngine, Plan, PlanStep, StepResult
from mission_read_model import InMemoryMissionListReadModel, MissionListItem
from pipeline_contracts import TenantContext


def tenant(tenant_id: str) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id, principal_id="u", roles=("practitioner", "approver"), region="ksa"
    )


class _GatherExecutor:
    """Runs the non-consequential steps (with citations); the engine pauses before the gate."""

    def __init__(self, citations: tuple[str, ...]) -> None:
        self._citations = citations

    def execute(self, request: Any) -> StepResult:
        return StepResult(
            step_id=request.step_id, ok=True, output="gathered", citations=self._citations
        )


def _await(
    store: InMemoryMissionStore,
    read_model: InMemoryMissionListReadModel,
    *,
    tenant_id: str,
    scope: str,
    mtype: str = "gap_assessment",
    at: float,
    citations: tuple[str, ...] = ("doc-1", "doc-2"),
) -> str:
    """Drive a mission to AWAITING_APPROVAL at a consequential step; project it. Returns its id."""
    engine = MissionEngine(store, _GatherExecutor(citations), clock=lambda: at)
    ctx = TenantContext(tenant_id=tenant_id, principal_id="system")
    mission = engine.create(f"{mtype}: {scope}", ctx)
    engine.plan(
        mission,
        Plan(
            steps=(
                PlanStep(description="Gather evidence", instruction="do"),
                PlanStep(description="Publish findings", instruction="do", consequential=True),
            )
        ),
    )
    engine.execute(mission)  # → AWAITING_APPROVAL at "Publish findings"
    read_model.record(
        MissionListItem(
            mission.id, tenant_id, mtype, scope, mission.status.value,
            mission.created_at, mission.updated_at,
        )
    )
    return mission.id


# --- one waiting decision, fully populated ----------------------------------------------


def test_one_waiting_decision_carries_what_a_person_needs() -> None:
    store, rm = InMemoryMissionStore(), InMemoryMissionListReadModel()
    mid = _await(store, rm, tenant_id="T", scope="Vendor Acme", mtype="vendor_review", at=100.0)

    items = ApprovalQueueProjection(store, rm).execute(tenant("T"))
    assert len(items) == 1
    d = items[0]
    assert d.mission_id == mid
    assert d.proposed_action == "Publish findings"  # the human part of the Core reason
    assert d.mission_type == "vendor_review" and d.mission_scope == "Vendor Acme"
    assert d.waiting_since == 100.0
    assert d.evidence_count == 2  # doc-1, doc-2

    # decision_id is the live approval id — the reference Approve/Reject acts on
    stored = store.get(mid, tenant("T"))
    assert stored is not None
    assert d.decision_id == stored.approval.id


# --- tenant isolation -------------------------------------------------------------------


def test_queue_is_tenant_scoped() -> None:
    store, rm = InMemoryMissionStore(), InMemoryMissionListReadModel()
    _await(store, rm, tenant_id="T", scope="A", at=100.0)
    _await(store, rm, tenant_id="T2", scope="B", at=100.0)

    a = ApprovalQueueProjection(store, rm).execute(tenant("T"))
    b = ApprovalQueueProjection(store, rm).execute(tenant("T2"))
    assert [d.mission_scope for d in a] == ["A"]
    assert [d.mission_scope for d in b] == ["B"]


def test_unknown_tenant_sees_empty() -> None:
    store, rm = InMemoryMissionStore(), InMemoryMissionListReadModel()
    _await(store, rm, tenant_id="T", scope="A", at=100.0)
    assert ApprovalQueueProjection(store, rm).execute(tenant("nobody")) == ()


# --- ordering: longest-waiting first ----------------------------------------------------


def test_longest_waiting_decision_comes_first() -> None:
    store, rm = InMemoryMissionStore(), InMemoryMissionListReadModel()
    _await(store, rm, tenant_id="T", scope="Newer", at=300.0)
    _await(store, rm, tenant_id="T", scope="Older", at=100.0)  # waited longer → first

    order = [d.mission_scope for d in ApprovalQueueProjection(store, rm).execute(tenant("T"))]
    assert order == ["Older", "Newer"]


# --- recent decisions (shown when nothing is waiting) -----------------------------------


def _decide(
    store: InMemoryMissionStore,
    rm: InMemoryMissionListReadModel,
    mission_id: str,
    *,
    tenant_id: str,
    approved: bool,
    at: float,
    scope: str,
) -> None:
    """Approve (→ completed) or reject (→ cancelled) a waiting mission — the reused S2 path."""
    engine = MissionEngine(store, _GatherExecutor(()), clock=lambda: at)
    ctx = TenantContext(tenant_id=tenant_id, principal_id="approver")
    mission = store.get(mission_id, ctx)
    assert mission is not None
    if approved:
        engine.approve(mission, ctx)
        engine.resume(mission)
    else:
        engine.reject(mission, ctx)
    final = store.get(mission_id, ctx)
    assert final is not None
    rm.record(
        MissionListItem(
            final.id, tenant_id, "gap_assessment", scope, final.status.value,
            final.created_at, final.updated_at,
        )
    )


def test_recent_decisions_are_the_last_decided_newest_first() -> None:
    store, rm = InMemoryMissionStore(), InMemoryMissionListReadModel()
    a = _await(store, rm, tenant_id="T", scope="Alpha", at=100.0)
    _decide(store, rm, a, tenant_id="T", approved=True, at=200.0, scope="Alpha")
    b = _await(store, rm, tenant_id="T", scope="Beta", at=300.0)
    _decide(store, rm, b, tenant_id="T", approved=False, at=400.0, scope="Beta")

    recent = ApprovalQueueProjection(store, rm).recent_decisions(tenant("T"))
    # newest decided first: Beta rejected (400) then Alpha approved (200)
    assert [(d.proposed_action, d.approved) for d in recent] == [
        ("Publish findings", False),
        ("Publish findings", True),
    ]
    # and a decided mission is no longer in the waiting queue
    assert ApprovalQueueProjection(store, rm).execute(tenant("T")) == ()


def test_recent_decisions_are_tenant_scoped() -> None:
    store, rm = InMemoryMissionStore(), InMemoryMissionListReadModel()
    a = _await(store, rm, tenant_id="T", scope="Alpha", at=100.0)
    _decide(store, rm, a, tenant_id="T", approved=True, at=200.0, scope="Alpha")
    assert ApprovalQueueProjection(store, rm).recent_decisions(tenant("T2")) == ()


# --- fail-safe: a stale snapshot is not a decision --------------------------------------


def test_snapshot_without_a_live_approval_is_skipped() -> None:
    store, rm = InMemoryMissionStore(), InMemoryMissionListReadModel()
    _await(store, rm, tenant_id="T", scope="Real", at=100.0)
    # a read-model row claiming "awaiting" for a mission the store never had → not a decision
    rm.record(MissionListItem("ghost", "T", "gap_assessment", "Ghost", "awaiting_approval", 1, 2))

    scopes = {d.mission_scope for d in ApprovalQueueProjection(store, rm).execute(tenant("T"))}
    assert scopes == {"Real"}  # ghost skipped (store.get → None)
