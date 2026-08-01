"""Tool metadata contracts (CLAUDE.md §9, §10; ADR 0042 §5).

A `ToolSpec` is the catalog entry: what a tool is, what it needs, and what it *affects* —
enough for the Orchestrator to plan with and for the Registry to govern access, **without
knowing how the tool runs**. The single load-bearing field is `side_effect`: a
`CONSEQUENTIAL` tool declares that it changes state and therefore must pass a human gate
before it runs. Critically, the tool only *declares* this — the **Mission Engine enforces the
gate** (ADR 0042 §5), and the tool never self-authorizes a consequential action (CLAUDE.md §9).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pipeline_contracts import dataclass_dict

from tool_registry.errors import InvalidToolSpec


class SideEffectProfile(str, Enum):
    """Whether invoking the tool changes state. Read-only tools never gate; consequential
    tools are gated by the Mission Engine before they run (ADR 0042 §5)."""

    READ_ONLY = "read_only"
    CONSEQUENTIAL = "consequential"


@dataclass(frozen=True)
class ToolSpec:
    """A tool's catalog entry. Immutable: a tool's identity and contract do not change under a
    running system — a new contract is a new version (CLAUDE.md §10).

    `required_roles` is **declarative metadata only**: it records the roles a tool declares it
    needs, for a *future authorization phase* to read and enforce (CLAUDE.md §10, §20). The
    Registry stores it and never evaluates it — there is no authorization system yet.
    `cost_hint` / `latency_hint_ms` are planning signals for the Orchestrator, never
    guarantees."""

    name: str
    version: int = 1
    description: str = ""
    side_effect: SideEffectProfile = SideEffectProfile.READ_ONLY
    required_roles: tuple[str, ...] = ()
    cost_hint: float = 0.0
    latency_hint_ms: float = 0.0

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise InvalidToolSpec("a tool must have a non-empty name")
        if self.version < 1:
            raise InvalidToolSpec(f"tool version must be >= 1, got {self.version}")
        object.__setattr__(self, "required_roles", tuple(self.required_roles))

    @property
    def qualified_name(self) -> str:
        """The stable, versioned identifier used everywhere a tool is referenced in logs,
        plans, and audit (`analyze_control_gap.v2`) — CLAUDE.md §21."""
        return f"{self.name}.v{self.version}"

    @property
    def is_consequential(self) -> bool:
        return self.side_effect is SideEffectProfile.CONSEQUENTIAL

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)
