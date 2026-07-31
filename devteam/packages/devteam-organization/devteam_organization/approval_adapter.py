"""The Approval → Lifecycle adapter — a translation layer, nothing more (S5 Phase 2).

A decided ``ApprovalRequest`` becomes a generic ``LifecycleEvent`` that flows through
``LifecycleCoordinator.notify`` — exactly the seam the Core was frozen with. The adapter makes **no
lifecycle decision**: whether to resume, escalate, or close is the Coordinator's; the adapter only
maps a status to an event kind.

Mapping (the only knowledge here):

* ``GRANTED``   → ``APPROVAL_GRANTED`` (trigger HUMAN — a person decided)
* ``REJECTED``  → ``APPROVAL_REJECTED`` (trigger HUMAN)
* ``EXPIRED``   → ``APPROVAL_REJECTED`` (trigger TIMER, detail "expired") — expiry *is* a reject, so
  the Core needs no new event kind and stays frozen
* ``CANCELLED`` → no event — a cancel is internal to the Approval Domain and must never wake the
  lifecycle
* ``PENDING``   → no event — nothing has been decided yet

The event's ``correlation_ref`` is the request's ``target_ref`` (the problem it gates) and its
``event_id`` is the decision id (or ``<request>:expired``), so ``notify`` stays idempotent — a
re-dispatched decision is ignored, a late decision on a closed problem is dropped.
"""

from __future__ import annotations

from devteam_approval import ApprovalRequest, ApprovalService, ApprovalStatus

from devteam_organization.lifecycle import (
    LifecycleCoordinator,
    LifecycleEvent,
    LifecycleEventKind,
    LifecycleOutcome,
    Trigger,
)

_EVENT_KIND: dict[ApprovalStatus, LifecycleEventKind] = {
    ApprovalStatus.GRANTED: LifecycleEventKind.APPROVAL_GRANTED,
    ApprovalStatus.REJECTED: LifecycleEventKind.APPROVAL_REJECTED,
    ApprovalStatus.EXPIRED: LifecycleEventKind.APPROVAL_REJECTED,  # expiry = reject("expired")
}


def approval_event(request: ApprovalRequest) -> LifecycleEvent | None:
    """The one pure translation: the generic ``LifecycleEvent`` a decided request implies, or None
    for PENDING/CANCELLED (a cancel is internal and must never wake the lifecycle). ``event_id`` is
    the decision id (or ``<request>:expired``) so ``notify`` stays idempotent."""
    kind = _EVENT_KIND.get(request.status)
    if kind is None:
        return None
    decision = request.current_decision
    event_id = decision.id if decision is not None else f"{request.id}:expired"
    trigger = Trigger.HUMAN if decision is not None else Trigger.TIMER
    detail = "expired" if request.status is ApprovalStatus.EXPIRED else ""
    return LifecycleEvent(
        kind=kind,
        event_id=event_id,
        correlation_ref=request.target_ref,
        trigger=trigger,
        source="approval",
        detail=detail,
    )


class ApprovalLifecycleAdapter:
    """Translates a decided ``ApprovalRequest`` into a ``LifecycleEvent`` and notifies the
    coordinator. Holds no state and takes no lifecycle decision."""

    def __init__(self, coordinator: LifecycleCoordinator) -> None:
        self._coordinator = coordinator

    def to_event(self, request: ApprovalRequest) -> LifecycleEvent | None:
        return approval_event(request)

    def dispatch(self, request: ApprovalRequest) -> LifecycleOutcome | None:
        """Translate + notify. Returns the coordinator's outcome, or None when there is nothing to
        notify (PENDING/CANCELLED) or the coordinator ignored it (duplicate / closed target)."""
        event = self.to_event(request)
        if event is None:
            return None
        return self._coordinator.notify(event)


class ApprovalDecisionAdapter:
    """The frozen ``Adapter`` (rule 5: External → Generic Event; never touches state). Each drain
    reads the shared store and yields the events for decisions not yet emitted this process. The
    coordinator's own ``event_id`` dedup + the reconciling tick cover restarts and lost drains, so a
    decision is applied exactly once even though the store is polled every pass."""

    def __init__(self, service: ApprovalService) -> None:
        self._service = service
        self._emitted: set[str] = set()

    @property
    def id(self) -> str:
        return "approval"

    @property
    def trigger(self) -> Trigger:
        return Trigger.HUMAN

    def drain(self) -> list[LifecycleEvent]:
        events: list[LifecycleEvent] = []
        for request in self._service.all():
            event = approval_event(request)
            if event is None or event.event_id in self._emitted:
                continue
            self._emitted.add(event.event_id)
            events.append(event)
        return events
