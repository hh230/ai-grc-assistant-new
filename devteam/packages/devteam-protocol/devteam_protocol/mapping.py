"""The boundary adapters — how the collaboration protocol meets the frozen Core (ADR 0061).

Agents plug into the Mission Engine through the EXISTING ``ExecutionPort``: a dispatched step (a
``StepRequest``) becomes an ``AgentRequest``, and the ``AgentResult`` folds back into the
``StepResult`` the engine records. These two pure functions ARE that seam — no new engine, no new
lifecycle. The role a step routes to comes from ``PlanStep.tool`` (ADR 0048), resolved by the agent
executor (a realization built only after this protocol is reviewed).
"""

from __future__ import annotations

from devteam_contracts import AgentFinding
from mission_engine.ports import StepRequest, StepResult

from devteam_protocol.messages import AgentHandoff, AgentRequest, AgentResult
from devteam_protocol.roles import AgentRole


def agent_request_from_step(
    step: StepRequest,
    *,
    role: AgentRole,
    inbox: AgentHandoff | None = None,
    finding: AgentFinding | None = None,
) -> AgentRequest:
    """Build the agent-facing ``AgentRequest`` from the Core ``StepRequest`` the engine dispatched,
    reusing tenant, mission/step identity, the instruction, and the consequential flag — nothing is
    re-derived. ``role`` comes from the step's routing (``StepRequest.tool``, ADR 0048); ``inbox``
    carries the prior agent's handoff (built upstream from ``prior_results``, ADR 0051)."""
    return AgentRequest(
        role=role,
        intent=step.instruction,
        tenant=step.tenant,
        mission_id=step.mission_id,
        step_id=step.step_id,
        consequential=step.consequential,
        inbox=inbox,
        finding=finding,
    )


def agent_result_to_step(result: AgentResult, *, step_id: str) -> StepResult:
    """Fold an ``AgentResult`` down to the Core ``StepResult`` the engine records — the summary the
    lifecycle and audit need (``ok`` / ``output`` / ``source_ids`` / ``confidence`` / ``warnings``).
    Lossy by design: the richer collaboration layer (artifacts / findings / decision / handoff) is
    preserved by the Foreman and the audit trail, not forced through the seam (ADR 0042 §12.2)."""
    return StepResult(
        step_id=step_id,
        ok=result.ok,
        output=result.output,
        source_ids=result.source_ids,
        confidence=result.confidence,
        warnings=result.warnings,
    )
