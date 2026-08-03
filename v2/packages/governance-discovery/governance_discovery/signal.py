"""Typed Signals — the facts the adaptive interview accumulates (ADR 0066 §2.3).

A Signal is never a bare boolean by default: governance maturity is not binary, and quantities
like headcount are captured as real numbers, not pre-bucketed bands. `value_type` says which shape
`value` takes; `SignalSet` is the accumulated, latest-value-wins collection the engine reasons
over.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ValueType(str, Enum):
    BOOLEAN = "boolean"
    ENUM = "enum"
    NUMERIC = "numeric"
    DATE = "date"
    PERCENTAGE = "percentage"
    # Free-form clarification text. Never gates a predicate directly — captured as supplementary
    # context for a human reviewer (and, later, a bounded LLM normalizer), never structural
    # control flow (CLAUDE.md §6 pillar 8). Questions of this type are typically `required=False`.
    TEXT = "text"
    # A provenance modifier: the underlying value (still boolean/enum/numeric underneath) was
    # corroborated by an uploaded/ingested document rather than self-reported. Confidence is
    # stamped 1.0 directly and the free-text LLM normalizer is bypassed (ADR 0066 §2.3).
    EVIDENCE_BACKED = "evidence_backed"


# The default ordered maturity scale for process/policy-state questions — five levels, not a
# yes/no (ADR 0066 §2.3). A pack may declare a custom ordered scale for a specific signal key
# instead (see `predicate.enum_scales`).
DEFAULT_MATURITY_SCALE: tuple[str, ...] = (
    "absent",
    "verbal",
    "documented_unapproved",
    "approved",
    "reviewed_periodically",
)


@dataclass(frozen=True)
class Signal:
    key: str
    value_type: ValueType
    value: Any
    confidence: float = 1.0
    source_answer_id: str | None = None


class SignalSet:
    """The live, accumulated fact set. Immutable — `with_signal` returns a new SignalSet, so a
    session can always reconstruct exactly what was known at any point (CLAUDE.md §19)."""

    def __init__(self, signals: dict[str, Signal] | None = None) -> None:
        self._signals: dict[str, Signal] = dict(signals or {})

    def with_signal(self, signal: Signal) -> SignalSet:
        updated = dict(self._signals)
        updated[signal.key] = signal
        return SignalSet(updated)

    def get(self, key: str) -> Signal | None:
        return self._signals.get(key)

    def has(self, key: str) -> bool:
        return key in self._signals

    def value(self, key: str, default: Any = None) -> Any:
        signal = self._signals.get(key)
        return signal.value if signal is not None else default

    def keys(self) -> frozenset[str]:
        return frozenset(self._signals.keys())

    def as_dict(self) -> dict[str, Any]:
        return {key: signal.value for key, signal in self._signals.items()}

    def __len__(self) -> int:
        return len(self._signals)

    def __repr__(self) -> str:  # pragma: no cover - debug convenience
        return f"SignalSet({self.as_dict()!r})"
