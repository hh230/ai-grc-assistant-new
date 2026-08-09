"""Validating a sector question's signal declaration (ADR 0068 §D1).

A pack question may say "answering me writes signal K". This module is what stops that sentence
from being a wish. It runs at seed time, where the option list is in hand — the schema can only
state the half it can see on its own (`writes_signal IS NULL OR signal_value_map IS NOT NULL`).

Every rule here exists because of a specific way a compliance decision goes wrong:

* **The map is keyed by `option_id`, never by text.** Otherwise revising Arabic wording or adding
  an English translation would move a decision, and a translator would become a governance actor.
* **Completeness in both directions.** A missing option means an unanswerable default; an extra
  entry means the author is describing an option that no longer exists. Neither may pass silently.
* **`null` is a declaration, not a hole.** "We don't know" contributes nothing. What it must never
  do is become `False` — that is how a system decides an organization has no obligation because
  nobody asked it properly.
* **Closed question types only.** `text` can never map to a value without reading it. `multi_select`
  needs a condition ("if any of these are selected…"), and a condition inside a knowledge pack is a
  rule — which the pack contract forbids. Deferred to its own ADR rather than smuggled in here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from governance_discovery.pack import load_bundled_packs
from governance_discovery.signal import DEFAULT_MATURITY_SCALE, ValueType
from governance_discovery.writable_signals import rejection_reason, writable_signals

from grc_api.question_options import normalized_options

# The only question types whose answer maps to a value without interpretation.
DECLARABLE_TYPES = ("enum", "boolean")
# A boolean question has no option list, so its two branches use these reserved ids — one
# declaration shape for every question type instead of one per type.
BOOLEAN_OPTION_IDS = ("true", "false")


@dataclass(frozen=True)
class DeclarationError:
    question_id: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.question_id}: {self.message}"


def _engine_enum_values(signal_key: str, packs: dict[str, Any]) -> tuple[str, ...] | None:
    """The vocabulary the engine itself defines for an enum signal, or None when it is a maturity
    ladder question with no explicit options."""
    for pack in packs.values():
        for question in pack.questions:
            if question.writes_signal == signal_key:
                if question.options:
                    return tuple(question.options)
                return DEFAULT_MATURITY_SCALE
    return None


def _expected_option_ids(question: dict[str, Any]) -> tuple[str, ...]:
    """The ids a declaration must cover. Only options with a STABLE id count: a bare string's id is
    the string itself, and a map keyed by Arabic text is the thing ADR 0068 exists to prevent."""
    if question.get("type") == "boolean":
        return BOOLEAN_OPTION_IDS
    return tuple(o.option_id for o in normalized_options(question) if o.has_stable_id)


def validate_declaration(
    question: dict[str, Any], packs: dict[str, Any] | None = None
) -> list[DeclarationError]:
    """Every problem with one question's declaration. Empty list = valid (including the common
    case of no declaration at all)."""
    signal_key = question.get("writes_signal")
    question_id = str(question.get("question_id") or "<unnamed>")
    value_map = question.get("signal_value_map")

    if not signal_key:
        if value_map:
            return [
                DeclarationError(
                    question_id,
                    "has a signal_value_map but declares no writes_signal — a map that maps to "
                    "nothing is a leftover, not a declaration",
                )
            ]
        return []

    resolved_packs = load_bundled_packs() if packs is None else packs
    errors: list[DeclarationError] = []

    reason = rejection_reason(signal_key, resolved_packs)
    if reason:
        return [DeclarationError(question_id, reason)]

    question_type = question.get("type")
    if question_type not in DECLARABLE_TYPES:
        return [
            DeclarationError(
                question_id,
                f"type '{question_type}' cannot declare a signal — only "
                f"{', '.join(DECLARABLE_TYPES)} map to a value without interpreting the answer "
                "(ADR 0068 §D1a)",
            )
        ]

    if not isinstance(value_map, dict):
        return [DeclarationError(question_id, "declares writes_signal but no signal_value_map")]

    expected = _expected_option_ids(question)
    if question_type == "enum" and len(expected) != len(question.get("options") or ()):
        errors.append(
            DeclarationError(
                question_id,
                "every option needs a stable option_id before this question can declare a signal "
                "— the map is keyed by id so that rewording or translating an option cannot move "
                "a decision",
            )
        )
    if len(set(expected)) != len(expected):
        errors.append(DeclarationError(question_id, "option_id values must be unique"))

    missing = [i for i in expected if i not in value_map]
    if missing:
        errors.append(
            DeclarationError(
                question_id,
                f"no signal value declared for option(s) {', '.join(missing)} — declare null "
                "explicitly if the option carries no signal; there is no default",
            )
        )
    extra = [k for k in value_map if k not in expected]
    if extra:
        errors.append(
            DeclarationError(
                question_id,
                f"signal_value_map names option(s) that do not exist: {', '.join(sorted(extra))}",
            )
        )

    errors.extend(_value_errors(question_id, signal_key, value_map, resolved_packs))
    return errors


def _value_errors(
    question_id: str, signal_key: str, value_map: dict[str, Any], packs: dict[str, Any]
) -> list[DeclarationError]:
    value_type = writable_signals(packs)[signal_key]
    errors: list[DeclarationError] = []
    for option_id, value in value_map.items():
        if value is None:
            continue  # a declared null: contributes nothing, and that is a decision
        if value_type is ValueType.BOOLEAN and not isinstance(value, bool):
            errors.append(
                DeclarationError(
                    question_id,
                    f"option '{option_id}' maps to {value!r}, but '{signal_key}' is boolean",
                )
            )
        elif value_type is ValueType.NUMERIC and not isinstance(value, (int, float)):
            errors.append(
                DeclarationError(
                    question_id,
                    f"option '{option_id}' maps to {value!r}, but '{signal_key}' is numeric",
                )
            )
        elif value_type is ValueType.ENUM:
            allowed = _engine_enum_values(signal_key, packs)
            if allowed and value not in allowed:
                errors.append(
                    DeclarationError(
                        question_id,
                        f"option '{option_id}' maps to {value!r}, which is not one of "
                        f"'{signal_key}''s values ({', '.join(allowed)})",
                    )
                )
    return errors


def validate_pack_declarations(
    pack: dict[str, Any], packs: dict[str, Any] | None = None
) -> list[DeclarationError]:
    resolved = load_bundled_packs() if packs is None else packs
    return [
        error
        for question in pack.get("questions", ())
        for error in validate_declaration(question, resolved)
    ]
