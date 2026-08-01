"""`CreateMissionCommand` — the first **create** behavior of the product (Slice S7).

Every command before this *mutated* an existing mission (approve/reject/start), so they share
the `MissionCommand` template (load → …). Create is different: **there is no mission to load — it
makes one.** So it is a standalone command with its own short sequence:

    define (product type + scope → Core goal + plan)  →  create (+ plan, idempotent)  →  project

- **`define`** goes through a `MissionDefinitionProvider` — a Mission *type* is a plan factory, and
  what comes back is the whole *definition* `(goal, plan)`, product language translated to the Core.
- **`create`** goes through a `MissionCreator` (Core `create` + `plan`, idempotent by key).
- **`project`** records the creation into the Mission List projection — the product `type`/`scope`
  the Core does not store — so the new mission appears on every read surface with no special path.

**No Draft is persisted.** The Reality Gate confirmed the Core creates a `Mission` directly (no
`DRAFT` state); the input form that fed this command was Presentation State, gone once the mission
exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mission_application.contracts import (
    CommandContext,
    MissionCreator,
    MissionDefinitionProvider,
    ProjectionPort,
)


@dataclass(frozen=True)
class CreateMissionInputs:
    """What the user chose: a Mission type (one of the 6), a scope, optional documents, and the
    idempotency key from the request. `document_ids` is carried for the record; the plan factory
    scopes evidence to the tenant's knowledge, so it needs only the scope today."""

    mission_type: str
    scope: str
    document_ids: tuple[str, ...] = ()
    idempotency_key: str = ""


@dataclass(frozen=True)
class CreatedMission:
    """The subject the creation projection records: the new mission + the product metadata the Core
    does not store (`type`/`scope`). Carried through the generic `ProjectionPort`, so no new
    projection contract is needed — the same seam approve/reject project through."""

    mission: Any
    mission_type: str
    scope: str = field(default="")


@dataclass(frozen=True)
class MissionCreatedResult:
    """The create outcome — richer than a bare `CommandResult` because the review station shows a
    plan summary: how many `steps` the mission will run, and how many `human_approvals` (gates) it
    will need. Both are counted from the plan the command just built, in product terms (a count of
    decisions, never the internal `consequential` flag per step)."""

    mission_id: str
    status: str
    steps: int
    human_approvals: int


class CreateMissionCommand:
    """Create a new, planned mission from a type + scope. Standalone (not a `MissionCommand`)."""

    def __init__(
        self,
        *,
        definer: MissionDefinitionProvider,
        creator: MissionCreator,
        projection: ProjectionPort[Any],
    ) -> None:
        self._definer = definer
        self._creator = creator
        self._projection = projection

    def execute(self, context: CommandContext, inputs: CreateMissionInputs) -> MissionCreatedResult:
        # Practitioner + type ∈ the 6 are enforced at the API boundary; tenant scoping travels on
        # the context. Nothing to authorize here beyond that (role enforcement is deferred).
        tenant = context.tenant_context()
        goal, plan = self._definer.define(inputs.mission_type, inputs.scope, tenant)
        mission = self._creator.create(goal, plan, tenant, idempotency_key=inputs.idempotency_key)
        self._projection.project(CreatedMission(mission, inputs.mission_type, inputs.scope))
        # The plan summary for the review station — steps to run, and human approvals (gates) it
        # will need — counted from the plan, so the user sees "what did I create?" before "how?".
        steps = tuple(plan.steps)
        return MissionCreatedResult(
            mission_id=mission.id,
            status=mission.status.value,
            steps=len(steps),
            human_approvals=sum(1 for step in steps if getattr(step, "consequential", False)),
        )
