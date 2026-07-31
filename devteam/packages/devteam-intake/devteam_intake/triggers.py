"""TriggerSource — the only origin-aware layer (ADR 0063/0064).

Each realization normalizes one external event into an IntakeSignal, setting the correlation_ref at
the granularity that IS its policy: per-entity for issues/CI/Sentry (updates correlate),
per-occurrence for schedules (each is new). Two sources ship here; GitHub, Sentry, and Schedule
follow the same Port with no change elsewhere.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from assistant_runtime.intent import CapabilityIntent
from devteam_contracts import AgentFinding, FindingSeverity, platform_tenant

from devteam_intake.signal import IntakeSignal

# The mission-level capability a dev trigger asks for by default.
_QUALITY_REVIEW = "quality_review"


@runtime_checkable
class TriggerSource(Protocol):
    """Normalizes one external event into an IntakeSignal. The only place that knows a trigger's
    origin."""

    def normalize(self, raw: dict[str, object]) -> IntakeSignal: ...


class ManualRequestSource:
    """A manual owner request. Per-request correlation (each request is its own mission)."""

    origin = "manual"

    def normalize(self, raw: dict[str, object]) -> IntakeSignal:
        request = str(raw.get("request", ""))
        ref = f"manual:{raw.get('request_id') or request}"
        intent = CapabilityIntent(
            capability_id=str(raw.get("capability") or _QUALITY_REVIEW),
            confidence=1.0,
            inputs={"request": request},
        )
        return IntakeSignal(
            tenant=platform_tenant(), intent=intent, correlation_ref=ref, origin=self.origin
        )


class CIFailureSource:
    """A CI failure webhook. Per-pipeline correlation, so reruns of the same pipeline update the
    same mission rather than spawning duplicates."""

    origin = "ci"

    def normalize(self, raw: dict[str, object]) -> IntakeSignal:
        pipeline = str(raw.get("pipeline") or "unknown")
        finding = AgentFinding(
            kind="ci_failure",
            severity=FindingSeverity.HIGH,
            summary=f"CI failed: {pipeline}",
            source=self.origin,
            detail=str(raw.get("detail", "")),
        )
        intent = CapabilityIntent(
            capability_id=_QUALITY_REVIEW, confidence=1.0, inputs={"pipeline": pipeline}
        )
        return IntakeSignal(
            tenant=platform_tenant(),
            intent=intent,
            correlation_ref=f"ci:pipeline:{pipeline}",
            origin=self.origin,
            findings=(finding,),
        )
