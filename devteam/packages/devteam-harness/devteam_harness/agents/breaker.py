"""Breaker — tries to break the system on purpose.

Its invariant comes straight from the service's own contract (`governance_session/errors.py`:
"never a raw exception leaks to a caller"): every hostile input must be rejected with a **typed**
`GovernanceSessionError`, which routers map to a proper status code. A raw `TypeError`/`KeyError`
escaping instead is a real defect — the API would return an unhandled 500.

The second invariant is subtler and matters more: **a rejected input must not corrupt the
session**. A system that rejects bad data but leaves state damaged is worse than one that
crashes, because the damage is silent.
"""

from __future__ import annotations

from typing import Any

from governance_session.errors import GovernanceSessionError

from devteam_harness.agents.base import AgentReport, Finding, Severity
from devteam_harness.organizations import generate_organization
from devteam_harness.runner import build_service
from devteam_harness.store import InMemoryGovernanceStore

AGENT = "breaker"

# Values chosen to attack the boundary: wrong types, extremes, encoding tricks, and payloads that
# would be dangerous if they ever reached a query or a template.
HOSTILE_VALUES: tuple[tuple[str, Any], ...] = (
    ("none", None),
    ("empty_string", ""),
    ("whitespace", "   "),
    ("wrong_type_list", []),
    ("wrong_type_dict", {}),
    ("wrong_type_bool", True),
    ("negative", -1),
    ("huge_int", 10**18),
    ("float_nan", float("nan")),
    ("float_inf", float("inf")),
    ("long_string", "A" * 10_000),
    ("null_byte", "abc\x00def"),
    ("sql_injection", "'; DROP TABLE discovery_sessions; --"),
    ("xss", "<script>alert(1)</script>"),
    # U+202E as an escape, never a literal control character in source (ruff PLE2502). Worth
    # attacking on a bilingual Arabic/English product: an RTL override that survives into a
    # rendered plan could visually reverse text a reviewer is relying on.
    ("unicode_rtl_override", "\u202egnirts desrever"),
    ("emoji", "🙈" * 50),
    ("unknown_enum_option", "definitely-not-a-valid-option"),
    ("newlines", "line1\nline2\r\nline3"),
)


def _finding(kind: str, detail: str, seed: int, severity: Severity) -> Finding:
    return Finding(
        agent=AGENT,
        severity=severity,
        kind=kind,
        detail=detail,
        reproduce=f"python -m devteam_harness --breaker-seed {seed}",
        seed=seed,
    )


def run(seed: int) -> AgentReport:
    """Attack one organization's interview from every angle we can think of."""
    report = AgentReport(agent=AGENT)
    organization = generate_organization(seed)
    store = InMemoryGovernanceStore()
    service = build_service(store, namespace=organization.tenant_id)
    session, question = service.start(organization.tenant_id)

    if question is None:
        report.findings.append(
            _finding("no_opening_question", "a fresh session offered no question", seed, Severity.INVARIANT)
        )
        return report

    # --- hostile answers to a legitimate question -------------------------------------------
    for label, value in HOSTILE_VALUES:
        report.bump("hostile_inputs_tried")
        try:
            service.answer(session.id, organization.tenant_id, question.id, value)
            # Accepting is not automatically wrong (e.g. a text question legitimately takes any
            # string) — but the session must still be coherent afterwards, checked below.
            report.bump("accepted")
        except GovernanceSessionError:
            report.bump("rejected_correctly")
        except Exception as exc:  # noqa: BLE001 — the whole point is to catch untyped escapes
            report.findings.append(
                _finding(
                    "untyped_exception",
                    f"{label} -> {type(exc).__name__}: {exc} "
                    f"(question {question.id}, type {question.value_type.value})",
                    seed,
                    Severity.CRASH,
                )
            )

        # The session must survive every rejected input, still readable and still in progress.
        current = store.get_session(session.id, organization.tenant_id)
        if current is None:
            report.findings.append(
                _finding("session_lost", f"session vanished after {label}", seed, Severity.CRASH)
            )
            return report

    # --- protocol abuse ----------------------------------------------------------------------
    _probe(report, seed, "unknown_question", lambda: service.answer(
        session.id, organization.tenant_id, "q:does-not-exist", True))

    _probe(report, seed, "unknown_session", lambda: service.answer(
        "session-does-not-exist", organization.tenant_id, question.id, True))

    # Cross-tenant read must be indistinguishable from "not found" (CLAUDE.md §20).
    _probe(report, seed, "cross_tenant_answer", lambda: service.answer(
        session.id, "some-other-tenant", question.id, True))

    _probe(report, seed, "skip_required", lambda: service.skip(
        session.id, organization.tenant_id, question.id))

    return report


def _probe(report: AgentReport, seed: int, label: str, call: Any) -> None:
    """Run one abusive call; only an untyped escape is a finding."""
    report.bump("protocol_abuses_tried")
    try:
        call()
        report.bump("accepted")
    except GovernanceSessionError:
        report.bump("rejected_correctly")
    except Exception as exc:  # noqa: BLE001
        report.findings.append(
            _finding(
                "untyped_exception",
                f"{label} -> {type(exc).__name__}: {exc}",
                seed,
                Severity.CRASH,
            )
        )
