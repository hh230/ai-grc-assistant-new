"""Turns one raw answer (whatever JSON-plain value the client submitted) into a typed `Signal`,
validated against the question's declared `value_type`/`options`/`allow_multiple` (CLAUDE.md §22:
validate at boundaries). This is the "direct" resolution path (ADR 0066 §2.3) — free-text answers
are stored verbatim as `ValueType.TEXT` context, never coerced into a structural signal here; the
bounded LLM classifier role described in the ADR is a later addition, not part of this slice.
"""

from __future__ import annotations

from datetime import date

from governance_discovery.pack import Question
from governance_discovery.signal import Signal, ValueType

from governance_session.errors import InvalidAnswer


def resolve_signal(question: Question, raw_answer: object) -> Signal:
    value_type = question.value_type
    if value_type == ValueType.BOOLEAN:
        value = _as_boolean(question, raw_answer)
    elif value_type == ValueType.NUMERIC or value_type == ValueType.PERCENTAGE:
        value = _as_number(question, raw_answer)
    elif value_type == ValueType.DATE:
        value = _as_date_string(question, raw_answer)
    elif value_type == ValueType.ENUM:
        value = _as_enum(question, raw_answer)
    elif value_type == ValueType.TEXT:
        value = _as_text(question, raw_answer)
    else:  # pragma: no cover - EVIDENCE_BACKED has no direct-entry path in this slice
        raise InvalidAnswer(question.id, f"unsupported value_type for direct entry: {value_type}")
    return Signal(key=question.writes_signal, value_type=value_type, value=value, confidence=1.0)


def _as_boolean(question: Question, raw: object) -> bool:
    if isinstance(raw, bool):
        return raw
    raise InvalidAnswer(question.id, "expected a boolean (yes/no)")


def _as_number(question: Question, raw: object) -> float | int:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise InvalidAnswer(question.id, "expected a number")
    return raw


def _as_date_string(question: Question, raw: object) -> str:
    if not isinstance(raw, str):
        raise InvalidAnswer(question.id, "expected an ISO date string (YYYY-MM-DD)")
    try:
        date.fromisoformat(raw)
    except ValueError as exc:
        raise InvalidAnswer(question.id, "expected an ISO date string (YYYY-MM-DD)") from exc
    return raw


def _as_enum(question: Question, raw: object) -> object:
    options = question.options or ()
    if question.allow_multiple:
        if not isinstance(raw, list) or not raw:
            raise InvalidAnswer(question.id, "expected a non-empty list of options")
        invalid = [item for item in raw if item not in options]
        if invalid:
            raise InvalidAnswer(question.id, f"not a valid option: {invalid}")
        return list(raw)
    if raw not in options:
        raise InvalidAnswer(question.id, f"not a valid option: {raw!r}")
    return raw


def _as_text(question: Question, raw: object) -> str:
    if not isinstance(raw, str):
        raise InvalidAnswer(question.id, "expected text")
    return raw.strip()
