"""Applicability derivation — sector is a way to INFER obligations, not the axis rules key on.

The engine used to key rules on `primary_activity` directly, and the result was measurable: eight
of nine industries produced identical plans. Not because industry does not matter — it matters
enormously — but because writing a rule set per sector does not scale. Thirteen sectors times the
rules each one implies is a combinatorial explosion nobody maintains, so in practice nobody wrote
any, and the question became decorative.

The fix is to name what sectors actually *carry*:

    healthcare ──┐
    education  ──┼─→ processes_personal_data ─→ (rules about privacy)
    retail     ──┘

    financial_services ─→ provides_financial_services ─→ subject_to_sama ─→ (SAMA rules)

    government ───────┐
    has_gov_clients ──┴─→ is_government_linked ─→ subject_to_nca ─→ (NCA ECC rules)

Rules key on the derived property. Adding a sector then means adding *derivations* — a line of
data saying what that sector implies — not a parallel copy of every rule. This is the same reason
frameworks are data (CLAUDE.md §13): the thing that grows must be the data, not the engine.

Three invariants make this safe to reason about:

1. **An answer always beats an inference.** A derivation never overwrites a signal the customer
   actually answered. If they say they do not handle personal data, we do not conclude otherwise
   from their industry — we may be wrong about the industry's implications, they are not wrong
   about their own operations.
2. **Every derived signal carries its provenance.** Which derivation fired, from which source
   signals, on what regulatory basis — so a plan can always explain *why* PDPL was deemed to
   apply (CLAUDE.md §19).
3. **Derivation is a fixpoint, not one pass.** A property derived in one step may satisfy the
   condition of another (sector → financial services → SAMA). Termination is guaranteed by
   monotonicity — facts only accumulate, never change — and `MAX_DERIVATION_PASSES` additionally
   bounds the *depth*, so an implausibly long chain in a hand-edited pack fails loudly instead of
   quietly doing surprising work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from governance_discovery.predicate import Expr, evaluate, referenced_signals
from governance_discovery.signal import Signal, SignalSet, ValueType

# A derivation chain deeper than this is a modelling mistake, not a legitimate inference. Bounded
# so that a cyclic pack (data, therefore capable of containing a cycle) fails loudly and quickly
# rather than hanging the interview.
MAX_DERIVATION_PASSES = 8

# Derived signals are stamped below full confidence: an inference from sector is weaker evidence
# than the organization's own answer, and a recommendation that rests on one should say so rather
# than present it as established fact (ADR 0066 §5.6).
DERIVED_CONFIDENCE = 0.8


@dataclass(frozen=True)
class Derivation:
    """One inference: 'if this is true of you, then this obligation applies to you'."""

    id: str
    when: Expr
    derives_signal: str
    derives_value: Any
    value_type: ValueType
    # The regulatory reason this inference is legitimate. Not decoration — it is what a customer
    # is shown when they ask why an obligation was attributed to them, and what a reviewer checks.
    basis: str

    @property
    def source_signals(self) -> frozenset[str]:
        return referenced_signals(self.when)


@dataclass(frozen=True)
class DerivedFact:
    """The audit record for one inferred signal."""

    signal_key: str
    value: Any
    derivation_id: str
    basis: str
    source_signals: tuple[str, ...]

    def explain(self) -> str:
        sources = ", ".join(self.source_signals) or "no source"
        return f"{self.signal_key}={self.value!r} inferred from {sources} — {self.basis}"


@dataclass
class DerivationOutcome:
    signals: SignalSet
    derived: tuple[DerivedFact, ...] = ()
    # Derivations that matched but were declined because the customer had already answered. Kept
    # rather than dropped: a systematic disagreement between what a sector implies and what
    # customers report is a signal about the MODEL, and it is invisible if we discard it.
    overridden_by_answer: tuple[str, ...] = field(default_factory=tuple)

    def explain(self) -> list[str]:
        return [fact.explain() for fact in self.derived]


def parse_derivation(raw: dict) -> Derivation:
    for required in ("id", "when", "derives_signal", "derives_value", "value_type", "basis"):
        if required not in raw:
            raise ValueError(f"derivation missing required field: {required} in {raw.get('id')!r}")
    if not str(raw["id"]).startswith("d:"):
        raise ValueError(f"derivation id must start with 'd:': {raw['id']!r}")
    if not str(raw["basis"]).strip():
        raise ValueError(
            f"{raw['id']}: a derivation must cite the regulatory basis that makes the inference "
            f"legitimate — an unjustified inference is a guess wearing a citation's clothes"
        )
    return Derivation(
        id=raw["id"],
        when=raw["when"],
        derives_signal=raw["derives_signal"],
        derives_value=raw["derives_value"],
        value_type=ValueType(raw["value_type"]),
        basis=raw["basis"],
    )


def apply_derivations(
    signals: SignalSet,
    derivations: tuple[Derivation, ...],
    enum_scales: dict[str, tuple[str, ...]] | None = None,
) -> DerivationOutcome:
    """Infer every obligation implied by what the organization told us.

    Runs to a fixpoint so a chain (sector → financial services → SAMA) resolves in one call, and
    so the ORDER derivations appear in a pack file cannot change the outcome — order-dependence in
    a data file is a bug waiting for whoever edits it next.
    """
    answered = set(signals.keys())
    current = signals
    facts: dict[str, DerivedFact] = {}
    overridden: set[str] = set()

    for _ in range(MAX_DERIVATION_PASSES):
        changed = False
        for derivation in derivations:
            if not evaluate(derivation.when, current, enum_scales):
                continue
            key = derivation.derives_signal
            if key in answered:
                # The customer's own answer stands. Recorded, never silently dropped.
                overridden.add(derivation.id)
                continue
            existing = facts.get(key)
            if existing is not None and existing.value == derivation.derives_value:
                continue
            if existing is not None:
                raise ValueError(
                    f"derivations {existing.derivation_id} and {derivation.id} both derive "
                    f"'{key}' with conflicting values ({existing.value!r} vs "
                    f"{derivation.derives_value!r}) — the knowledge pack is contradictory"
                )
            facts[key] = DerivedFact(
                signal_key=key,
                value=derivation.derives_value,
                derivation_id=derivation.id,
                basis=derivation.basis,
                source_signals=tuple(sorted(derivation.source_signals)),
            )
            current = current.with_signal(
                Signal(
                    key=key,
                    value_type=derivation.value_type,
                    value=derivation.derives_value,
                    confidence=DERIVED_CONFIDENCE,
                )
            )
            changed = True
        if not changed:
            break
    else:
        raise ValueError(
            f"derivations did not settle within {MAX_DERIVATION_PASSES} passes — the knowledge "
            f"pack likely contains a derivation cycle"
        )

    return DerivationOutcome(
        signals=current,
        derived=tuple(facts[key] for key in sorted(facts)),
        overridden_by_answer=tuple(sorted(overridden)),
    )


def derivations_from_packs(packs: dict) -> tuple[Derivation, ...]:
    """Every derivation contributed by every loaded pack.

    Deliberately NOT filtered to active packs. Derivations are what *decide* which packs activate,
    so gating them on activation would be circular — a SAMA pack could never open, because the
    signal that opens it is derived by the pack it opens.
    """
    collected: list[Derivation] = []
    for pack in packs.values():
        collected.extend(getattr(pack, "derivations", ()))
    return tuple(collected)
