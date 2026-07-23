"""Rasheed V2 **Mission Integration** — the composition root that runs the frozen Mission Store
slices (1–4) as one system, end to end. **Integration & verification only**: it adds no feature,
starts no new slice, and changes no frozen component (no ADR, port, engine, or `EventBus` change).

It owns only the *wiring* of the path

    Mission Engine → Mission Store → Unit of Work → Transactional Outbox
                   → Outbox Relay → Delivery Bus → Audit Sink

- `MissionRuntime` (composition root): a per-transition capture half (`run_transition`) where the
  store and `OutboxSink` share one `UnitOfWork` connection so state and events commit atomically,
  and a delivery half (`relay`) where the `OutboxRelay` drains committed rows onto a Delivery Bus.
- `MissionAuditSink` (glue): the Delivery Bus's terminal subscriber, recording the delivered event
  stream so an end-to-end run can prove the committed, published events reached audit.
"""

from mission_integration.audit import MissionAuditSink
from mission_integration.runtime import MissionRuntime

__all__ = [
    "MissionRuntime",
    "MissionAuditSink",
]
