"""Which signals a Sector Knowledge Pack question is allowed to write (ADR 0068 §D2).

Derived from the loaded packs, never from a hand-maintained list: a list would be a second source
of truth about the engine's own vocabulary, and it would rot the first time someone adds a rule.

Three exclusions, each for its own reason:

* **Orphans** — a signal no rule and no derivation reads. Writing one is a question the customer
  answers for nothing, which is precisely the defect the sector packs already have.
* **Derived signals** — `subject_to_nca`, `cross_border_data_exposure` and their kin are
  CONCLUSIONS, not facts. Letting a pack assert one is letting the pack write a rule, which the
  Sector Knowledge Pack contract forbids. A pack states the fact; the derivation draws the
  conclusion.
* **`primary_activity`** — the signal that selects the sector in the first place. A sector pack
  writing it would be circular.
"""

from __future__ import annotations

from typing import Any

from governance_discovery.predicate import referenced_signals
from governance_discovery.signal import ValueType

# The sector selector. Excluded on its own grounds — see the module docstring.
SECTOR_SELECTOR = "primary_activity"


def _read_by_rules_and_derivations(packs: dict[str, Any]) -> frozenset[str]:
    keys: set[str] = set()
    for pack in packs.values():
        for rule in pack.rules:
            keys |= set(referenced_signals(rule.predicate))
        for derivation in getattr(pack, "derivations", ()) or ():
            keys |= set(derivation.source_signals)
    return frozenset(keys)


def _written_by_questions(packs: dict[str, Any]) -> dict[str, ValueType]:
    return {q.writes_signal: q.value_type for pack in packs.values() for q in pack.questions}


def _written_by_derivations(packs: dict[str, Any]) -> frozenset[str]:
    return frozenset(
        d.derives_signal
        for pack in packs.values()
        for d in (getattr(pack, "derivations", ()) or ())
    )


def writable_signals(packs: dict[str, Any]) -> dict[str, ValueType]:
    """`{signal_key: value_type}` a sector question may declare — asked by the interview, read by
    something, not a conclusion, not the sector selector."""
    asked = _written_by_questions(packs)
    consumed = _read_by_rules_and_derivations(packs)
    derived = _written_by_derivations(packs)
    return {
        key: value_type
        for key, value_type in asked.items()
        if key in consumed and key not in derived and key != SECTOR_SELECTOR
    }


def rejection_reason(key: str, packs: dict[str, Any]) -> str | None:
    """Why `key` may not be declared, in words a pack author can act on. `None` when it may."""
    if key in writable_signals(packs):
        return None
    if key == SECTOR_SELECTOR:
        return (
            f"'{key}' selects the sector this pack belongs to; a question inside it writing the "
            "signal that chose it is circular"
        )
    if key in _written_by_derivations(packs):
        return (
            f"'{key}' is DERIVED — a conclusion the engine draws, not a fact a customer states. "
            "Write the fact it is derived from instead; asserting the conclusion would put a rule "
            "in a knowledge pack (ADR 0068 §D2)"
        )
    if key not in _written_by_questions(packs):
        return f"'{key}' is not a signal any engine question writes"
    return (
        f"'{key}' is written but no rule and no derivation reads it — a question answered for "
        "nothing. Give it a consumer first, or do not declare it"
    )
