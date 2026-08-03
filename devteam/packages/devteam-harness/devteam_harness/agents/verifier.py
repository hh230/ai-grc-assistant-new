"""Verifier — decides whether results are sound.

Deliberately a thin adapter over the `invariants` module rather than a second rule engine. There
must be exactly ONE definition of "correct" in this harness; a Verifier with its own private
opinion would drift from the invariants and start disagreeing with the campaign runner about the
same scenario.
"""

from __future__ import annotations

from devteam_harness.agents.base import AgentReport, Finding, Severity
from devteam_harness.campaign import check_scenario

AGENT = "verifier"


def run(*, count: int, start_seed: int = 0) -> AgentReport:
    """Verify a population, turning invariant violations into findings with repro steps."""
    report = AgentReport(agent=AGENT)

    for offset in range(count):
        seed = start_seed + offset
        checked = check_scenario(seed)
        report.bump("scenarios")

        if checked.result.error is not None:
            report.bump("crashed")
            report.findings.append(
                Finding(
                    agent=AGENT,
                    severity=Severity.CRASH,
                    kind=checked.result.error_type or "error",
                    detail=checked.result.error,
                    reproduce=f"python -m devteam_harness --seed {seed}",
                    seed=seed,
                )
            )

        for violation in checked.violations:
            report.bump("violations")
            report.findings.append(
                Finding(
                    agent=AGENT,
                    severity=Severity.INVARIANT,
                    kind=violation.name,
                    detail=violation.detail,
                    reproduce=f"python -m devteam_harness --seed {seed}",
                    seed=seed,
                )
            )

        if checked.ok:
            report.bump("passed")

    return report
