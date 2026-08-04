"""The Decision Verifier — does the plan make SENSE?

Every other check in this harness asks "did the system work". This one asks "did the system think
correctly", which is a different question and the one that matters most in a product whose output is
advice a compliance team will act on.

The distinction is concrete. A plan can be perfectly valid by every technical measure — schema
correct, ids unique, dependencies resolvable, HTTP 200 — and still be **bad advice**:

    the organization says: no policies, no org structure, no risk assessment
    the plan says:         "review the security policy"

Nothing technical is wrong there. There is no policy to review. No type checker, no invariant about
data integrity, and no browser sweep can see it — because the defect is in the *judgement*, not in
the code.

**These are product-quality rules, not code-safety rules**, and the distinction is kept visible:
a violation here means the product gave poor advice, never that it crashed. They are reported as
their own class so a release conversation can tell "the system is broken" apart from "the system is
working and its advice is wrong" — two problems with completely different owners and fixes.

Deterministic on purpose. An LLM judge (see `judge.py`) can weigh nuance these rules cannot, but it
cannot gate a release: it is non-reproducible and cannot be argued with. These rules can do both.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# The maturity ladder every state signal moves along. Order IS the semantics: you cannot review
# what is not documented, and you cannot approve what was never drafted.
MATURITY_LADDER: tuple[str, ...] = (
    "absent",
    "verbal",
    "documented_unapproved",
    "approved",
    "reviewed_periodically",
)

# Rung at or below which an artifact does not meaningfully exist yet.
DOES_NOT_EXIST_AT_OR_BELOW = "verbal"

# What a plan item asks someone to DO, taken from the seed's verb. A plan is a list of actions, and
# the verb is what decides whether the action presupposes something that already exists.
CREATE_VERBS = frozenset({"draft", "establish", "designate", "formalize", "plan", "create"})
PRESUPPOSING_VERBS = frozenset({"review", "approve", "update", "refresh", "audit", "renew"})

# Buckets in schedule order — index comparison is how "before" is decided.
BUCKET_ORDER: tuple[str, ...] = ("week_1", "week_2", "month_1", "month_3", "month_6", "year_1")

PRIORITY_RANK: dict[str, int] = {"critical": 0, "high": 1, "medium": 2, "low": 3}
HIGH_SEVERITIES = frozenset({"critical", "high"})


@dataclass(frozen=True)
class DecisionFinding:
    """One judgement defect in one plan. `rule` groups; `detail` is the argument for why."""

    rule: str
    detail: str


@dataclass
class PlanContext:
    """Everything needed to judge one plan: what the organization said, and what it was told."""

    signals: dict[str, Any]
    plan_items: list[dict[str, Any]]
    gaps: list[dict[str, Any]]
    maturity: dict[str, Any]
    capacity: dict[str, Any]

    def verb(self, item: dict[str, Any]) -> str:
        """The action a plan item asks for, e.g. `seed:draft_foundational_policies` -> `draft`."""
        return str(item["id"]).removeprefix("seed:").split("_", 1)[0]

    def bucket_index(self, item: dict[str, Any]) -> int:
        bucket = item.get("timeframe_bucket", "")
        return BUCKET_ORDER.index(bucket) if bucket in BUCKET_ORDER else len(BUCKET_ORDER)


def _exists_yet(value: Any) -> bool:
    """Whether a signal's value means the artifact meaningfully exists.

    A ladder value at or below `verbal` means it does not: "we talk about it" is not a document
    anyone can review or approve.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value in MATURITY_LADDER:
        return MATURITY_LADDER.index(value) > MATURITY_LADDER.index(DOES_NOT_EXIST_AT_OR_BELOW)
    # Unknown shape — do not invent a judgement about it.
    return True


def _creates_signal(context: PlanContext, signal: str) -> list[dict[str, Any]]:
    """Items in the same plan that bring `signal` into existence."""
    return [
        item
        for item in context.plan_items
        if context.verb(item) in CREATE_VERBS
        and (item.get("resolves_signal") or {}).get("signal") == signal
    ]


# --- the rules --------------------------------------------------------------------------------


def no_action_on_something_that_does_not_exist(context: PlanContext) -> list[DecisionFinding]:
    """Never ask someone to review, approve or update a thing that does not exist.

    The owner's example: an organization answers "no policies, no org structure, no risk
    assessment", and the plan says "review the security policy". There is nothing to review.

    A presupposing action is acceptable only if the artifact already exists, OR if the same plan
    creates it FIRST — a plan that says "draft the policy, then approve it" is coherent; one that
    says only "approve it" is not.
    """
    findings = []
    for item in context.plan_items:
        if context.verb(item) not in PRESUPPOSING_VERBS:
            continue
        for signal in item.get("source_signal_keys", ()):
            if signal not in context.signals or _exists_yet(context.signals[signal]):
                continue
            creators = _creates_signal(context, signal)
            if not creators:
                findings.append(
                    DecisionFinding(
                        "no_action_on_something_that_does_not_exist",
                        f"{item['id']} asks to {context.verb(item)} '{signal}', but the "
                        f"organization answered {context.signals[signal]!r} and nothing in the "
                        f"plan creates it",
                    )
                )
            elif all(
                context.bucket_index(creator) > context.bucket_index(item) for creator in creators
            ):
                findings.append(
                    DecisionFinding(
                        "no_action_on_something_that_does_not_exist",
                        f"{item['id']} ({item.get('timeframe_bucket')}) acts on '{signal}' before "
                        f"the item that creates it "
                        f"({creators[0]['id']}, {creators[0].get('timeframe_bucket')})",
                    )
                )
    return findings


def no_step_before_its_prerequisite(context: PlanContext) -> list[DecisionFinding]:
    """A plan must not schedule a task before something it depends on.

    Distinct from the `plan_dependencies_exist` invariant, which asks whether the dependency is
    *present*. This asks whether the ORDER makes sense to a human executing the plan top to bottom.
    """
    by_id = {item["id"]: item for item in context.plan_items}
    findings = []
    for item in context.plan_items:
        for dependency_id in item.get("depends_on_item_ids", ()):
            dependency = by_id.get(dependency_id)
            if dependency is None:
                continue  # a missing dependency is the invariant's finding, not this rule's
            if context.bucket_index(item) < context.bucket_index(dependency):
                findings.append(
                    DecisionFinding(
                        "no_step_before_its_prerequisite",
                        f"{item['id']} is scheduled {item.get('timeframe_bucket')} but depends on "
                        f"{dependency_id} scheduled {dependency.get('timeframe_bucket')}",
                    )
                )
    return findings


def high_risk_never_gets_low_priority(context: PlanContext) -> list[DecisionFinding]:
    """A critical or high-severity gap must not be answered with a low-priority task.

    Mis-prioritising is worse than omitting: an organization that trusts the ordering will do the
    low-priority item last, and believe it is being systematic while the worst exposure stays open.
    """
    findings = []
    for gap in context.gaps:
        severity = str(gap.get("severity", "")).lower()
        if severity not in HIGH_SEVERITIES:
            continue
        gap_signals = set(gap.get("source_signal_keys") or ())
        if not gap_signals:
            continue
        for item in context.plan_items:
            if not gap_signals & set(item.get("source_signal_keys") or ()):
                continue
            priority = str(item.get("priority", "")).lower()
            if PRIORITY_RANK.get(priority, 99) > PRIORITY_RANK["high"]:
                findings.append(
                    DecisionFinding(
                        "high_risk_never_gets_low_priority",
                        f"gap {gap.get('id', '?')} is {severity} but {item['id']} that addresses "
                        f"it is priority {priority}",
                    )
                )
    return findings


def no_duplicate_tasks(context: PlanContext) -> list[DecisionFinding]:
    """Two tasks that move the same signal to the same state are the same task, worded twice.

    Duplication is not merely untidy: it inflates the plan, makes the organization do work twice,
    and destroys trust in the plan's length as a signal of effort.
    """
    seen: dict[tuple[str, str], str] = {}
    findings = []
    for item in context.plan_items:
        resolves = item.get("resolves_signal") or {}
        key = (str(resolves.get("signal")), str(resolves.get("value")))
        if key == ("None", "None"):
            continue
        if key in seen:
            findings.append(
                DecisionFinding(
                    "no_duplicate_tasks",
                    f"{item['id']} and {seen[key]} both move {key[0]} to {key[1]}",
                )
            )
        else:
            seen[key] = item["id"]
    return findings


def an_immature_organization_gets_a_plan(context: PlanContext) -> list[DecisionFinding]:
    """An organization with nothing in place must never be handed an empty plan.

    This is the most damaging possible output: the organization least equipped to know what to do
    is told there is nothing to do, and reads it as reassurance.
    """
    if context.plan_items:
        return []
    zero_dimensions = [
        name
        for name, value in context.maturity.items()
        if isinstance(value, dict) and value.get("stars", 1) == 0
    ]
    if zero_dimensions:
        return [
            DecisionFinding(
                "an_immature_organization_gets_a_plan",
                f"empty plan for an organization scoring zero in {sorted(zero_dimensions)}",
            )
        ]
    return []


def a_plan_fits_what_the_organization_can_execute(context: PlanContext) -> list[DecisionFinding]:
    """Do not hand a small organization more work than it could ever do.

    The yardstick is the product's OWN capacity model, not an invented number: `per_period_budget`
    is what the Scheduler already believes this organization can absorb per period. A plan larger
    than the whole horizon's budget is one the organization cannot execute, and an unexecutable
    plan is abandoned rather than partially followed.
    """
    budget = context.capacity.get("per_period_budget") or {}
    if not budget:
        return []
    horizon = sum(int(value) for value in budget.values())
    if horizon and len(context.plan_items) > horizon:
        return [
            DecisionFinding(
                "a_plan_fits_what_the_organization_can_execute",
                f"{len(context.plan_items)} items for a '{context.capacity.get('tier')}' "
                f"organization whose whole-horizon budget is {horizon}",
            )
        ]
    return []


def every_critical_gap_has_a_task(context: PlanContext) -> list[DecisionFinding]:
    """A gap the system itself calls critical must produce something to DO about it.

    Telling someone they have a critical gap and handing them a plan that does not mention it is
    worse than not detecting it: the gap appears in the report, so it looks handled.

    ONLY EVALUATED WHEN THE GAP CARRIES SIGNALS. The first version of this rule also fired when a
    gap carried none — and produced 78 false positives on 300 organizations. Seed 7 is the proof:
    `gap:gov_client_without_compliance_officer` is flagged, and the plan DOES contain
    `seed:designate_compliance_owner`, which addresses it exactly. The rule simply could not see
    the link, because gaps have no signal linkage in the data model.

    Reporting "nothing addresses this" about a gap that is plainly addressed is the crying-wolf
    failure this harness treats as its own defect. The untraceable case is reported separately and
    honestly by `gaps_are_traceable_to_tasks` — as a traceability problem, which is what it is.
    """
    if not context.plan_items:
        return []  # an empty plan is `an_immature_organization_gets_a_plan`'s finding, not this one

    addressed = {
        signal
        for item in context.plan_items
        for signal in (item.get("source_signal_keys") or ())
    }
    return [
        DecisionFinding(
            "every_critical_gap_has_a_task",
            f"{gap.get('gap_id') or gap.get('id') or '?'} is {gap.get('severity')} but no plan "
            f"item addresses {sorted(set(gap.get('source_signal_keys') or ()))}",
        )
        for gap in context.gaps
        if str(gap.get("severity", "")).lower() in HIGH_SEVERITIES
        and set(gap.get("source_signal_keys") or ())
        and not (set(gap.get("source_signal_keys") or ()) & addressed)
    ]


def gaps_are_traceable_to_tasks(context: PlanContext) -> list[DecisionFinding]:
    """A gap must be linkable to the work that closes it.

    Today no gap carries `source_signal_keys`, so nothing — not this harness, not the UI, not an
    auditor — can mechanically answer "which task closes this gap?". The answer may well exist in
    someone's head; it does not exist in the data.

    That is a traceability defect, not an "unaddressed gap" defect, and the two are deliberately
    kept apart: one says the advice is wrong, this one says the advice cannot be checked. In a
    product whose value is auditability (CLAUDE.md §19), the second still matters.
    """
    return [
        DecisionFinding(
            "gaps_are_traceable_to_tasks",
            f"{gap.get('gap_id') or gap.get('id') or '?'} ({gap.get('severity')}) carries no "
            f"source signals, so no task can be mechanically linked to it",
        )
        for gap in context.gaps
        if str(gap.get("severity", "")).lower() in HIGH_SEVERITIES
        and not set(gap.get("source_signal_keys") or ())
    ]


RULES = (
    no_action_on_something_that_does_not_exist,
    no_step_before_its_prerequisite,
    high_risk_never_gets_low_priority,
    no_duplicate_tasks,
    an_immature_organization_gets_a_plan,
    a_plan_fits_what_the_organization_can_execute,
    every_critical_gap_has_a_task,
    gaps_are_traceable_to_tasks,
)


def verify_decision(context: PlanContext) -> list[DecisionFinding]:
    """Run every product-quality rule over one plan."""
    findings: list[DecisionFinding] = []
    for rule in RULES:
        findings.extend(rule(context))
    return findings


def context_from(turns: list[Any], applicability: Any) -> PlanContext:
    """Build the judgement context from what the organization ANSWERED and what it was TOLD.

    Signals come from the transcript rather than from the analysis, deliberately: the point is to
    check the plan against the organization's own words, not against the system's interpretation of
    them. Checking a system's output against its own input would let a mis-reading pass unnoticed.
    """
    signals = {
        turn.question_id.removeprefix("q:"): turn.answer
        for turn in turns
        if not turn.skipped and turn.answer is not None
    }
    return PlanContext(
        signals=signals,
        plan_items=list(applicability.plan_items),
        gaps=list(applicability.gaps or ()),
        maturity=dict(applicability.maturity or {}),
        capacity=dict(applicability.capacity or {}),
    )
