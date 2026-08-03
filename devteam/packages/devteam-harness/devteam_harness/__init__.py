"""AI Test Harness — synthetic organizations driven through the real Governance journey.

P1 (this slice): generate organizations, answer any adaptive question, run Discovery to
conclusion in-process. Invariants + result persistence, the full Plan flow, browser/monkey
testing, and the dashboard/CI gate land in later slices.
"""

from devteam_harness.answers import SKIP, AnswerStrategy
from devteam_harness.organizations import (
    Posture,
    SyntheticOrganization,
    generate_organization,
    generate_organizations,
)
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
    "InMemoryGovernanceStore",
    "Posture",
    "ScenarioResult",
    "SyntheticOrganization",
    "Turn",
    "build_service",
    "generate_organization",
    "generate_organizations",
    "run_discovery",
]
