"""Adapters — translate external systems into generic lifecycle events (ADR 0065, S4b-2 rules).

An adapter's ONLY job is ``External → Generic Event`` (rule 5): it never touches lifecycle state —
the ``LifecycleCoordinator`` is the single owner of state. Adapters are hot-swappable via registry,
not an ``if/else`` (rule 1): a new source (GitLab, Jenkins, a local runner) is a new registration.
Each adapter stamps its drained events with its own ``source`` (rule 4) so the audit names the
concrete emitter, not just the trigger class. A failing adapter is contained (rule 3): the tick
still reconciles, so a lost or broken source never makes the system incorrect.
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from devteam_organization.lifecycle.coordinator import LifecycleEvent, Trigger

_LOG = logging.getLogger("devteam.organization.lifecycle.adapters")


@runtime_checkable
class Adapter(Protocol):
    """A source of generic lifecycle events. ``drain`` returns the events buffered since the last
    call (webhooks, polling, a queue), stamped with this adapter's trigger + source. It NEVER
    advances the coordinator or mutates state — only produces events (rule 5). ``id`` / ``trigger``
    are read-only so a frozen adapter satisfies the protocol."""

    @property
    def id(self) -> str: ...

    @property
    def trigger(self) -> Trigger: ...

    def drain(self) -> list[LifecycleEvent]: ...


class AdapterRegistry:
    """The registered adapters (rule 1 — hot-swappable, no if/else). ``drain_all`` collects every
    adapter's pending events for the daemon to feed the coordinator; a failing adapter is contained
    so one bad source cannot stall the others (rule 3 — the tick still reconciles)."""

    def __init__(self) -> None:
        self._adapters: dict[str, Adapter] = {}

    def register(self, adapter: Adapter) -> None:
        self._adapters[adapter.id] = adapter

    def get(self, adapter_id: str) -> Adapter | None:
        return self._adapters.get(adapter_id)

    def adapters(self) -> tuple[Adapter, ...]:
        return tuple(self._adapters.values())

    def drain_all(self) -> list[LifecycleEvent]:
        """Every adapter's pending events, in registration order. A drain that raises is logged and
        skipped — the tick reconciles regardless (rule 3)."""
        events: list[LifecycleEvent] = []
        for adapter in self._adapters.values():
            try:
                events.extend(adapter.drain())
            except Exception:  # a bad adapter must not stall the others
                _LOG.exception("adapter %s drain failed", adapter.id)
        return events
