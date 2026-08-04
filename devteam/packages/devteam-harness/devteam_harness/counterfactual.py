"""The Counterfactual Judge — what happens if ONE answer changes?

The Decision Verifier asks "is this plan sensible". This asks a harder question that catches a
different class of defect entirely:

    Is the plan *sensitive to the right things*, and *insensitive to the wrong ones*?

A plan is a decision function over the organization's answers. Judging its outputs one at a time
cannot see the shape of that function. Judging its **derivative** can, and three shapes are
defects:

| shape | what it looks like | why it is wrong |
|---|---|---|
| **CLIFF** | 45 employees → 46 flips the plan | a threshold sitting where no real distinction exists |
| **VANISHING** | a small IMPROVEMENT deletes every task | the org is punished for progress by being abandoned |
| **INERT** | gaining government clients changes nothing | the question was asked and then ignored |

`INERT` is the one nobody looks for. A question that never changes the outcome is worse than a
missing question: it costs the customer time and buys trust the system has not earned — they
believe the answer mattered.

This runs against `analyze()` directly, not through the interview. That is deliberate: the
interview is adaptive, so changing one answer changes which questions come next, and the comparison
would no longer be "one variable moved" but "two plans from two different conversations".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from governance_discovery.analysis import analyze

from devteam_harness.decisions import MATURITY_LADDER

# Signals whose answer materially changes an organization's obligations. If moving one of these
# changes nothing about the plan, the product asked a question it does not act on.
CONSEQUENTIAL_SIGNALS: frozenset[str] = frozenset(
    {
        "handles_personal_data",
        "has_gov_clients",
        "has_compliance_officer",
        "has_board",
        "policy_state",
        "org_structure_state",
        "risk_register_state",
        "internal_audit_state",
    }
)

# A one-step move along the ladder is the smallest meaningful change to a state signal.
LADDER_SIGNALS: frozenset[str] = frozenset(
    {"policy_state", "org_structure_state", "risk_register_state", "internal_audit_state"}
)

# Numeric probes: a ±1 change must never restructure a plan. Anything that does is a threshold
# sitting exactly where the product claims a distinction that does not exist in reality.
NEAR_MISS_DELTA = 1


@dataclass(frozen=True)
class Perturbation:
    """One single-variable change, described so a human can argue with it."""

    signal: str
    before: Any
    after: Any

    def describe(self) -> str:
        return f"{self.signal}: {self.before!r} → {self.after!r}"


@dataclass(frozen=True)
class CounterfactualFinding:
    kind: str
    perturbation: Perturbation
    detail: str


@dataclass
class PlanShape:
    """What a plan IS, reduced to what a comparison should care about.

    Task identity and priority — not wording, not ordering within a bucket. Comparing raw dicts
    would report a defect every time an unrelated field was added.
    """

    task_ids: frozenset[str]
    priorities: dict[str, str] = field(default_factory=dict)

    @property
    def size(self) -> int:
        return len(self.task_ids)

    def churn(self, other: PlanShape) -> float:
        """Fraction of tasks that differ — 0.0 identical, 1.0 nothing in common."""
        union = self.task_ids | other.task_ids
        if not union:
            return 0.0
        return len(self.task_ids ^ other.task_ids) / len(union)


def shape_of(applicability: Any) -> PlanShape:
    items = list(applicability.plan_items)
    return PlanShape(
        task_ids=frozenset(str(item["id"]) for item in items),
        priorities={str(item["id"]): str(item.get("priority", "")) for item in items},
    )


# --- the probes ---------------------------------------------------------------------------------


def ladder_perturbations(signals: dict[str, Any]) -> list[Perturbation]:
    """One rung UP for each maturity signal — the organization improving slightly."""
    perturbations = []
    for signal, value in signals.items():
        if signal not in LADDER_SIGNALS or value not in MATURITY_LADDER:
            continue
        index = MATURITY_LADDER.index(value)
        if index + 1 < len(MATURITY_LADDER):
            perturbations.append(Perturbation(signal, value, MATURITY_LADDER[index + 1]))
    return perturbations


def boolean_perturbations(signals: dict[str, Any]) -> list[Perturbation]:
    """Flip each consequential yes/no answer."""
    return [
        Perturbation(signal, value, not value)
        for signal, value in signals.items()
        if signal in CONSEQUENTIAL_SIGNALS and isinstance(value, bool)
    ]


def near_miss_perturbations(signals: dict[str, Any]) -> list[Perturbation]:
    """±1 on numeric answers — the 45 → 46 probe."""
    perturbations = []
    for signal, value in signals.items():
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        perturbations.append(Perturbation(signal, value, value + NEAR_MISS_DELTA))
        if value - NEAR_MISS_DELTA > 0:
            perturbations.append(Perturbation(signal, value, value - NEAR_MISS_DELTA))
    return perturbations


def all_perturbations(signals: dict[str, Any]) -> list[Perturbation]:
    return [
        *ladder_perturbations(signals),
        *boolean_perturbations(signals),
        *near_miss_perturbations(signals),
    ]


# --- judging one perturbation --------------------------------------------------------------------

# How much a plan may change when the organization improves by one rung. Above this, the plan is
# not adapting — it is being replaced.
IMPROVEMENT_CHURN_LIMIT = 0.75


def judge_change(
    perturbation: Perturbation, before: PlanShape, after: PlanShape
) -> list[CounterfactualFinding]:
    """Compare two plans that differ by exactly one answer."""
    findings: list[CounterfactualFinding] = []

    # VANISHING — only for a genuine IMPROVEMENT along the maturity ladder. A boolean flip that
    # REDUCES obligations (no longer handling personal data) legitimately removes its task, and
    # reporting that would be crying wolf: correct behaviour dressed as a defect.
    if perturbation.signal in LADDER_SIGNALS and before.size > 0 and after.size == 0:
        findings.append(
            CounterfactualFinding(
                "improvement_empties_the_plan",
                perturbation,
                f"{perturbation.describe()} removed ALL {before.size} task(s) — an organization "
                f"that improved by one step is told it has nothing to do",
            )
        )
        return findings

    # CLIFF — a ±1 numeric change must never restructure a plan.
    if isinstance(perturbation.before, int) and not isinstance(perturbation.before, bool):
        churn = before.churn(after)
        if churn > 0:
            findings.append(
                CounterfactualFinding(
                    "threshold_cliff",
                    perturbation,
                    f"{perturbation.describe()} changed {round(churn * 100)}% of the plan — a "
                    f"one-unit difference should not restructure advice",
                )
            )
        return findings

    # Excessive churn on a single-rung improvement.
    if perturbation.signal in LADDER_SIGNALS:
        churn = before.churn(after)
        if churn > IMPROVEMENT_CHURN_LIMIT:
            findings.append(
                CounterfactualFinding(
                    "improvement_replaces_the_plan",
                    perturbation,
                    f"{perturbation.describe()} changed {round(churn * 100)}% of the plan — one "
                    f"step of progress should adapt the plan, not replace it",
                )
            )
    return findings


def domain_of(signal: str, value: Any) -> list[Any]:
    """Every value a signal can take — the whole domain, not one neighbouring step."""
    if signal in LADDER_SIGNALS:
        return list(MATURITY_LADDER)
    if isinstance(value, bool):
        return [True, False]
    return []


def find_ignored_signals(signals: dict[str, Any], replan: Any) -> list[CounterfactualFinding]:
    """Signals the plan never reacts to, ACROSS THEIR WHOLE DOMAIN.

    Deliberately not "this one step changed nothing" — that was the first version, and it produced
    412 findings on 120 organizations, most of them correct behaviour. `policy_state` moving from
    documented_unapproved to approved changes nothing, yet that signal plainly does drive the plan
    at other values; reporting it is crying wolf, and a harness that cries wolf trains people to
    ignore it.

    A signal is ignored only if EVERY value it can hold produces the identical plan. That is a real
    and serious defect: the customer is asked a question, spends thought on it, and it can never
    affect the answer — which costs their time and buys trust the system has not earned.
    """
    findings = []
    for signal, value in signals.items():
        if signal not in CONSEQUENTIAL_SIGNALS:
            continue
        domain = domain_of(signal, value)
        if len(domain) < 2:
            continue

        shapes = set()
        for candidate in domain:
            changed = dict(signals)
            changed[signal] = candidate
            try:
                shape = shape_of(replan(changed))
            except Exception:  # noqa: BLE001, S112 — a crash is reported by the caller's probe
                continue
            shapes.add((shape.task_ids, tuple(sorted(shape.priorities.items()))))

        if len(shapes) == 1:
            findings.append(
                CounterfactualFinding(
                    "consequential_answer_ignored",
                    Perturbation(signal, value, f"any of {domain}"),
                    f"'{signal}' produces the IDENTICAL plan for every value it can take "
                    f"({domain}) — the customer is asked a question that can never change the "
                    f"answer",
                )
            )
    return findings


@dataclass
class CounterfactualReport:
    """Every probe run against one organization, and what each produced."""

    seed: int
    probes: int = 0
    findings: list[CounterfactualFinding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.findings

    def render(self) -> str:
        header = f"seed {self.seed}: {self.probes} probe(s), {len(self.findings)} finding(s)"
        return "\n".join(
            [header, *(f"    [{f.kind}] {f.detail}" for f in self.findings)]
        )


def analyse_sensitivity(
    seed: int,
    signals: dict[str, Any],
    replan: Any,
) -> CounterfactualReport:
    """Probe one organization's decision surface.

    `replan` maps a full signal dict to an applicability — injected rather than imported so this
    module stays testable without the engine, and so the same analysis can later be pointed at a
    different generator.
    """
    report = CounterfactualReport(seed=seed)
    before = shape_of(replan(signals))
    report.findings.extend(find_ignored_signals(signals, replan))

    for perturbation in all_perturbations(signals):
        report.probes += 1
        changed = dict(signals)
        changed[perturbation.signal] = perturbation.after
        try:
            after = shape_of(replan(changed))
        except Exception as exc:  # noqa: BLE001 — a perturbation that crashes IS a finding
            report.findings.append(
                CounterfactualFinding(
                    "perturbation_crashed",
                    perturbation,
                    f"{perturbation.describe()} raised {type(exc).__name__}: {exc}",
                )
            )
            continue
        report.findings.extend(judge_change(perturbation, before, after))

    return report


# --- binding to the real engine --------------------------------------------------------------


def engine_replanner(engine: Any, value_types: dict[str, str]) -> Any:
    """A `replan` bound to the real decision engine.

    Calls `analyze()` directly rather than replaying the interview: the interview is ADAPTIVE, so
    changing one answer changes which questions follow, and the comparison would stop being "one
    variable moved" and become "two plans from two different conversations".
    """
    from governance_discovery.signal import Signal, SignalSet

    def replan(signals: dict[str, Any]) -> Any:
        signal_set = SignalSet()
        for key, value in signals.items():
            value_type = value_types.get(key)
            if value_type is None:
                continue  # a signal the transcript never typed cannot be rebuilt faithfully
            signal_set = signal_set.with_signal(Signal(key=key, value_type=value_type, value=value))
        return analyze(signal_set, engine)

    return replan


def sensitivity_of_scenario(seed: int, *, engine: Any, turns: list[Any]) -> CounterfactualReport:
    """Probe the decision surface around one scenario's real answers."""
    signals = {
        turn.question_id.removeprefix("q:"): turn.answer
        for turn in turns
        if not turn.skipped and turn.answer is not None
    }
    value_types = {
        turn.question_id.removeprefix("q:"): turn.value_type
        for turn in turns
        if not turn.skipped
    }
    return analyse_sensitivity(seed, signals, engine_replanner(engine, value_types))
