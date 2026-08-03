"""Pure functions behind Plan Execution's maturity recalculation (ADR 0066 §5.3). No I/O — the
`governance-plan-execution` service (a separate package) reads/writes rows and calls these; nothing
here touches a database or a clock. This is what makes "un-completing a task" need no undo logic:
current state is always recomputed fresh from a frozen baseline plus whatever is *currently* done,
never mutated in place.
"""

from __future__ import annotations

from governance_discovery.signal import Signal, SignalSet, ValueType


def _infer_value_type(existing: Signal | None, value: object) -> ValueType:
    if existing is not None:
        return existing.value_type
    if isinstance(value, bool):
        return ValueType.BOOLEAN
    if isinstance(value, (int, float)):
        return ValueType.NUMERIC
    return ValueType.ENUM


def effective_signals(
    baseline: SignalSet, resolutions: list[tuple[str, object, float]]
) -> SignalSet:
    """`baseline` is the frozen snapshot copied into `organization_profiles` when a discovery
    session concluded (ADR 0066 §5.7). `resolutions` is `(signal_key, value, completed_at)` for
    every `governance_plan_item` currently `status='done'` with a non-null `resolves_signal`,
    across every plan version for the tenant — the caller (the Plan Execution service) is
    responsible for that query; this function only combines what it's given.

    Applied in ascending `completed_at` order so the most recent completion wins a same-key
    conflict (the rare case of two different items resolving the same signal) — deterministic,
    no wall-clock access, no hidden state. An item that is reopened simply stops appearing in
    `resolutions` on the next call; there is no separate "revert" to perform.
    """
    result = baseline
    for key, value, _completed_at in sorted(resolutions, key=lambda r: r[2]):
        value_type = _infer_value_type(baseline.get(key), value)
        result = result.with_signal(
            Signal(key=key, value_type=value_type, value=value, confidence=1.0)
        )
    return result


__all__ = ["effective_signals"]
