"""Intent Understanding — layer 1 of the two-layer selection (ADR 0046 §4).

The `IntentRecognizer` **suggests** a capability; it **never decides or runs** anything. It maps a
free-text request to a `CapabilityIntent` — a *candidate* capability id, a confidence, and any
inputs it extracted. The deterministic `CapabilitySelector` (layer 2) then decides.

**No real LLM in Slice 2.** This module ships the port plus one reference implementation,
`KeywordIntentRecognizer` — a trivial, deterministic matcher. The real LLM-backed recognizer will
implement the same `IntentRecognizer` port and drop in with no change to the Selector, the Catalogs,
or the runtime. That separation is the whole point of making intent a port: the LLM can influence
*which registered capability* is proposed, and nothing more (the anti-hallucination boundary).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from pipeline_contracts import TenantContext


@dataclass(frozen=True)
class CapabilityIntent:
    """A *suggestion*, not an action: the candidate capability id (empty for "no idea"), a
    confidence, and any extracted inputs. It is deliberately incapable of naming a Mission or
    triggering execution — it names at most a *candidate capability id*."""

    capability_id: str = ""
    confidence: float = 0.0
    inputs: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class IntentRecognizer(Protocol):
    """The port layer 1 depends on. An implementation suggests a `CapabilityIntent` from a request;
    it must not select, resolve, persist, or execute."""

    def recognize(self, request: str, tenant: TenantContext) -> CapabilityIntent: ...


class KeywordIntentRecognizer:
    """A reference `IntentRecognizer` (NO LLM): matches the request against a keyword → capability
    map, first hit wins, and passes the raw request through as an input. Deterministic and trivial —
    it exists so the two-layer selection can be exercised without a model. A miss returns an empty
    `capability_id`, so the Selector falls back (ADR 0046 §4)."""

    def __init__(self, keyword_to_capability: Mapping[str, str]) -> None:
        # lower-cased for case-insensitive substring matching
        self._map: dict[str, str] = {kw.lower(): cid for kw, cid in keyword_to_capability.items()}

    def recognize(self, request: str, tenant: TenantContext) -> CapabilityIntent:
        text = request.lower()
        for keyword, capability_id in self._map.items():
            if keyword in text:
                return CapabilityIntent(
                    capability_id=capability_id, confidence=1.0, inputs={"request": request}
                )
        return CapabilityIntent(capability_id="", confidence=0.0, inputs={"request": request})
