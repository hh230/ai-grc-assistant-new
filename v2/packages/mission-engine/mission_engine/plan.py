"""The plan — a persisted, versioned, first-class artifact, never LLM text (ADR 0042 §12.6).

Every Mission has a plan: a `simple` mission is exactly a plan of one read-only step, a
`composite` mission a plan of many. In later phases the plan is *produced* by the
Orchestrator's planning step (which may consult the LLM as a suggester, §2.2); the Mission
Engine owns *storing, versioning, and exposing* it. Re-planning creates a new `Plan` version
on the same mission — never a mutation of an accepted plan.

`execution_profile` is an **attribute derived from the plan**, not a type and not a separate
execution path (ADR 0042 §11): a plan is `simple` iff it has exactly one step and no step
requires a human gate; otherwise it is `composite`. Adding scope to a `simple` mission is a
re-plan, not a type change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from pipeline_contracts import dataclass_dict

from mission_engine.errors import PlanError
from mission_engine.ids import new_step_id


class ExecutionProfile(str, Enum):
    SIMPLE = "simple"
    COMPOSITE = "composite"


@dataclass(frozen=True)
class PlanStep:
    """One step of a plan: a unit of work the executor runs behind the `ExecutionPort`.

    `consequential` declares a side-effecting step that must pass a human gate *before* it
    runs (ADR 0042 §5, §12.5); a read-only step never gates. `instruction` is the opaque
    payload the executor interprets — for the Pipeline Tool (a later step) it will carry the
    grounded-answer request. The Mission Engine never inspects `instruction`: it dispatches,
    it does not reason (§3)."""

    description: str = ""
    instruction: str = ""
    consequential: bool = False
    id: str = field(default_factory=new_step_id)

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)


@dataclass(frozen=True)
class Plan:
    """An immutable plan version: an ordered tuple of steps plus a version number. Frozen, so
    a plan is never edited in place; `next_version` produces a successor (ADR 0042 §12.6)."""

    steps: tuple[PlanStep, ...]
    version: int = 1

    def __post_init__(self) -> None:
        if not self.steps:
            raise PlanError("a plan must have at least one step")

    @property
    def execution_profile(self) -> ExecutionProfile:
        if len(self.steps) == 1 and not self.has_gate:
            return ExecutionProfile.SIMPLE
        return ExecutionProfile.COMPOSITE

    @property
    def has_gate(self) -> bool:
        return any(step.consequential for step in self.steps)

    def next_version(self, steps: tuple[PlanStep, ...]) -> Plan:
        """The re-plan operation: a new version on the same mission, higher version number."""
        return Plan(steps=steps, version=self.version + 1)

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self, extra={"execution_profile": self.execution_profile.value})


def single_step_plan(instruction: str, description: str = "") -> Plan:
    """The canonical `simple` mission plan: exactly one read-only step (ADR 0042 §11). This is
    what a trivial grounded question ("what does NCA ECC say about MFA?") becomes — a Mission
    from birth, not a Query that is later promoted."""
    return Plan(steps=(PlanStep(description=description, instruction=instruction),))
