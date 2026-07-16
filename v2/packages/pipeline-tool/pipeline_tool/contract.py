"""The explicit contract between a Tool invoked as a **mission step** and the executor that
maps its result to a `StepResult`.

Making this a named, single-sourced contract — rather than a dict shape shared by convention
between `PipelineTool` (which writes it) and `RegistryExecutor` (which reads it) — is what lets
**any** future Tool (SQL, Document, Risk, Workflow, …) plug into the Mission Engine's execution
path with **no change to `RegistryExecutor`**: a tool that produces a `ToolStepResult` is
mappable, uniformly.

This module is deliberately **mission-agnostic**: it imports no `mission_engine`. A tool builds
a `ToolStepResult` and serializes it with `as_payload()`; the executor reconstructs it with
`from_payload()` and is the *only* side that knows how to turn it into a `StepResult`. Keeping
the mission mapping on the executor means a tool never depends on the Mission Engine — it stays
callable by any of the six callers (CLAUDE.md §9).
"""

from __future__ import annotations

from dataclasses import dataclass

# The payload keys the executor sends to *any* mission-step tool. `INSTRUCTION` is the step's
# single opaque instruction (mirroring `PlanStep.instruction`/`StepRequest.instruction`), which
# each tool interprets in its own terms — a neutral key, not a pipeline-specific one.
PAYLOAD_INSTRUCTION = "instruction"
PAYLOAD_TRACE_ID = "trace_id"
# The mission this step runs within (ADR 0042 §12.2). The executor puts the mission id here so
# the tool can stamp the pipeline's events/audit with it — the tool never imports mission-engine.
PAYLOAD_MISSION_ID = "mission_id"


@dataclass(frozen=True)
class ToolStepResult:
    """The standard result a Tool returns when invoked as a mission step. `output` is the
    human-facing result text/summary; `source_ids` and `confidence` carry grounding when the
    tool has any (empty/`None` when it does not — e.g. a SQL tool); `warnings` are non-fatal
    notes. `ok=False` marks a failed run, which the Mission Engine turns into a fail-safe."""

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
        partial result degrades safely instead of crashing the executor."""
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
