"""The `CapabilitySelector` — layer 2 of the two-layer selection (ADR 0046 §4).

**One responsibility, deterministically:** does the suggested capability exist in the Capability
Catalog? **Yes → that capability. No → the fallback** (`ask` / `simple_question`). No extra
intelligence — no confidence thresholds, no input validation, no ranking (a Slice-2 constraint).
This is the boundary that makes the LLM a *suggester*: the LLM can influence which registered
capability is chosen; the Selector guarantees only a *registered* capability is ever returned, so a
hallucinated one can never reach a Mission.
"""

from __future__ import annotations

from assistant_runtime.capability import Capability
from assistant_runtime.capability_catalog import CapabilityCatalog
from assistant_runtime.errors import FallbackCapabilityMissing
from assistant_runtime.intent import CapabilityIntent


class CapabilitySelector:
    """Resolves a `CapabilityIntent` to a **registered** `Capability`, falling back when the
    candidate is unknown."""

    def __init__(self, catalog: CapabilityCatalog, *, fallback_id: str = "simple_question") -> None:
        self._catalog = catalog
        self._fallback_id = fallback_id

    def select(self, intent: CapabilityIntent) -> Capability:
        """Existence check only (ADR 0046 §4): the candidate if registered, else the fallback. The
        fallback itself must be registered, or this fails loud (`FallbackCapabilityMissing`) rather
        than returning nothing."""
        candidate = self._catalog.get(intent.capability_id)
        if candidate is not None:
            return candidate
        fallback = self._catalog.get(self._fallback_id)
        if fallback is None:
            raise FallbackCapabilityMissing(self._fallback_id)
        return fallback
