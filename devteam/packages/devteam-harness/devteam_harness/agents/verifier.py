"""Verifier — decides whether results are sound across a population.

A thin adapter over the invariants, deliberately: there must be exactly ONE definition of
"correct" in this harness. A Verifier with its own opinion would drift from the invariants and
start disagreeing with the campaign runner about the same scenario.

Its ONE responsibility: run a RANGE of seeds and report what is wrong.
(Regression runs a recorded LIST of seeds — same conversion, shared in `base.findings_for_seed`.)
"""

from __future__ import annotations

from devteam_harness.agents.base import AgentReport, Severity, findings_for_seed

AGENT = "verifier"


def run(*, count: int, start_seed: int = 0) -> AgentReport:
    report = AgentReport(agent=AGENT)
    for offset in range(count):
        findings, ok = findings_for_seed(start_seed + offset, AGENT)
        report.bump("scenarios")
        report.findings.extend(findings)
        report.bump("crashed", sum(1 for f in findings if f.severity is Severity.CRASH))
        report.bump("violations", sum(1 for f in findings if f.severity is Severity.INVARIANT))
        if ok:
            report.bump("passed")
    return report
