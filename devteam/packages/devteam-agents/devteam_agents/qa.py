"""The QA agent (read-only) — runs the standalone test suites and reports (ADR 0061/0062).

Realizes the Agent protocol for AgentRole.QA. It uses the devteam-ci runner (injected, so it is
unit-testable without invoking uv) to run the suites, then returns an AgentResult: a test-report
artifact, an AgentFinding per failing package, and an AgentDecision (PROCEED when all green, else
REQUEST_CHANGES). Read-only — it never writes, so it needs no human gate.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from devteam_ci import PackageResult, format_report
from devteam_protocol import (
    AgentArtifact,
    AgentDecision,
    AgentFinding,
    AgentRequest,
    AgentResult,
    AgentRole,
    AgentVerdict,
    FindingSeverity,
)

# Injected so QA is testable without invoking uv; the composition root binds it to the real runner.
SuiteRunner = Callable[[], Sequence[PackageResult]]


class QaAgent:
    role = AgentRole.QA

    def __init__(self, run_suites: SuiteRunner) -> None:
        self._run_suites = run_suites

    def handle(self, request: AgentRequest) -> AgentResult:
        results = list(self._run_suites())
        failed = [r for r in results if not r.ok]
        passed = len(results) - len(failed)
        findings = tuple(
            AgentFinding(
                kind="test_failure",
                severity=FindingSeverity.HIGH,
                summary=f"suite failed: {result.name}",
                source=AgentRole.QA.value,
                detail=result.summary,
            )
            for result in failed
        )
        verdict = AgentVerdict.PROCEED if not failed else AgentVerdict.REQUEST_CHANGES
        return AgentResult(
            # The STEP succeeded (QA ran the suites); test failures are carried by the findings and
            # the decision, not by ok — a shortfall reports downstream instead of aborting.
            ok=True,
            output=f"QA: {passed}/{len(results)} suites green",
            findings=findings,
            artifacts=(
                AgentArtifact(
                    kind="test_report",
                    title="standalone suites",
                    content=format_report(results),
                    produced_by=AgentRole.QA,
                ),
            ),
            decision=AgentDecision(
                verdict=verdict,
                by_role=AgentRole.QA,
                rationale=f"{passed}/{len(results)} suites green",
            ),
        )
