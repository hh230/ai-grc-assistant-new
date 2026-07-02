"""Aggregate tracking contract.

Every aggregate a repository loads, adds, or saves is *tracked* with the Unit of Work so
that, at commit time, the domain events the aggregates recorded can be collected and
handed to the transactional outbox. This is how the persistence layer turns recorded
domain events into integration events atomically with the state change that produced them.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from grc_domain.shared.entity import AggregateRoot


@runtime_checkable
class AggregateTracker(Protocol):
    """Anything that can register a touched aggregate root for event collection."""

    def track(self, aggregate: AggregateRoot) -> None: ...
