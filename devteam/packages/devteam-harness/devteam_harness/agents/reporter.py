"""Reporter — turns raw findings into something a human can act on.

Thousands of findings are useless if they are a flat list. This groups by (kind, severity),
counts each class, and — critically — keeps ONE concrete reproduction command per class. A single
runnable command beats a hundred near-identical stack traces, because the first thing anyone does
with a bug report is try to see it themselves.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from devteam_harness.agents.base import AgentReport, Finding, Severity

AGENT = "reporter"

# Worst first — a crash always outranks an invariant violation.
_SEVERITY_ORDER = {Severity.CRASH: 0, Severity.INVARIANT: 1, Severity.SUSPICIOUS: 2}


@dataclass
class FindingClass:
    """One distinct kind of problem, however many times it occurred."""

    kind: str
    severity: Severity
    count: int
    agents: set[str] = field(default_factory=set)
    example_detail: str = ""
    reproduce: str = ""
    seeds: list[int] = field(default_factory=list)


@dataclass
class Report:
    classes: list[FindingClass]
    stats: dict[str, dict[str, int]]
    total_findings: int

    @property
    def ok(self) -> bool:
        return self.total_findings == 0

    def render(self) -> str:
        lines: list[str] = []
        for agent, stats in sorted(self.stats.items()):
            summary = "  ".join(f"{k}={v}" for k, v in sorted(stats.items()))
            lines.append(f"[{agent}] {summary}")

        if not self.classes:
            lines.append("")
            lines.append("no findings")
            return "\n".join(lines)

        lines.append("")
        lines.append(f"{self.total_findings} finding(s) in {len(self.classes)} class(es):")
        for finding_class in self.classes:
            agents = ",".join(sorted(finding_class.agents))
            lines.append("")
            lines.append(
                f"  [{finding_class.severity.value.upper()}] {finding_class.kind}"
                f"  x{finding_class.count}  (via {agents})"
            )
            lines.append(f"    example  : {finding_class.example_detail}")
            lines.append(f"    reproduce: {finding_class.reproduce}")
            if finding_class.seeds:
                shown = ", ".join(str(s) for s in finding_class.seeds[:8])
                more = "" if len(finding_class.seeds) <= 8 else f" (+{len(finding_class.seeds) - 8} more)"
                lines.append(f"    seeds    : {shown}{more}")
        return "\n".join(lines)


def compile_report(reports: list[AgentReport]) -> Report:
    """Fold every agent's output into one classified report."""
    grouped: dict[tuple[str, Severity], list[Finding]] = defaultdict(list)
    stats: dict[str, dict[str, int]] = {}
    total = 0

    for agent_report in reports:
        stats[agent_report.agent] = dict(agent_report.stats)
        for finding in agent_report.findings:
            grouped[(finding.kind, finding.severity)].append(finding)
            total += 1

    classes = []
    for (kind, severity), findings in grouped.items():
        classes.append(
            FindingClass(
                kind=kind,
                severity=severity,
                count=len(findings),
                agents={f.agent for f in findings},
                example_detail=findings[0].detail,
                reproduce=findings[0].reproduce,
                seeds=[f.seed for f in findings if f.seed is not None],
            )
        )

    classes.sort(key=lambda c: (_SEVERITY_ORDER[c.severity], -c.count))
    return Report(classes=classes, stats=stats, total_findings=total)
