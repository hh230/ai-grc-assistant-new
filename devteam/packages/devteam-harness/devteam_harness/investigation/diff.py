"""Decision Diff — what CHANGED between two plans, not what the two plans are.

Showing "plan A" beside "plan B" does not scale. Reviewing a thousand candidate rule changes means
reading two thousand plans, and a human comparing them by eye will miss the one line that matters.
A diff is what makes that review possible at all:

    +2 tasks
    -1 task
    priority changed: establish_risk_register  medium → high
    schedule moved:   draft_policies           month_3 → week_1

This is a domain diff, not a text diff. It is expressed in the vocabulary a product owner reasons
about — tasks, priorities, schedule, dependencies — because the question being answered is
"did this change the advice, and how", not "did these bytes change".

It is also deliberately ORDER-INSENSITIVE within a timeframe. Two plans that schedule the same
tasks in the same buckets are the same advice, whatever order a list happens to hold them in;
reporting that as a difference would bury the real ones.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FieldChange:
    """One task's attribute moving — the reason a diff is more than added/removed."""

    task: str
    attribute: str
    before: Any
    after: Any

    def describe(self) -> str:
        return f"{self.attribute} changed: {self.task}  {self.before} → {self.after}"


@dataclass
class DecisionDiff:
    """Everything that changed between two plans for the same organization."""

    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changes: list[FieldChange] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.added or self.removed or self.changes)

    @property
    def magnitude(self) -> int:
        """How much moved. Used to rank candidates: a smaller diff that fixes the same defect is
        the better change, because less of the product's behaviour is put at risk."""
        return len(self.added) + len(self.removed) + len(self.changes)

    def render(self) -> str:
        if self.empty:
            return "no change"
        lines = []
        if self.added:
            lines.append(f"+{len(self.added)} task(s): {', '.join(sorted(self.added))}")
        if self.removed:
            lines.append(f"-{len(self.removed)} task(s): {', '.join(sorted(self.removed))}")
        lines.extend(f"  {change.describe()}" for change in self.changes)
        return "\n".join(lines)


# Attributes worth diffing: the ones that change what a human is asked to DO, when, and in what
# order. Wording keys are excluded on purpose — a renamed translation key is not a decision change.
COMPARED_ATTRIBUTES: tuple[tuple[str, str], ...] = (
    ("priority", "priority"),
    ("timeframe_bucket", "schedule"),
    ("effort_size", "effort"),
)


def diff_plans(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> DecisionDiff:
    """Compare two plans as ADVICE."""
    before_by_id = {str(item["id"]): item for item in before}
    after_by_id = {str(item["id"]): item for item in after}

    diff = DecisionDiff(
        added=sorted(set(after_by_id) - set(before_by_id)),
        removed=sorted(set(before_by_id) - set(after_by_id)),
    )

    for task in sorted(set(before_by_id) & set(after_by_id)):
        old, new = before_by_id[task], after_by_id[task]
        for key, label in COMPARED_ATTRIBUTES:
            if old.get(key) != new.get(key):
                diff.changes.append(FieldChange(task, label, old.get(key), new.get(key)))

        old_deps = sorted(str(d) for d in old.get("depends_on_item_ids") or ())
        new_deps = sorted(str(d) for d in new.get("depends_on_item_ids") or ())
        if old_deps != new_deps:
            diff.changes.append(FieldChange(task, "dependencies", old_deps, new_deps))

    return diff


@dataclass
class PopulationDiff:
    """The same diff, aggregated over many organizations.

    A rule change is judged by its effect on a POPULATION, never on one example — a change that
    helps one organization and quietly harms fifty is the failure mode this exists to expose.
    """

    scenarios: int = 0
    unchanged: int = 0
    diffs: dict[int, DecisionDiff] = field(default_factory=dict)

    def add(self, seed: int, diff: DecisionDiff) -> None:
        self.scenarios += 1
        if diff.empty:
            self.unchanged += 1
        else:
            self.diffs[seed] = diff

    @property
    def affected(self) -> int:
        return len(self.diffs)

    @property
    def total_magnitude(self) -> int:
        return sum(diff.magnitude for diff in self.diffs.values())

    def render(self, *, examples: int = 3) -> str:
        lines = [
            (
                f"{self.affected}/{self.scenarios} organization(s) affected, "
                f"{self.total_magnitude} total change(s)"
            )
        ]
        for seed, diff in list(self.diffs.items())[:examples]:
            lines.append(f"  seed {seed}:")
            lines.extend(f"    {line}" for line in diff.render().splitlines())
        return "\n".join(lines)
