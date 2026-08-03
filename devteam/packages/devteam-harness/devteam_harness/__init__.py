"""AI Test Harness — synthetic organizations driven through the real Governance journey.

P1: generate organizations, answer any adaptive question, run Discovery to conclusion in-process.
P2: assert invariants over every run and persist every result (SQLite), reproducible by seed.
The full Plan flow, browser/monkey testing, and the dashboard/CI gate land in later slices.
"""

from devteam_harness.answers import SKIP, AnswerStrategy
from devteam_harness.campaign import CheckedScenario, check_scenario, run_campaign
from devteam_harness.invariants import Violation
from devteam_harness.organizations import (
    Posture,
    SyntheticOrganization,
    generate_organization,
    generate_organizations,
)
from devteam_harness.results import ResultStore, RunSummary
from devteam_harness.runner import (
    DEFAULT_MAX_TURNS,
    ScenarioResult,
    Turn,
    build_service,
    run_discovery,
)
from devteam_harness.store import AnswerRow, InMemoryGovernanceStore

__all__ = [
    "DEFAULT_MAX_TURNS",
    "SKIP",
    "AnswerRow",
    "AnswerStrategy",
    "CheckedScenario",
    "InMemoryGovernanceStore",
    "Posture",
    "ResultStore",
    "RunSummary",
    "ScenarioResult",
    "SyntheticOrganization",
    "Turn",
    "Violation",
    "build_service",
    "check_scenario",
    "generate_organization",
    "generate_organizations",
    "run_campaign",
    "run_discovery",
]
