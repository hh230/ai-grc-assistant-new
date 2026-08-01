"""``ObservingExecutor`` — the mission-bound observation point (a wrapped ``ExecutionPort``).

The frozen ``ExecutionPort`` (ADR 0042 §12.3) is where a dispatched ``StepRequest`` — carrying the
``mission_id``, ``step_id``, ``tenant``, and ``tool`` the tool boundary drops — meets the engine.
Wrapping it (exactly as ``DevToolExecutor`` and ``RegistryExecutor`` are themselves realizations of
it) is the clean seam to observe an agent step: forward the inner result unchanged, and emit the
runtime facts around it. Read-only — it never alters the mission's result.

For an agent step it emits, in order: an explicit ``AgentHandoffOccurred`` when work transfers from
a previous agent (``DECLARED`` when the previous agent's ``AgentResult.handoff`` named this one,
otherwise ``OBSERVED`` from the routing transition), then ``AgentStarted`` -> (optionally
``AgentDecisionRecorded``) -> ``AgentCompleted`` carrying the session's work-product (output
summary, artifact refs, errors). It reads that work-product from the shared ``StepCapture`` the
``ResultCourier`` fills. A non-agent step (a Git tool) has no agent, so it passes straight through
with no event and does not break a surrounding relay. Timing uses a monotonic clock for the duration
and wall-clock for the timestamp, both injectable for deterministic tests.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from devteam_protocol import AgentResult
from mission_engine.ports import ExecutionPort, StepRequest, StepResult

from devteam_observability.adapter.capture import StepCapture
from devteam_observability.adapter.roster import agent_id_for, role_for_tool
from devteam_observability.core import (
    AgentCompleted,
    AgentDecisionRecorded,
    AgentHandoffOccurred,
    AgentId,
    AgentStarted,
    ArtifactRef,
    HandoffSource,
    RuntimeObserver,
)

_SUMMARY_LIMIT = 240


class ObservingExecutor:
    """Wraps an ``ExecutionPort`` to emit agent-level runtime events around each agent step. Inject
    the inner executor (the ``DevToolExecutor``), the observer to emit to, and the shared capture;
    ``monotonic``/``wall`` are injectable clocks."""

    def __init__(
        self,
        inner: ExecutionPort,
        observer: RuntimeObserver,
        capture: StepCapture,
        *,
        monotonic: Callable[[], float] = time.perf_counter,
        wall: Callable[[], float] = time.time,
    ) -> None:
        self._inner = inner
        self._observer = observer
        self._capture = capture
        self._monotonic = monotonic
        self._wall = wall
        # Per-mission handoff tracking (the executor is the source of truth for the relay).
        self._last_agent: dict[str, AgentId] = {}
        self._declared: dict[str, tuple[AgentId, str]] = {}

    def execute(self, request: StepRequest) -> StepResult:
        role = role_for_tool(request.tool)
        if role is None:
            # A non-agent step (a Git tool): nothing to observe — run it and pass the result on.
            return self._inner.execute(request)

        agent_id = agent_id_for(role)
        tenant_id = request.tenant.tenant_id
        self._capture.clear()
        self._emit_handoff(request, agent_id, tenant_id)
        self._observer.observe(
            AgentStarted(
                mission_id=request.mission_id,
                tenant_id=tenant_id,
                occurred_at=self._wall(),
                agent=agent_id,
                step_id=request.step_id,
            )
        )
        started = self._monotonic()
        try:
            step_result = self._inner.execute(request)
        except Exception as exc:
            # The step raised: seal the session fail-safe (ok=False) so the agent is not left
            # WORKING, then re-raise for the engine to fail the mission (ADR 0042 §7).
            self._finish(
                request, agent_id, tenant_id, started, ok=False, result=None, error=repr(exc)
            )
            raise

        result = self._capture.take()
        self._finish(
            request, agent_id, tenant_id, started, ok=step_result.ok, result=result, error=None
        )
        self._record_declared_handoff(request.mission_id, result)
        return step_result

    # --- handoffs (explicit events; DECLARED preferred, OBSERVED as a marked fallback) ------

    def _emit_handoff(self, request: StepRequest, agent_id: AgentId, tenant_id: str) -> None:
        mission_id = request.mission_id
        previous = self._last_agent.get(mission_id)
        self._last_agent[mission_id] = agent_id
        if previous is None or previous == agent_id:
            return
        declared = self._declared.pop(mission_id, None)
        if declared is not None and declared[0] == agent_id:
            source, reason = HandoffSource.DECLARED, declared[1] or "declared handoff"
        else:
            source, reason = HandoffSource.OBSERVED, "mission relay"
        self._observer.observe(
            AgentHandoffOccurred(
                mission_id=mission_id,
                tenant_id=tenant_id,
                occurred_at=self._wall(),
                from_agent=previous,
                to_agent=agent_id,
                reason=reason,
                source=source,
            )
        )

    def _record_declared_handoff(self, mission_id: str, result: AgentResult | None) -> None:
        """If the agent declared a handoff, remember its target so the NEXT step's transfer is
        recorded as DECLARED rather than merely OBSERVED."""
        if result is None or result.handoff is None:
            return
        target = agent_id_for(result.handoff.to_role)
        self._declared[mission_id] = (target, result.handoff.reason)

    # --- completion / session sealing -------------------------------------------------------

    def _finish(
        self,
        request: StepRequest,
        agent_id: AgentId,
        tenant_id: str,
        started: float,
        *,
        ok: bool,
        result: AgentResult | None,
        error: str | None,
    ) -> None:
        decision = result.decision if result is not None else None
        if decision is not None:
            self._observer.observe(
                AgentDecisionRecorded(
                    mission_id=request.mission_id,
                    tenant_id=tenant_id,
                    occurred_at=self._wall(),
                    agent=agent_id,
                    verdict=decision.verdict.value,
                    rationale=decision.rationale,
                    confidence=decision.confidence,
                )
            )
        self._observer.observe(
            AgentCompleted(
                mission_id=request.mission_id,
                tenant_id=tenant_id,
                occurred_at=self._wall(),
                agent=agent_id,
                step_id=request.step_id,
                ok=ok,
                duration_ms=max(0.0, (self._monotonic() - started) * 1000.0),
                verdict=decision.verdict.value if decision is not None else None,
                output_summary=_summarize(result.output) if result is not None else "",
                artifacts=_artifact_refs(result),
                errors=_errors(result, error),
            )
        )


def _summarize(text: str, limit: int = _SUMMARY_LIMIT) -> str:
    stripped = text.strip()
    return stripped if len(stripped) <= limit else stripped[: limit - 1].rstrip() + "…"


def _artifact_refs(result: AgentResult | None) -> tuple[ArtifactRef, ...]:
    if result is None:
        return ()
    return tuple(
        ArtifactRef(kind=a.kind, title=a.title, media_type=a.media_type) for a in result.artifacts
    )


def _errors(result: AgentResult | None, error: str | None) -> tuple[str, ...]:
    """The session's errors: the raised exception if the step blew up, else the agent's warnings
    plus an explicit marker when it reported ``ok=False``."""
    if error is not None:
        return (error,)
    if result is None:
        return ()
    errors = list(result.warnings)
    if not result.ok:
        errors.append("agent reported failure (ok=False)")
    return tuple(errors)
