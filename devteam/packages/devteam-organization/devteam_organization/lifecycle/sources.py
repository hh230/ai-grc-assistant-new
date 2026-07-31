"""Real evidence sources — verify a problem against a live re-observation (ADR 0065, S4b-2b-2b).

The clearing source is honest: to check a problem is gone, re-fetch its connector and re-run that
connector's emitter — if the problem's ``correlation_ref`` is no longer emitted, the originating
evidence is gone (SATISFIED); if it is still emitted, it persists (UNSATISFIED); if the connector
cannot be reached, we cannot confirm (UNAVAILABLE) and the problem stays open. The same connector
that detected the problem verifies its closure. The execution sources (CI, runtime, human) are
injected by the host — connector-only domains reuse the clearing source.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from devteam_organization.lifecycle.correlation import ProblemSignal
from devteam_organization.lifecycle.emission import ProblemEmitter, default_emitters
from devteam_organization.lifecycle.resolution import Evidence, EvidenceSource, EvidenceSources


def build_evidence_sources(
    *,
    connector_fetch: Callable[[str], Mapping[str, object] | None],
    emitters: tuple[ProblemEmitter, ...] | None = None,
    ci_green: EvidenceSource | None = None,
    runtime_healthy: EvidenceSource | None = None,
    human_confirmed: EvidenceSource | None = None,
) -> EvidenceSources:
    """Build the real evidence sources. ``connector_fetch`` re-reads a connector's OK data (the host
    passes a use_cache=False fetch); the emitters re-derive whether a problem still shows. Execution
    sources (CI, runtime, human) are injected — an unwired one reports UNAVAILABLE, so a domain that
    needs it stays open until the host provides it."""
    chosen = emitters if emitters is not None else default_emitters()
    by_connector = {emitter.connector_id: emitter for emitter in chosen}

    def connector_cleared(signal: ProblemSignal) -> Evidence:
        emitter = by_connector.get(signal.connector_id)
        if emitter is None:
            return Evidence.unavailable("connector", f"no emitter for {signal.connector_id!r}")
        data = connector_fetch(signal.connector_id)
        if data is None:
            return Evidence.unavailable("connector", f"{signal.connector_id} unavailable")
        still_present = any(
            emitted.correlation_ref == signal.correlation_ref for emitted in emitter.emit(data)
        )
        if still_present:
            return Evidence.unsatisfied("connector", "the evidence still shows")
        return Evidence.satisfied("connector", "the originating evidence is gone")

    def _unwired(role: str) -> EvidenceSource:
        return lambda _signal: Evidence.unavailable(role, "not wired")

    return EvidenceSources(
        connector_cleared=connector_cleared,
        ci_green=ci_green if ci_green is not None else _unwired("ci"),
        runtime_healthy=runtime_healthy if runtime_healthy is not None else _unwired("runtime"),
        # Connector-backed domains reuse the clearing source; the host overrides for real stores.
        evidence_present=connector_cleared,
        human_confirmed=human_confirmed if human_confirmed is not None else _unwired("human"),
        documentation_reviewed=connector_cleared,
    )
