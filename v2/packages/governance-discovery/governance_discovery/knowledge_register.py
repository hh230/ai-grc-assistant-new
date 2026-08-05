"""The Knowledge Register — every question must justify its existence, and be checked against
what the packs actually do.

A question that cannot change any answer costs the customer time and buys trust the product has not
earned. Five of nineteen questions were in exactly that state before anyone noticed, and the only
reason it was noticed at all was a population sweep months later.

A document would have rotted. This does not, because it is **cross-checked against the rule graph**:
the register declares what a question is *for*, and `verify_register` proves the declaration matches
what the packs actually do. A question that stops driving decisions fails the check; a question
added without a declaration fails the check.

The five things a question must answer before it may be asked:

1. **why it exists**            — `purpose`
2. **what regulation needs it** — `regulatory_basis`
3. **which rules use it**       — derived from the packs, never hand-maintained, so it cannot lie
4. **what if it is missing**    — `when_unanswered`
5. **its effect on the answer** — `decision_effect`

`decision_effect` is the load-bearing field. `NONE` is a legal value — some questions are
genuinely for the record or for a future capability — but it must be *declared*, with a reason.
That converts "dead question" from an accident nobody sees into a deliberate, reviewable state.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

from governance_discovery.pack import KnowledgePack
from governance_discovery.predicate import referenced_signals


class DecisionEffect(enum.Enum):
    """How a question's answer reaches the customer's plan."""

    SEEDS_TASK = "seeds_task"          # its answer can add or remove work
    ACTIVATES_PACK = "activates_pack"  # its answer decides which questions follow
    SCORES_MATURITY = "scores_maturity"  # its answer moves a maturity dimension
    FLAGS_GAP = "flags_gap"            # its answer can raise a gap
    SCHEDULES = "schedules"            # its answer changes timing, not content
    DERIVES_APPLICABILITY = "derives_applicability"  # its answer implies which regime applies
    GATES_QUESTION = "gates_question"  # its answer decides whether another question is asked
    NONE = "none"                      # declared inert — must carry a reason


class WhenUnanswered(enum.Enum):
    """What the engine does with silence.

    Worth declaring explicitly because a predicate on a missing signal evaluates to False, which
    means gating on an unanswered question silently DROPS advice rather than being conservative
    with it. That is a fail-closed default, and it must be a choice rather than a surprise.
    """

    BLOCKS_CONCLUSION = "blocks_conclusion"
    LOWERS_CONFIDENCE = "lowers_confidence"
    RULES_DO_NOT_FIRE = "rules_do_not_fire"
    NO_EFFECT = "no_effect"


@dataclass(frozen=True)
class RegisterEntry:
    """One question's licence to be asked."""

    question_id: str
    purpose: str
    regulatory_basis: str
    when_unanswered: WhenUnanswered
    decision_effect: tuple[DecisionEffect, ...]
    inert_reason: str = ""

    def __post_init__(self) -> None:
        if DecisionEffect.NONE in self.decision_effect and not self.inert_reason:
            raise ValueError(
                f"{self.question_id}: a question declared to have NO decision effect must say why "
                f"it is still asked — otherwise it is a dead question with paperwork"
            )


@dataclass
class RegisterViolation:
    question_id: str
    problem: str


@dataclass
class RegisterReport:
    violations: list[RegisterViolation] = field(default_factory=list)
    checked: int = 0

    @property
    def ok(self) -> bool:
        return not self.violations

    def render(self) -> str:
        if self.ok:
            return f"knowledge register: {self.checked} question(s), all consistent with the packs"
        lines = [f"knowledge register: {len(self.violations)} problem(s)"]
        lines.extend(f"  {v.question_id}: {v.problem}" for v in self.violations)
        return "\n".join(lines)


def signals_that_drive_decisions(packs: dict[str, KnowledgePack]) -> set[str]:
    """Every signal the packs actually read — from rule predicates AND pack activation.

    Derived, never declared. A hand-maintained list of "which rules use this" is a list that will
    be wrong within a month; this one cannot drift because it is read from the same structures the
    engine evaluates.
    """
    used: set[str] = set()
    for pack in packs.values():
        activation = getattr(pack, "activation_predicate", None)
        if activation:
            used |= referenced_signals(activation)
        for rule in pack.rules:
            used |= referenced_signals(rule.predicate)
        # A signal read only by a derivation still drives decisions — arguably more than one read
        # by a single rule, since a derived property feeds every rule keyed on it. `ownership_type`
        # appears in no rule and is far from dead.
        for derivation in getattr(pack, "derivations", ()):
            used |= derivation.source_signals
        # Question applicability: a signal that decides whether another question is even ASKED is
        # shaping the interview, which is a decision the customer experiences directly.
        for question in pack.questions:
            used |= referenced_signals(question.applicability_predicate)
    return used


def verify_register(
    register: dict[str, RegisterEntry], packs: dict[str, KnowledgePack]
) -> RegisterReport:
    """Prove the register describes the packs as they actually are."""
    report = RegisterReport()
    asked: dict[str, str] = {}
    for pack in packs.values():
        for question in pack.questions:
            asked[question.id] = question.writes_signal

    driving = signals_that_drive_decisions(packs)

    for question_id, signal in sorted(asked.items()):
        report.checked += 1
        entry = register.get(question_id)
        if entry is None:
            report.violations.append(
                RegisterViolation(
                    question_id,
                    "asked of customers but absent from the register — no stated purpose, "
                    "regulatory basis, or decision effect",
                )
            )
            continue

        declared_inert = entry.decision_effect == (DecisionEffect.NONE,)
        actually_drives = signal in driving

        if declared_inert and actually_drives:
            report.violations.append(
                RegisterViolation(
                    question_id,
                    f"declared inert, but '{signal}' is read by the packs — the register "
                    f"understates it",
                )
            )
        elif not declared_inert and not actually_drives:
            report.violations.append(
                RegisterViolation(
                    question_id,
                    f"declared to affect decisions ({[e.value for e in entry.decision_effect]}), "
                    f"but no rule or activation predicate reads '{signal}' — this is a dead "
                    f"question",
                )
            )

    for question_id in sorted(set(register) - set(asked)):
        report.checked += 1
        report.violations.append(
            RegisterViolation(question_id, "in the register but no pack asks it — stale entry")
        )

    return report


def _entry(
    question_id: str,
    purpose: str,
    basis: str,
    unanswered: WhenUnanswered,
    effects: tuple[DecisionEffect, ...],
    inert_reason: str = "",
) -> tuple[str, RegisterEntry]:
    return question_id, RegisterEntry(
        question_id=question_id,
        purpose=purpose,
        regulatory_basis=basis,
        when_unanswered=unanswered,
        decision_effect=effects,
        inert_reason=inert_reason,
    )


# The register as it stands TODAY. Entries marked inert are the honest record of questions the
# product asks and does not yet act on — each is an open backlog item, not an oversight.
REGISTER: dict[str, RegisterEntry] = dict(
    [
        _entry(
            "q:primary_activity",
            "Infer which regulatory regime and sector obligations apply.",
            "NCA ECC applicability; sector-specific regimes (SAMA for financial services).",
            WhenUnanswered.RULES_DO_NOT_FIRE,
            (DecisionEffect.ACTIVATES_PACK,),
        ),
        _entry(
            "q:employee_count",
            "Size the plan to what the organization can actually execute, and gate structures "
            "that presuppose staff to run them.",
            "Proportionality — ISO 27001 §4.1 (context of the organization).",
            WhenUnanswered.RULES_DO_NOT_FIRE,
            (DecisionEffect.SEEDS_TASK, DecisionEffect.SCHEDULES),
        ),
        _entry(
            "q:provides_saas",
            "A SaaS provider holds other organizations' data, which changes its obligations.",
            "NCA CCC (cloud); NIST CSF for service providers.",
            WhenUnanswered.RULES_DO_NOT_FIRE,
            (DecisionEffect.ACTIVATES_PACK, DecisionEffect.SCORES_MATURITY),
        ),
        _entry(
            "q:has_compliance_officer",
            "Accountability for compliance must have a named owner.",
            "ISO 27001 §5.3; NCA ECC 1-1.",
            WhenUnanswered.RULES_DO_NOT_FIRE,
            (DecisionEffect.SEEDS_TASK, DecisionEffect.FLAGS_GAP, DecisionEffect.SCORES_MATURITY),
        ),
        _entry(
            "q:org_structure_state",
            "Roles and authorities must be documented and approved before anything rests on them.",
            "ISO 27001 §5.3.",
            WhenUnanswered.RULES_DO_NOT_FIRE,
            (DecisionEffect.SEEDS_TASK, DecisionEffect.SCORES_MATURITY),
        ),
        _entry(
            "q:policy_state",
            "A written, approved policy is the foundation every other control cites.",
            "ISO 27001 §5.2; NCA ECC 1-1.",
            WhenUnanswered.RULES_DO_NOT_FIRE,
            (DecisionEffect.SEEDS_TASK, DecisionEffect.FLAGS_GAP, DecisionEffect.SCORES_MATURITY),
        ),
        _entry(
            "q:risk_register_state",
            "Risk must be identified and owned before it can be treated.",
            "ISO 27001 §6.1; NCA ECC 1-5.",
            WhenUnanswered.RULES_DO_NOT_FIRE,
            (DecisionEffect.SEEDS_TASK, DecisionEffect.SCORES_MATURITY),
        ),
        _entry(
            "q:internal_audit_state",
            "Assurance that controls operate, not merely that they exist.",
            "ISO 27001 §9.2.",
            WhenUnanswered.RULES_DO_NOT_FIRE,
            (DecisionEffect.SEEDS_TASK, DecisionEffect.SCORES_MATURITY),
        ),
        _entry(
            "q:execution_capacity",
            "How much work the organization can absorb per period.",
            "Proportionality — ISO 27001 §4.1.",
            WhenUnanswered.RULES_DO_NOT_FIRE,
            (DecisionEffect.SCHEDULES, DecisionEffect.SCORES_MATURITY),
        ),
        _entry(
            "q:handles_personal_data",
            "Personal data brings privacy obligations that apply regardless of sector.",
            "PDPL; ISO 27701.",
            WhenUnanswered.RULES_DO_NOT_FIRE,
            (DecisionEffect.SEEDS_TASK, DecisionEffect.FLAGS_GAP),
        ),
        _entry(
            "q:has_gov_clients",
            "Serving government entities pulls an organization into the national regime.",
            "NCA ECC applicability.",
            WhenUnanswered.RULES_DO_NOT_FIRE,
            (DecisionEffect.SEEDS_TASK, DecisionEffect.FLAGS_GAP),
        ),
        _entry(
            "q:has_board",
            "Governance decisions need a body empowered to take them.",
            "ISO 27001 §5.1; NCA ECC 1-2.",
            WhenUnanswered.RULES_DO_NOT_FIRE,
            (DecisionEffect.SEEDS_TASK, DecisionEffect.SCORES_MATURITY),
        ),
        _entry(
            "q:has_it_team",
            "An organization with an IT function runs technology that needs a security baseline "
            "and data-residency controls, whether or not it sells software.",
            "NCA ECC 2-x (technology controls); NCA CCC (cloud).",
            WhenUnanswered.RULES_DO_NOT_FIRE,
            (DecisionEffect.ACTIVATES_PACK,),
        ),
        _entry(
            "q:tech_team_maturity",
            "Whether technical practice is documented and approved, not merely present.",
            "NCA ECC 2-x.",
            WhenUnanswered.RULES_DO_NOT_FIRE,
            (DecisionEffect.SEEDS_TASK,),
        ),
        _entry(
            "q:cloud_data_residency_controlled",
            "Where regulated data physically resides.",
            "PDPL cross-border transfer; NCA CCC.",
            WhenUnanswered.RULES_DO_NOT_FIRE,
            (DecisionEffect.SEEDS_TASK,),
        ),
        _entry(
            "q:ownership_type",
            "Ownership decides regime membership independently of sector: a government-owned "
            "entity is in national scope whatever it does, and foreign ownership implies "
            "cross-border reporting.",
            "NCA ECC applicability; PDPL cross-border transfer.",
            WhenUnanswered.RULES_DO_NOT_FIRE,
            (DecisionEffect.DERIVES_APPLICABILITY,),
        ),
        _entry(
            "q:outsources_critical_functions",
            "Work handed to a third party is still the organization's obligation; third-party "
            "risk is invisible to every other question we ask.",
            "ISO 27001 Annex A 5.19–5.23 (supplier relationships); NCA ECC 4-1.",
            WhenUnanswered.RULES_DO_NOT_FIRE,
            (DecisionEffect.SEEDS_TASK, DecisionEffect.SCORES_MATURITY),
        ),
        _entry(
            "q:operates_critical_infrastructure",
            "Critical national infrastructure carries the heaviest obligations in the regime, and "
            "no other answer reveals it.",
            "NCA ECC — critical national infrastructure scope.",
            WhenUnanswered.RULES_DO_NOT_FIRE,
            (
                DecisionEffect.SEEDS_TASK,
                DecisionEffect.FLAGS_GAP,
                DecisionEffect.DERIVES_APPLICABILITY,
            ),
        ),
        _entry(
            "q:data_geography",
            "Where regulated data physically sits decides whether transfer safeguards are needed.",
            "PDPL cross-border transfer provisions.",
            WhenUnanswered.RULES_DO_NOT_FIRE,
            (DecisionEffect.DERIVES_APPLICABILITY,),
        ),
        # --- declared inert: asked today, not yet acted on. Each is a backlog item. -------------
        _entry(
            "q:has_legal_team",
            "Whether legal review capacity exists in-house.",
            "Not yet tied to a control.",
            WhenUnanswered.NO_EFFECT,
            (DecisionEffect.NONE,),
            inert_reason=(
                "Backlog P2-7. Retained because legal capacity is expected to gate contractual and "
                "PDPL obligations once those rules exist; until then it changes nothing and the "
                "customer's time spent on it is not yet earned."
            ),
        ),
        _entry(
            "q:held_licenses",
            "Certifications and licences already held.",
            "ISO 27001 certification status; sector licensing.",
            WhenUnanswered.NO_EFFECT,
            (DecisionEffect.NONE,),
            inert_reason=(
                "Backlog P1-2. An ISO-certified organization is currently told to draft "
                "foundational policies. This is the highest value-per-effort open item, and is "
                "declared here so it cannot be forgotten again."
            ),
        ),
        _entry(
            "q:last_policy_review_date",
            "When the policy was last reviewed.",
            "ISO 27001 §5.2 (policy shall be reviewed at planned intervals).",
            WhenUnanswered.LOWERS_CONFIDENCE,
            (DecisionEffect.NONE,),
            inert_reason=(
                "Backlog P2-8. The most misleading kind of inert question: no rule reads it, "
                "yet it becomes REQUIRED once policies are approved, so leaving it blank lowers "
                "confidence — an effect no customer would predict from the question."
            ),
        ),
        _entry(
            "q:additional_context_note",
            "Free text for anything the structured questions cannot capture.",
            "None — an escape hatch, not a control.",
            WhenUnanswered.NO_EFFECT,
            (DecisionEffect.NONE,),
            inert_reason=(
                "Deliberately inert. It exists so a customer can say something the model has no "
                "signal for, and so those answers can be mined later for the signals we are "
                "missing (backlog P4-12). It must never gate a decision as unvalidated free text."
            ),
        ),
    ]
)


def verify_bundled() -> RegisterReport:
    """Check the register against the packs this build actually ships."""
    from governance_discovery.pack import load_bundled_packs

    return verify_register(REGISTER, load_bundled_packs())


def register_as_rows() -> list[dict[str, Any]]:
    """The register flattened for a document or a UI — one row per question."""
    return [
        {
            "question": entry.question_id,
            "purpose": entry.purpose,
            "regulatory_basis": entry.regulatory_basis,
            "when_unanswered": entry.when_unanswered.value,
            "decision_effect": [effect.value for effect in entry.decision_effect],
            "inert_reason": entry.inert_reason,
        }
        for entry in REGISTER.values()
    ]
