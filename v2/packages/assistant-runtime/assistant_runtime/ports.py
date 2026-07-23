"""The one port the Assistant reaches the Core through (ADR 0046 §2).

`MissionDriver` is the *single* seam between the product layer and the frozen Core. It is exactly
the one method the Assistant needs from the Core's `MissionRuntime` — `run_transition` — as a
`Protocol` the Assistant owns. The frozen `mission-integration.MissionRuntime` satisfies it
structurally (it has that method), so:

- the Assistant depends only on `mission-engine` (for the `MissionEngine` it drives inside a
  transition) and `pipeline-contracts` — **not** on `mission-integration` or `mission-store`;
- a spy/fake driver can be injected in unit tests with no database;
- there is **no reverse dependency** into the Core — the arrow points one way, Assistant → Core.

This is a port the *Assistant* owns, not a new Core interface — the Core is untouched.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable

if TYPE_CHECKING:  # type-only; avoids importing the engine at module load beyond what's needed
    from collections.abc import Callable

    from mission_engine import MissionEngine

T = TypeVar("T")


@runtime_checkable
class MissionDriver(Protocol):
    """Drive one Mission Engine transition inside one atomic unit of work, returning `apply`'s
    result. Matches `MissionRuntime.run_transition`; the Assistant depends on nothing more."""

    def run_transition(self, apply: Callable[[MissionEngine], T]) -> T: ...
