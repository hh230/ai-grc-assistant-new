"""A campaign — run N organizations, check every invariant, persist every result.

This is the unit a release gate runs: one command, one database, one verdict.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass

from devteam_harness import invariants
from devteam_harness.organizations import generate_organization
from devteam_harness.results import ResultStore, RunSummary
from devteam_harness.runner import DEFAULT_MAX_TURNS, ScenarioResult, run_discovery
from devteam_harness.store import InMemoryGovernanceStore


@dataclass(frozen=True)
class CheckedScenario:
    """A scenario plus its invariant verdict."""

    result: ScenarioResult
    violations: list[invariants.Violation]

    @property
    def ok(self) -> bool:
        return self.result.ok and not self.violations


def check_scenario(seed: int, *, max_turns: int = DEFAULT_MAX_TURNS) -> CheckedScenario:
    """Run one organization and evaluate every invariant against it.

    Reproducing any reported failure is exactly this call with the reported seed.
    """
    organization = generate_organization(seed)
    store = InMemoryGovernanceStore()
    result = run_discovery(organization, max_turns=max_turns, store=store)

    violations = list(invariants.check_transcript(result.turns))

    if result.concluded and result.session_id is not None:
        session = store.get_session(result.session_id, organization.tenant_id)
        if session is None:
            violations.append(
                invariants.Violation(
                    "concluded_session_is_readable",
                    "session missing from its own tenant after conclusion",
                )
            )
        elif session.applicability is None:
            violations.append(
                invariants.Violation(
                    "conclusion_produces_analysis", "concluded without an applicability analysis"
                )
            )
        else:
            violations.extend(invariants.check_applicability(session.applicability))

        if organization.tenant_id not in store.organization_baselines:
            violations.append(
                invariants.Violation(
                    "conclusion_writes_baseline", "no organization baseline written on conclusion"
                )
            )

    return CheckedScenario(result=result, violations=violations)


def run_campaign(
    *,
    count: int,
    start_seed: int = 0,
    store: ResultStore | None = None,
    max_turns: int = DEFAULT_MAX_TURNS,
) -> tuple[RunSummary, ResultStore]:
    """Run `count` scenarios, persisting each one. Returns the summary and the store."""
    store = store if store is not None else ResultStore()
    run_id = store.start_run(started_at=time.time(), start_seed=start_seed)

    for offset in range(count):
        seed = start_seed + offset
        checked = check_scenario(seed, max_turns=max_turns)
        result = checked.result
        store.record_scenario(
            run_id=run_id,
            seed=seed,
            tenant_id=result.organization.tenant_id,
            posture=result.organization.posture.value,
            concluded=result.concluded,
            ok=checked.ok,
            turn_count=result.turn_count,
            error_type=result.error_type,
            error=result.error,
            transcript=[asdict(turn) for turn in result.turns],
            violations=[(v.name, v.detail) for v in checked.violations],
        )

    return store.finish_run(run_id, finished_at=time.time()), store
