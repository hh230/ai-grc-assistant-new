"""The `CapabilityCatalog` — the product-facing registry (ADR 0046 §4).

A plain, in-memory registry of `Capability` records keyed by id. **No logic** beyond
register/lookup: it does not select, resolve to plans, or run anything. It is the "what can the
Assistant do" catalog; the Mission Catalog is the "how is each built" catalog.
"""

from __future__ import annotations

from collections.abc import Iterable

from assistant_runtime.capability import Capability


class CapabilityCatalog:
    """A registry of `Capability` by id. Register at construction or later; look up by id.

    Duplicate ids are rejected loudly — a catalog with two capabilities under one id is a wiring
    bug, not a silent last-wins."""

    def __init__(self, capabilities: Iterable[Capability] = ()) -> None:
        self._by_id: dict[str, Capability] = {}
        for capability in capabilities:
            self.register(capability)

    def register(self, capability: Capability) -> None:
        if capability.id in self._by_id:
            raise ValueError(f"capability {capability.id!r} is already registered")
        self._by_id[capability.id] = capability

    def get(self, capability_id: str) -> Capability | None:
        """The capability for an id, or `None` if absent — the exact question the Selector asks."""
        return self._by_id.get(capability_id)

    def __contains__(self, capability_id: object) -> bool:
        return capability_id in self._by_id

    def ids(self) -> tuple[str, ...]:
        return tuple(self._by_id)
