"""`MissionRuntime` — the composition root for the mission end-to-end path (Integration only).

This wires the *frozen* components into the single flow the integration diagram describes, with no
change to any of them, no new port, and no new feature:

    Mission Engine → Mission Store → Unit of Work → Transactional Outbox
                   → Outbox Relay → Delivery Bus → Audit Sink

The runtime owns only the **wiring**, in two halves that the Transactional Outbox pattern keeps
deliberately separate:

- **Capture half** (`run_transition`) — one engine transition runs inside one `UnitOfWork`. The
  `PostgresMissionStore` and the `OutboxSink` are both bound to `uow.connection`, and the engine
  emits onto a synchronous **Capture Bus** whose only subscriber is that sink. So the mission's
  state change (`save`) and its domain events (outbox rows) commit **atomically** — no dual write
  (ADR 0043-S4 I1/I2). Per Rev.3 the capture is **per-transition**: one transition, one transaction.

- **Delivery half** (`relay`) — the `OutboxRelay` later drains committed-but-unpublished rows, in
  insertion order, onto the **Delivery Bus** (a *different* `EventBus`, outside any write
  transaction) via a `DeliveryBusPublisher`. The Delivery Bus's subscriber is the `MissionAuditSink`
  — the audit terminal. At-least-once: a lost mark re-publishes on the next drain (I6).

Every object composed here is frozen; the runtime adds no behaviour beyond assembly, so it is safe
to sit outside the frozen packages. The psycopg driver is imported lazily (inside the DB-touching
methods), matching the store and relay, so this module imports with or without the driver present.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from event_bus import ALL_EVENTS, InProcessEventBus
from event_bus.bus import EventBus
from mission_engine import EchoExecutor, MissionEngine, MissionStatus
from mission_engine.ports import ExecutionPort
from mission_store import (
    DeliveryBusPublisher,
    OutboxRelay,
    OutboxSink,
    PostgresMissionStore,
    UnitOfWork,
)
from mission_store.config import TABLE
from mission_store.config import dsn as default_dsn
from mission_store.outbox_schema import OUTBOX_TABLE

from mission_integration.audit import MissionAuditSink

if TYPE_CHECKING:  # type-only; the driver is never needed to import this module
    from collections.abc import Callable

    from mission_engine import Mission
    from pipeline_contracts import TenantContext

T = TypeVar("T")

_MISSING_PG = (
    "MissionRuntime needs the 'psycopg' package for its end-to-end DB path. "
    "Install the optional extra: mission-integration[postgres]"
)


def _connect(dsn: str, *, autocommit: bool) -> Any:
    """Open a psycopg connection, importing the driver lazily so the module loads without it."""
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - exercised only without the extra installed
        raise ImportError(_MISSING_PG) from exc
    return psycopg.connect(dsn, autocommit=autocommit)


class MissionRuntime:
    """The end-to-end wiring. Construct once; drive each engine transition through `run_transition`,
    then `relay` to deliver the committed events onto the Delivery Bus and into the Audit Sink.

    Nothing here is a store, a repository, or a service locator — it is assembly. The Delivery Bus
    and Audit Sink are created and connected on construction (unless injected), and the capture-side
    objects (connection, UoW, store, sink, capture bus, engine) are built fresh **per transition**,
    exactly as the outbox pattern requires (Rev.3, per-transition capture).
    """

    def __init__(
        self,
        *,
        dsn: str | None = None,
        missions_table: str = TABLE,
        outbox_table: str = OUTBOX_TABLE,
        executor: ExecutionPort | None = None,
        delivery_bus: EventBus | None = None,
        audit_sink: MissionAuditSink | None = None,
    ) -> None:
        self._dsn = dsn or default_dsn()
        self._missions_table = missions_table
        self._outbox_table = outbox_table
        self._executor: ExecutionPort = executor or EchoExecutor()
        self._audit = audit_sink or MissionAuditSink()
        if delivery_bus is None:
            # The Delivery Bus carries the real downstream consumers; here that is the Audit Sink.
            # Subscribe it to every event type so it is the faithful audit terminal of the path.
            delivery_bus = InProcessEventBus()
            delivery_bus.subscribe(ALL_EVENTS, self._audit.record)
        self._delivery_bus = delivery_bus

    # --- exposed collaborators ----------------------------------------------------------

    @property
    def audit(self) -> MissionAuditSink:
        """The Audit Sink terminal — the recorded, delivered event stream."""
        return self._audit

    @property
    def delivery_bus(self) -> EventBus:
        """The Delivery Bus the relay publishes onto (outside any write transaction)."""
        return self._delivery_bus

    # --- capture half: one transition, one atomic transaction ---------------------------

    def run_transition(self, apply: Callable[[MissionEngine], T]) -> T:
        """Drive ONE engine transition inside its own `UnitOfWork` and return `apply`'s result.

        The store and the `OutboxSink` share `uow.connection`, and the engine emits onto a
        synchronous Capture Bus the sink subscribes to — so the mission `save` and its events land
        in the same transaction and commit together on clean exit (or roll back together on any
        exception, including a store `IdempotencyConflict` or a failed event write). `apply` gets
        the fully-wired engine; e.g. `run_transition(lambda e: e.run_simple(goal, tenant, instr))`
        or `run_transition(lambda e: e.plan(mission, plan))`.
        """
        writer = _connect(self._dsn, autocommit=False)
        try:
            with UnitOfWork(connection=writer) as uow:
                store = PostgresMissionStore(
                    connection=uow.connection, table=self._missions_table
                )
                capture_bus = InProcessEventBus()  # synchronous; the sink must NOT be isolated (I4)
                sink = OutboxSink(connection=uow.connection, table=self._outbox_table)
                capture_bus.subscribe(ALL_EVENTS, sink.write)
                engine = MissionEngine(store, self._executor, events=capture_bus)
                return apply(engine)
        finally:
            writer.close()

    # --- delivery half: drain committed rows onto the Delivery Bus → Audit Sink ---------

    def relay(self, *, limit: int = 100) -> int:
        """Drain committed-but-unpublished outbox rows onto the Delivery Bus (and thus the Audit
        Sink), in insertion order, marking each published. Returns the count delivered. Idempotent
        once published; at-least-once if a mark is lost (I6). Opens its own autocommit connection
        (the relay's owned mode) and closes it — the delivery side is outside any write transaction.
        """
        relay = OutboxRelay(dsn=self._dsn, table=self._outbox_table)
        try:
            return relay.drain(DeliveryBusPublisher(self._delivery_bus), limit=limit)
        finally:
            relay.close()

    # --- reads --------------------------------------------------------------------------

    def load(self, mission_id: str, tenant: TenantContext) -> Mission | None:
        """Reload a mission from the durable store within the caller's tenant scope — the seam a
        *resume* uses to reconstruct mission state after a process boundary. Returns `None` if no
        such mission exists for this tenant (cross-tenant reads cannot happen; enforced in SQL)."""
        reader = _connect(self._dsn, autocommit=True)
        try:
            store = PostgresMissionStore(connection=reader, table=self._missions_table)
            return store.get(mission_id, tenant)
        finally:
            reader.close()

    # --- resume orchestration (ADR 0044 Slice 3) ----------------------------------------

    def approve(
        self, mission_id: str, approver: TenantContext, *, comment: str = ""
    ) -> Mission | None:
        """Reload a paused mission and apply a human approval in its own transaction (→ RESUMED),
        so `MissionApproved` is captured atomically into the outbox. Returns the approved mission,
        or `None` if it does not exist for this tenant. This is *not* resume — call
        `resume_if_approved` to continue execution."""
        mission = self.load(mission_id, approver)
        if mission is None:
            return None
        return self.run_transition(
            lambda engine: engine.approve(mission, approver, comment=comment)
        )

    def reject(
        self, mission_id: str, approver: TenantContext, *, comment: str = ""
    ) -> Mission | None:
        """Reload a paused mission and apply a human rejection in its own transaction (→ CANCELLED,
        fail-safe), so `MissionRejected` is captured atomically into the outbox."""
        mission = self.load(mission_id, approver)
        if mission is None:
            return None
        return self.run_transition(lambda engine: engine.reject(mission, approver, comment=comment))

    def resume_if_approved(self, mission_id: str, tenant: TenantContext) -> Mission | None:
        """The resume-orchestration entry point (ADR 0044 Slice 3): **detect** that a mission was
        approved (its persisted status is `RESUMED`), **reload** it from the store, and **re-enter**
        it into the Mission Engine to **continue execution** from the pause point — all in one
        transaction whose events (`MissionResumed`, the gated step, `MissionCompleted` or the next
        gate) are captured to the outbox exactly like any other transition.

        No scheduler, queue, or polling: the caller names the mission. A mission that is not
        `RESUMED` is returned unchanged (nothing to resume); `None` if it does not exist."""
        mission = self.load(mission_id, tenant)
        if mission is None:
            return None
        if mission.status is not MissionStatus.RESUMED:
            return mission  # not approved / not resumable — a deliberate no-op
        return self.run_transition(lambda engine: engine.resume(mission))
