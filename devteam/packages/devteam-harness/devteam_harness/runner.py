"""Drives one synthetic organization through a complete Discovery interview.

Runs against the real `DiscoverySessionService` and the real engine + bundled packs — the same
objects grc-api composes — but with the in-memory store and injected clock/id generator. No
database, no LLM, no HTTP, no browser, so thousands of scenarios run in-process and every one is
byte-for-byte reproducible from its seed.

A run is bounded by `max_turns`: an interview that will not terminate is itself a defect, and the
harness must report it as a failed scenario rather than hang forever.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from governance_discovery.engine import DiscoveryEngine
from governance_discovery.pack import load_bundled_packs
from governance_session.service import DiscoverySessionService

from devteam_harness.answers import SKIP, AnswerStrategy
from devteam_harness.organizations import SyntheticOrganization
from devteam_harness.store import InMemoryGovernanceStore

# An interview far longer than the real question set means non-termination, not a slow run.
DEFAULT_MAX_TURNS = 200


@dataclass(frozen=True)
class Turn:
    """One question/answer exchange — the transcript a failure is diagnosed from."""

    sequence: int
    question_id: str
    value_type: str
    required: bool
    answer: object
    skipped: bool


@dataclass
class ScenarioResult:
    """The full, self-describing outcome of one scenario."""

    organization: SyntheticOrganization
    concluded: bool
    turns: list[Turn] = field(default_factory=list)
    session_id: str | None = None
    # Populated only on failure — the exception type/message plus the transcript above is
    # everything needed to reproduce, since the seed regenerates the identical organization.
    error: str | None = None
    error_type: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.concluded

    @property
    def turn_count(self) -> int:
        return len(self.turns)


def build_service(store: InMemoryGovernanceStore, *, namespace: str) -> DiscoverySessionService:
    """Compose the real service over the harness store, with a deterministic clock and ids.

    `new_id` and `now` are injectable precisely so runs are reproducible — the service was
    designed with that seam, and the harness is its first non-test consumer.

    `namespace` scopes generated ids to one scenario. Without it every scenario restarts the
    counter at 1, so scenarios sharing a store collide on `id-000001` and silently overwrite each
    other's sessions — a harness that corrupts its own results would report confident nonsense.
    Ids stay a pure function of (namespace, call order), so determinism is preserved.
    """
    ids = itertools.count(1)
    clock = itertools.count(1)
    return DiscoverySessionService(
        engine=DiscoveryEngine(load_bundled_packs()),
        store=store,
        new_id=lambda: f"{namespace}-{next(ids):06d}",
        now=lambda: float(next(clock)),
    )


def run_discovery(
    organization: SyntheticOrganization,
    *,
    max_turns: int = DEFAULT_MAX_TURNS,
    store: InMemoryGovernanceStore | None = None,
) -> ScenarioResult:
    """Run one organization's interview to conclusion. Never raises — a scenario that blows up is
    a *result*, not a crash, because one bad scenario must not abort a run of thousands."""
    store = store if store is not None else InMemoryGovernanceStore()
    strategy = AnswerStrategy(organization)
    result = ScenarioResult(organization=organization, concluded=False)

    try:
        service = build_service(store, namespace=organization.tenant_id)
        session, question = service.start(organization.tenant_id)
        result.session_id = session.id

        for sequence in range(1, max_turns + 1):
            if question is None:
                # No question and not concluded means the engine has nothing eligible left but
                # never declared conclusion — a genuine engine defect, surfaced as a failure.
                break

            value = strategy.answer(question)
            skipped = value is SKIP
            if skipped:
                outcome = service.skip(session.id, organization.tenant_id, question.id)
            else:
                outcome = service.answer(
                    session.id, organization.tenant_id, question.id, value
                )

            result.turns.append(
                Turn(
                    sequence=sequence,
                    question_id=question.id,
                    value_type=question.value_type.value,
                    required=question.required,
                    answer=None if skipped else value,
                    skipped=skipped,
                )
            )

            if outcome.concluded:
                result.concluded = True
                break
            question = outcome.next_question
        else:
            result.error = f"interview did not conclude within {max_turns} turns"
            result.error_type = "NonTermination"
            return result

        if not result.concluded:
            result.error = "engine offered no further question but never concluded"
            result.error_type = "StalledInterview"
    except Exception as exc:  # noqa: BLE001 — a scenario failure is data, not a crash
        result.error = str(exc)
        result.error_type = type(exc).__name__

    return result
