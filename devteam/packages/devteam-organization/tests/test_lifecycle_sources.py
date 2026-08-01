"""Real evidence sources (ADR 0065) — verification re-fetches the connector and re-emits.

The clearing source is honest: a problem is cleared only when its connector no longer emits it; it
persists while the connector still shows it; and an unreachable connector is UNAVAILABLE, never a
false clear. Execution sources (CI, runtime, human) default to UNAVAILABLE until the host wires it.
"""

from __future__ import annotations

from collections.abc import Mapping

from devteam_organization.lifecycle import (
    Evidence,
    EvidenceState,
    ProblemSignal,
    build_evidence_sources,
)


def _signal(connector_id: str = "website") -> ProblemSignal:
    return ProblemSignal("operations", "https://a", "endpoint_down", connector_id=connector_id)


def _website(ok: bool) -> Mapping[str, object]:
    return {"endpoints": [{"url": "https://a", "ok": ok}]}


def test_connector_cleared_when_the_evidence_is_gone() -> None:
    # the website is healthy now → the WebsiteEmitter emits nothing → the signal is cleared
    sources = build_evidence_sources(connector_fetch=lambda _cid: _website(ok=True))
    assert sources.connector_cleared(_signal()).state is EvidenceState.SATISFIED


def test_connector_unsatisfied_while_the_evidence_still_shows() -> None:
    sources = build_evidence_sources(connector_fetch=lambda _cid: _website(ok=False))
    assert sources.connector_cleared(_signal()).state is EvidenceState.UNSATISFIED


def test_connector_unavailable_is_never_a_false_clear() -> None:
    sources = build_evidence_sources(connector_fetch=lambda _cid: None)
    assert sources.connector_cleared(_signal()).state is EvidenceState.UNAVAILABLE


def test_unknown_connector_is_unavailable() -> None:
    sources = build_evidence_sources(connector_fetch=lambda _cid: _website(ok=True))
    assert sources.connector_cleared(_signal("no-such")).state is EvidenceState.UNAVAILABLE


def test_execution_sources_default_unavailable_and_can_be_wired() -> None:
    default = build_evidence_sources(connector_fetch=lambda _cid: None)
    assert default.ci_green(_signal()).state is EvidenceState.UNAVAILABLE
    assert default.runtime_healthy(_signal()).state is EvidenceState.UNAVAILABLE

    wired = build_evidence_sources(
        connector_fetch=lambda _cid: None,
        runtime_healthy=lambda _s: Evidence("runtime", EvidenceState.SATISFIED),
    )
    assert wired.runtime_healthy(_signal()).state is EvidenceState.SATISFIED
