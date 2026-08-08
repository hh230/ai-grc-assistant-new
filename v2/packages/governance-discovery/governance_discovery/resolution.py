"""Signal Resolution (ADR 0068) — how a sector answer reaches the decision engine.

Sector Knowledge Pack answers used to reach the plan's PROSE and nothing else. That boundary was
deliberate and tested, and it stays: what changes here is that a sector question may now DECLARE
which existing engine signal it writes, and only then does its answer become a fact the rules can
see. Everything undeclared is still prose.

The measurement that motivated it: in real concluded sessions the signals gating the largest
regulatory decisions are answered a handful of times — `operates_critical_infrastructure` 3 of 14,
`data_geography` 5 — while the sector packs ask exactly those facts and threw the answers away. The
dominant case is therefore ABSENCE, not disagreement, and this module is shaped around that.

**Merge is a join on a flat lattice**, which is where its three required properties come from —
they are structural, not a discipline the caller must maintain:

    ⊥ ⊔ v = v          absence is the identity
    v ⊔ v = v          idempotent
    v ⊔ w = ⊤   (v≠w)  disagreement is a value of its own, not a winner
    ⊤ ⊔ x = ⊤          absorbing

`⊔` is commutative, associative and idempotent, so folding the sector claims CANNOT depend on their
order. The core answer is then applied as a DISTINGUISHED input rather than as one more element of
the fold — it is not "the last write", it is a different role:

    resolved(K) = core(K)          when the core interview answered K
                = ⨆ sector(K)      when the sector claims agree
                = unset            when they disagree and core is silent  (the fail-safe)

A `None` claim — an unanswered question, an option declared `null`, a boolean branch declared
`null` — never enters the fold at all. "We don't know" is not "no", and an unanswered question is
not "no". That is where wrong compliance decisions come from, so it is closed by the contract
rather than by care.

Two things this module deliberately does NOT do:

* It never reads answer TEXT. Values arrive already resolved through the pack's declared
  `option_id → value` map, so rewording or translating an option cannot move a decision.
* It never picks a winner in a disagreement. Both answers came from the same customer at full
  confidence; the sector question is not more specific, only differently worded. A conflict is
  recorded, the core value stands, and a human sees it at the approval gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from governance_discovery.signal import Signal, SignalSet, ValueType


class SignalOrigin(str, Enum):
    """Where a resolved value came from. Kept OFF `Signal` itself: the engine reasons over values,
    provenance is an audit record, and mixing the two would spread this feature through the frozen
    core for no gain."""

    CORE_ANSWER = "core_answer"
    SECTOR_ANSWER = "sector_answer"
    UNSET = "unset"


class ResolutionOutcome(str, Enum):
    ABSENT_FILLED = "absent_filled"
    CORROBORATED = "corroborated"
    CONFLICT_CORE_STANDS = "conflict_core_stands"
    CONFLICT_UNSET = "conflict_unset"


@dataclass(frozen=True)
class SectorClaim:
    """One sector answer that DECLARED a signal. `value is None` means the pack declared this
    option as carrying no signal — it is dropped, never coerced to False."""

    signal_key: str
    value: Any
    release_id: str
    question_id: str
    option_id: str
    value_type: ValueType


@dataclass(frozen=True)
class CoreClaim:
    signal_key: str
    value: Any


@dataclass(frozen=True)
class ResolvedSignal:
    """The audit record for one signal: what won, and everyone who spoke.

    In the CORROBORATED case `origin` stays CORE_ANSWER — the core interview remains the source and
    the sector claim is recorded as corroboration, not as a second author of the same fact.
    """

    signal_key: str
    resolved_value: Any
    origin: SignalOrigin
    outcome: ResolutionOutcome
    core_claim: CoreClaim | None = None
    sector_claims: tuple[SectorClaim, ...] = ()

    @property
    def is_conflict(self) -> bool:
        return self.outcome in (
            ResolutionOutcome.CONFLICT_CORE_STANDS,
            ResolutionOutcome.CONFLICT_UNSET,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "signal_key": self.signal_key,
            "resolved_value": self.resolved_value,
            "origin": self.origin.value,
            "outcome": self.outcome.value,
            "core_claim": (
                None if self.core_claim is None else {"value": self.core_claim.value}
            ),
            "sector_claims": [
                {
                    "release_id": c.release_id,
                    "question_id": c.question_id,
                    "option_id": c.option_id,
                    "value": c.value,
                }
                for c in self.sector_claims
            ],
        }


@dataclass(frozen=True)
class Resolution:
    """The two products of a merge, kept apart on purpose: what the engine reasons over, and the
    record of how it came to be."""

    signals: SignalSet
    resolved: tuple[ResolvedSignal, ...] = ()

    @property
    def conflicts(self) -> tuple[ResolvedSignal, ...]:
        return tuple(r for r in self.resolved if r.is_conflict)

    def as_audit(self) -> list[dict[str, Any]]:
        return [r.as_dict() for r in self.resolved]


# The lattice's top element. A module-level sentinel rather than an exception, because
# disagreement is an ordinary outcome here and not an error.
class _Conflicted:
    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging only
        return "⊤"


_CONFLICT = _Conflicted()


def _join(left: Any, right: Any) -> Any:
    """The flat-lattice join. Commutative, associative, idempotent — the whole determinism
    argument reduces to these three lines being true."""
    if left is _CONFLICT or right is _CONFLICT:
        return _CONFLICT
    if left is None:
        return right
    if right is None:
        return left
    return left if left == right else _CONFLICT


def resolve(core: SignalSet, claims: tuple[SectorClaim, ...] | list[SectorClaim]) -> Resolution:
    """Merge declared sector claims into the core signal set.

    Returns the SignalSet the engine will reason over, plus one `ResolvedSignal` per signal any
    sector claim spoke about. Signals nobody claimed are carried through untouched and produce no
    audit record — the record exists to explain the sector channel, not to restate the interview.
    """
    grouped: dict[str, list[SectorClaim]] = {}
    for claim in claims:
        # A claim with no value is not a claim. Dropped here, before the fold, so it can neither
        # create a conflict nor a value.
        if claim.value is None:
            continue
        grouped.setdefault(claim.signal_key, []).append(claim)

    signals = core
    records: list[ResolvedSignal] = []

    # Sorted so the AUDIT is stable too. The merge itself is order-independent by construction;
    # this only stops two identical runs producing differently-ordered records.
    for key in sorted(grouped):
        group = sorted(grouped[key], key=lambda c: (c.release_id, c.question_id, c.option_id))
        joined: Any = None
        for claim in group:
            joined = _join(joined, claim.value)

        core_signal = core.get(key)
        core_claim = None if core_signal is None else CoreClaim(key, core_signal.value)

        if core_signal is not None:
            if joined is _CONFLICT or joined != core_signal.value:
                # The core value stands and the plan is exactly what it would have been without
                # this feature — the weakest possible action, which is the right one when the
                # customer has told us two different things.
                outcome = ResolutionOutcome.CONFLICT_CORE_STANDS
            else:
                outcome = ResolutionOutcome.CORROBORATED
            records.append(
                ResolvedSignal(
                    signal_key=key,
                    resolved_value=core_signal.value,
                    origin=SignalOrigin.CORE_ANSWER,
                    outcome=outcome,
                    core_claim=core_claim,
                    sector_claims=tuple(group),
                )
            )
            continue

        if joined is _CONFLICT:
            # Two sector packs disagree and the interview never asked. Leaving the signal UNSET is
            # the fail-safe: no decision is built on a fact we do not have.
            records.append(
                ResolvedSignal(
                    signal_key=key,
                    resolved_value=None,
                    origin=SignalOrigin.UNSET,
                    outcome=ResolutionOutcome.CONFLICT_UNSET,
                    core_claim=None,
                    sector_claims=tuple(group),
                )
            )
            continue

        # The case this whole feature exists for: the interview never asked, and the sector did.
        #
        # `with_signal` appears here and nowhere else, and it is NOT the merge: the merge is the
        # `_join` fold above, and this writes a value that fold has already settled, once per key.
        # Merging BY looping `with_signal` would be last-write-wins — order-dependent, and the
        # exact property ADR 0068 exists to rule out.
        signals = signals.with_signal(
            Signal(key=key, value_type=group[0].value_type, value=joined, confidence=1.0)
        )
        records.append(
            ResolvedSignal(
                signal_key=key,
                resolved_value=joined,
                origin=SignalOrigin.SECTOR_ANSWER,
                outcome=ResolutionOutcome.ABSENT_FILLED,
                core_claim=None,
                sector_claims=tuple(group),
            )
        )

    return Resolution(signals=signals, resolved=tuple(records))
