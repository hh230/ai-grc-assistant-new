"""Explorer — hunts for scenarios nobody has tried yet.

Running 10,000 random organizations is not exploration if they all walk the same three paths.
This measures what has actually been *reached* — every (question, answer) pair and every distinct
path through the interview — and reports when new seeds stop buying new coverage. That plateau is
the honest signal that a population is saturated and the generator, not the count, needs to
change.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from devteam_harness.agents.base import AgentReport, Finding, Severity
from devteam_harness.organizations import generate_organization
from devteam_harness.runner import Turn, run_discovery

AGENT = "explorer"


@dataclass
class Coverage:
    """What the population has reached so far."""

    question_answers: set[tuple[str, str]] = field(default_factory=set)
    paths: set[tuple[str, ...]] = field(default_factory=set)
    questions: set[str] = field(default_factory=set)

    def observe(self, turns: Sequence[Turn]) -> int:
        """Fold one transcript in; returns how many NEW pairs it contributed."""
        before = len(self.question_answers)
        for turn in turns:
            question_id = turn.question_id
            answer = "<skipped>" if turn.skipped else repr(turn.answer)
            self.questions.add(question_id)
            self.question_answers.add((question_id, answer))
        self.paths.add(tuple(t.question_id for t in turns))
        return len(self.question_answers) - before


def run(
    *,
    count: int,
    start_seed: int = 0,
    window: int = 200,
    coverage: Coverage | None = None,
) -> tuple[AgentReport, Coverage]:
    """Explore `count` seeds, reporting coverage and flagging saturation.

    Saturation is judged by coverage *gained in the final window*, not by a trailing streak of
    unproductive seeds: one lucky late seed would reset a streak and hide a genuine plateau,
    whereas "the last N scenarios taught us nothing new" is the question actually being asked.

    Pass an existing `coverage` to continue exploring where a previous run stopped. Without it
    every run restarts from zero knowledge and can only ever report "new *within this run*",
    never "we have explored enough overall" — which is the question that matters across a
    campaign.
    """
    report = AgentReport(agent=AGENT)
    coverage = coverage if coverage is not None else Coverage()
    productive_seeds: list[int] = []
    longest_dry_streak = 0
    current_dry_streak = 0
    window = max(1, min(window, count))
    coverage_at_window_start = 0

    for offset in range(count):
        if offset == count - window:
            coverage_at_window_start = len(coverage.question_answers)

        seed = start_seed + offset
        result = run_discovery(generate_organization(seed))
        report.bump("scenarios")

        if coverage.observe(result.turns):
            productive_seeds.append(seed)
            current_dry_streak = 0
        else:
            current_dry_streak += 1
            longest_dry_streak = max(longest_dry_streak, current_dry_streak)

    gained_in_window = len(coverage.question_answers) - coverage_at_window_start
    report.stats["distinct_questions"] = len(coverage.questions)
    report.stats["distinct_question_answers"] = len(coverage.question_answers)
    report.stats["distinct_paths"] = len(coverage.paths)
    report.stats["productive_seeds"] = len(productive_seeds)
    report.stats["longest_dry_streak"] = longest_dry_streak
    report.stats["coverage_gained_in_final_window"] = gained_in_window

    if gained_in_window == 0:
        report.findings.append(
            Finding(
                agent=AGENT,
                severity=Severity.SUSPICIOUS,
                kind="coverage_plateau",
                detail=(
                    f"the last {window} scenarios added no new (question, answer) coverage — "
                    f"more scenarios of this shape will not find more; vary the generator instead"
                ),
                reproduce=f"python -m devteam_harness --team --count {count}",
            )
        )
    return report, coverage
