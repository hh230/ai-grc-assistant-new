"""The QA agent team.

Five roles, one shared vocabulary (`Finding`). Two of them — Verifier and Regression — are thin
adapters over machinery the harness already had (invariants, seed replay), not second
implementations: there must be exactly one definition of "correct" and one way to reproduce.
The genuinely new capability lives in Explorer (coverage-driven search) and Breaker (adversarial
input and protocol abuse).
"""

from devteam_harness.agents import breaker, explorer, regression, reporter, sentry, verifier
from devteam_harness.agents.base import AgentReport, Finding, Severity
from devteam_harness.agents.reporter import Report, compile_report
from devteam_harness.agents.team import TeamOutcome, run_team

__all__ = [
    "AgentReport",
    "Finding",
    "Report",
    "Severity",
    "TeamOutcome",
    "breaker",
    "compile_report",
    "explorer",
    "regression",
    "reporter",
    "run_team",
    "sentry",
    "verifier",
]
