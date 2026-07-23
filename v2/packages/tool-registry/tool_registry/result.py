"""The standard structured result a Tool returns when invoked (CLAUDE.md §9; ADR 0049).

`ToolStepResult` is the single-sourced shape **every** mission-invokable Tool speaks — the Pipeline
Tool, and every leaf tool (Framework Library, document parsers, search, …). A caller (the executor
behind the Mission Engine's `ExecutionPort`) reconstructs it with `from_payload` and maps it to a
`StepResult`; the tool builds one and serializes it with `as_payload`. Because the contract is
single-sourced here — in the pure package every tool already depends on — a new tool is executable
with **no change to the executor**, and **without depending on the LLM/orchestrator stack** (the
reason it lives here and not in `pipeline-tool`, ADR 0049).

This module is deliberately **mission-agnostic and LLM-agnostic**: it imports nothing but the
standard library. The *how a mission executor invokes a tool* envelope (payload keys, trace/mission
ids) stays in `pipeline-tool` — that is mission knowledge, which the registry does not hold.
"""

from __future__ import annotations

from dataclasses import dataclass

# The *generic* tool-step input keys — read by leaf tools, so they live here in the pure package
# every tool depends on (a leaf tool reads them without the LLM stack, ADR 0049/0051). The
# *mission-specific* envelope keys (trace/mission id, for audit) stay in `pipeline-tool`.
#
# `PAYLOAD_INSTRUCTION` — the step's single opaque instruction (mirrors `PlanStep`/`StepRequest`).
PAYLOAD_INSTRUCTION = "instruction"
# `PAYLOAD_PRIOR_CONTEXT` — the rendered output of the steps before this one (ADR 0051), so a
# synthesis tool runs *from* prior results. Empty for a first step; ignored by tools that skip it.
PAYLOAD_PRIOR_CONTEXT = "prior_context"


@dataclass(frozen=True)
class ToolStepResult:
    """The standard result a Tool returns. `output` is the human-facing result text/summary;
    `source_ids` and `confidence` carry grounding when the tool has any (empty/`None` when it does
    not — e.g. a SQL or control-lookup tool); `warnings` are non-fatal notes. `ok=False` marks a
    failed run, which the Mission Engine turns into a fail-safe (ADR 0042 §7)."""

    ok: bool = True
    output: str = ""
    source_ids: tuple[str, ...] = ()
    confidence: float | None = None
    warnings: tuple[str, ...] = ()

    def as_payload(self) -> dict[str, object]:
        """Serialize to the generic Tool boundary (`dict[str, object]`, CLAUDE.md §9)."""
        return {
            "ok": self.ok,
            "output": self.output,
            "source_ids": list(self.source_ids),
            "confidence": self.confidence,
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_payload(cls, data: dict[str, object]) -> ToolStepResult:
        """Reconstruct from a tool's result dict, coercing each field so an ill-behaved or
        partial result degrades safely instead of crashing the caller."""
        return cls(
            ok=bool(data.get("ok", False)),
            output=_as_str(data.get("output")),
            source_ids=_as_str_tuple(data.get("source_ids")),
            confidence=_as_float_or_none(data.get("confidence")),
            warnings=_as_str_tuple(data.get("warnings")),
        )


def _as_str(value: object) -> str:
    return value if isinstance(value, str) else ""


def _as_float_or_none(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    return float(value) if isinstance(value, (int, float)) else None


def _as_str_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(item for item in value if isinstance(item, str))
    return ()
