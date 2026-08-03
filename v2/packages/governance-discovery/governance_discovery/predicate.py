"""The declarative predicate DSL (ADR 0066 §2.3–§2.4) — a small interpreter over data, never
`eval`'d code (CLAUDE.md §6 pillar 8). Used identically for question `applicability_predicate`,
pack `activation_predicate`, and rule `predicate`.

Shape: `{"all": [Expr, ...]}` | `{"any": [Expr, ...]}` | `{"signal": key, "op": op, "value": v}`.
"""

from __future__ import annotations

from typing import Any

from governance_discovery.signal import DEFAULT_MATURITY_SCALE, SignalSet, ValueType

Expr = dict[str, Any]

_COMPARISON_OPS = frozenset({"gte", "lte", "between"})
_EQUALITY_OPS = frozenset({"eq", "neq", "in"})
_VALID_OPS = _COMPARISON_OPS | _EQUALITY_OPS


def _ordinal(key: str, value: Any, enum_scales: dict[str, tuple[str, ...]] | None) -> int:
    scale = (enum_scales or {}).get(key, DEFAULT_MATURITY_SCALE)
    try:
        return scale.index(value)
    except ValueError:
        return -1


def evaluate(
    expr: Expr | None,
    signals: SignalSet,
    enum_scales: dict[str, tuple[str, ...]] | None = None,
) -> bool:
    """A predicate of `None` always activates/applies — used for the always-on `core` pack and
    for questions with no gating condition."""
    if expr is None:
        return True
    if "all" in expr:
        return all(evaluate(sub, signals, enum_scales) for sub in expr["all"])
    if "any" in expr:
        return any(evaluate(sub, signals, enum_scales) for sub in expr["any"])

    key, op, target = expr["signal"], expr["op"], expr.get("value")
    if op not in _VALID_OPS:
        raise ValueError(f"unknown predicate op: {op!r}")

    signal = signals.get(key)
    if signal is None:
        return False
    value = signal.value

    if op == "eq":
        return value == target
    if op == "neq":
        return value != target
    if op == "in":
        return value in target
    if op == "between":
        low, high = target
        return value is not None and low <= value <= high

    # gte/lte: ordinal comparison for enum values, numeric comparison otherwise
    if signal.value_type == ValueType.ENUM:
        left, right = _ordinal(key, value, enum_scales), _ordinal(key, target, enum_scales)
    else:
        if value is None:
            return False
        left, right = value, target
    return left >= right if op == "gte" else left <= right


def references_signal(expr: Expr | None, key: str) -> bool:
    """Whether `key` appears anywhere in a predicate tree — the information-gain heuristic
    (ADR 0066 §2.4) counts how many rules reference a candidate question's signal key."""
    if expr is None:
        return False
    if "all" in expr or "any" in expr:
        return any(references_signal(sub, key) for sub in expr.get("all", expr.get("any", [])))
    return expr.get("signal") == key


def referenced_signals(expr: Expr | None) -> frozenset[str]:
    """Every signal key named anywhere in a predicate tree — the basis for per-recommendation
    Confidence (ADR 0066 §5.6): which facts does this rule's conclusion actually rest on."""
    if expr is None:
        return frozenset()
    if "all" in expr or "any" in expr:
        keys: set[str] = set()
        for sub in expr.get("all", expr.get("any", [])):
            keys |= referenced_signals(sub)
        return frozenset(keys)
    key = expr.get("signal")
    return frozenset({key}) if key else frozenset()
