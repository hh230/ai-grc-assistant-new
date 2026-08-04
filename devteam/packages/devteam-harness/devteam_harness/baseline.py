"""The regression gate — what makes this harness usable before every release.

A gate that fails on *any* finding is useless here, because one real product defect is currently
known and unfixed (`plan_dependencies_exist`, ~17% of organizations). Wired naively, the gate
would be red forever, and a permanently red gate is ignored within a week — at which point the
harness stops protecting anything.

So the gate compares against a **committed baseline** of what is already known to fail, and
answers the question that actually matters before a release:

    did this change make anything WORSE than it already was?

Three ways to be worse, all failures:
  - a finding kind that is not in the baseline at all  (something new broke)
  - a known kind occurring more often than the baseline (something got worse)
  - a coverage gap                                     (we did not actually check)

And one that is not a failure but must never pass silently: a known kind that has DISAPPEARED.
That usually means someone fixed it — good — but it can equally mean the check stopped running.
Either way the baseline is now wrong, and a stale baseline is a gate that has quietly stopped
gating. It is reported, and the gate tells you to refresh it.

The baseline is a committed file, reviewed like code. Raising it is a deliberate act with a diff
and a reviewer — not something a flaky run can do by accident.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from devteam_harness.agents.reporter import Report
from devteam_harness.dashboard import DID_NOT_RUN_KINDS

BASELINE_VERSION = 1


@dataclass(frozen=True)
class Comparison:
    """What changed relative to the baseline."""

    new_kinds: dict[str, int] = field(default_factory=dict)
    worsened: dict[str, tuple[int, int]] = field(default_factory=dict)
    disappeared: dict[str, int] = field(default_factory=dict)
    coverage_gaps: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Whether this run may ship. `disappeared` is deliberately NOT a failure — a fix should
        never block a release — but it does make the baseline stale, which is reported."""
        return not (self.new_kinds or self.worsened or self.coverage_gaps)

    @property
    def baseline_is_stale(self) -> bool:
        return bool(self.disappeared)

    def render(self) -> str:
        lines: list[str] = []
        for kind, count in sorted(self.new_kinds.items()):
            lines.append(f"  NEW       {kind}  x{count}  (not in the baseline — this is a regression)")
        for kind, (was, now) in sorted(self.worsened.items()):
            lines.append(f"  WORSE     {kind}  {was} -> {now}")
        for kind, count in sorted(self.coverage_gaps.items()):
            lines.append(f"  NOT RUN   {kind}  x{count}  (coverage did not execute — not a pass)")
        for kind, was in sorted(self.disappeared.items()):
            lines.append(f"  FIXED?    {kind}  was x{was}, now absent — refresh the baseline")

        if not lines:
            return "gate: PASS — nothing worse than the baseline"
        verdict = "PASS (baseline stale)" if self.ok else "FAIL"
        return f"gate: {verdict}\n" + "\n".join(lines)


def counts_from(report: Report) -> dict[str, int]:
    """Findings per kind. Kinds, not individual findings: a run over 500 organizations and a run
    over 1000 produce different totals for the same health, so the baseline records counts but the
    comparison treats an increase as meaningful only against a like-for-like run."""
    return {finding_class.kind: finding_class.count for finding_class in report.classes}


def write_baseline(report: Report, path: Path, *, scenarios: int) -> Path:
    """Record what is known to fail today. A deliberate, reviewable act.

    Coverage gaps are REFUSED. A baseline records known product defects; recording "this check did
    not run" would bake a blind spot into the gate permanently, which is the precise failure this
    package exists to prevent. The first generated baseline tried to do exactly that — it picked
    up a `route_unreachable` timeout caused by load on the machine — so the filter is not
    hypothetical.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    known = {
        kind: count
        for kind, count in counts_from(report).items()
        if kind not in DID_NOT_RUN_KINDS
    }
    path.write_text(
        json.dumps(
            {
                "version": BASELINE_VERSION,
                # Recorded so a comparison against a differently-sized run can be rejected rather
                # than silently mis-read: 7 violations in 40 scenarios is not 7 in 1000.
                "scenarios": scenarios,
                "known_failing": known,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def compare(report: Report, baseline_path: Path, *, scenarios: int) -> Comparison:
    """Compare a run against the committed baseline.

    A missing baseline is treated as "nothing is known to fail", so the first run of a new gate is
    strict rather than permissive. Being wrongly red is recoverable in one command; being wrongly
    green is how a regression ships.
    """
    known: dict[str, int] = {}
    recorded_scenarios = scenarios
    if baseline_path.is_file():
        data = json.loads(baseline_path.read_text(encoding="utf-8"))
        known = dict(data.get("known_failing", {}))
        recorded_scenarios = int(data.get("scenarios", scenarios))

    current = counts_from(report)
    # A run of a different size cannot be compared count-for-count, so counts are normalised to
    # the baseline's scale before asking "did this get worse".
    scale = (recorded_scenarios / scenarios) if scenarios else 1.0

    new_kinds = {kind: count for kind, count in current.items() if kind not in known}
    worsened = {}
    for kind, count in current.items():
        if kind in known and round(count * scale) > known[kind]:
            worsened[kind] = (known[kind], round(count * scale))

    return Comparison(
        new_kinds=new_kinds,
        worsened=worsened,
        disappeared={kind: was for kind, was in known.items() if kind not in current},
        coverage_gaps={
            kind: count for kind, count in current.items() if kind in DID_NOT_RUN_KINDS
        },
    )
