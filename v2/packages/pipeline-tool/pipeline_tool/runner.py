"""The narrow port the Pipeline Tool depends on (ADR 0038: the AI Orchestrator is the pipeline
composition root). `PipelineRunner` is exactly the one method the tool needs — the existing
`AIOrchestrator` satisfies it structurally, so the tool depends on the *capability*, not on the
concrete orchestrator wiring, and a test can drive it with the real pipeline behind fakes."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ai_orchestrator import PipelineResult
from pipeline_contracts import UserRequest


@runtime_checkable
class PipelineRunner(Protocol):
    """Runs one grounded pipeline pass. Satisfied by `ai_orchestrator.AIOrchestrator.run`. The
    request carries its tenant (ADR 0040 §4); `mission_id` stamps the run (ADR 0042 §12.2)."""

    def run(
        self,
        request: UserRequest,
        *,
        mission_id: str,
        trace_id: str | None = None,
    ) -> PipelineResult: ...
