from __future__ import annotations

import pytest
from devteam_agents import (
    AgentTool,
    DeveloperAgent,
    Foreman,
    MapCapabilityResolver,
    MonitorAgent,
    QaAgent,
    ReviewerAgent,
    SecurityAgent,
    build_agent_registry,
)
from devteam_ci import PackageResult
from devteam_protocol import (
    Agent,
    AgentArtifact,
    AgentCapability,
    AgentFinding,
    AgentHandoff,
    AgentRequest,
    AgentRole,
    AgentVerdict,
    FindingSeverity,
)
from devteam_tools import APPLY_PATCH, COMMIT_CHANGES, OPEN_PR, PUSH_BRANCH
from pipeline_contracts import TenantContext
from tool_registry.result import PAYLOAD_INSTRUCTION, PAYLOAD_PRIOR_CONTEXT, ToolStepResult


def _tenant() -> TenantContext:
    return TenantContext(tenant_id="platform", principal_id="foreman")


def _green() -> list[PackageResult]:
    return [PackageResult("a", 0, "3 passed"), PackageResult("b", 0, "2 passed")]


def _one_fail() -> list[PackageResult]:
    return [PackageResult("a", 0, "3 passed"), PackageResult("b", 1, "1 failed")]


def _no_findings() -> list[AgentFinding]:
    return []


def _alerts() -> list[AgentFinding]:
    return [AgentFinding(kind="error_spike", severity=FindingSeverity.HIGH, summary="errors up")]


def _no_patch(_request: AgentRequest) -> list[AgentArtifact]:
    return []


def _with_patch(_request: AgentRequest) -> list[AgentArtifact]:
    return [
        AgentArtifact(kind="diagnosis", title="root cause", content="null deref in parser"),
        AgentArtifact(kind="diff", title="fix", content="--- a\n+++ b"),
    ]


def _review_payload(qa_summary: str) -> dict[str, object]:
    return {PAYLOAD_INSTRUCTION: "review", PAYLOAD_PRIOR_CONTEXT: qa_summary}


def test_all_agents_realize_the_protocol() -> None:
    assert isinstance(QaAgent(_green), Agent)
    assert isinstance(ReviewerAgent(), Agent)
    assert isinstance(Foreman(), Agent)
    assert isinstance(MonitorAgent(_no_findings), Agent)
    assert isinstance(SecurityAgent(_no_findings), Agent)
    assert isinstance(DeveloperAgent(_no_patch), Agent)


def test_qa_agent_reports_green_and_proceeds() -> None:
    result = QaAgent(_green).handle(AgentRequest(role=AgentRole.QA, intent="qa", tenant=_tenant()))
    assert result.ok is True
    assert result.decision is not None and result.decision.verdict is AgentVerdict.PROCEED
    assert not result.findings
    assert result.artifacts[0].kind == "test_report"


def test_qa_agent_raises_a_finding_per_failing_suite() -> None:
    request = AgentRequest(role=AgentRole.QA, intent="qa", tenant=_tenant())
    result = QaAgent(_one_fail).handle(request)
    assert result.ok is True  # the step ran; the failure is carried by the finding + decision
    assert result.decision is not None and result.decision.verdict is AgentVerdict.REQUEST_CHANGES
    assert len(result.findings) == 1
    assert result.findings[0].kind == "test_failure"


def test_reviewer_approves_clean_qa_but_requests_changes_on_shortfall() -> None:
    clean = AgentHandoff(
        from_role=AgentRole.QA,
        to_role=AgentRole.REVIEWER,
        artifacts=(AgentArtifact(kind="prior_step", title="s1", content="QA: 2/2 suites green"),),
    )
    approved = ReviewerAgent().handle(
        AgentRequest(role=AgentRole.REVIEWER, intent="review", tenant=_tenant(), inbox=clean)
    )
    assert approved.decision is not None and approved.decision.verdict is AgentVerdict.APPROVE

    short = AgentHandoff(
        from_role=AgentRole.QA,
        to_role=AgentRole.REVIEWER,
        artifacts=(AgentArtifact(kind="prior_step", title="s1", content="QA: 1/2 suites green"),),
    )
    changes = ReviewerAgent().handle(
        AgentRequest(role=AgentRole.REVIEWER, intent="review", tenant=_tenant(), inbox=short)
    )
    assert changes.decision is not None and changes.decision.verdict is AgentVerdict.REQUEST_CHANGES


def test_reviewer_abstains_with_an_empty_inbox() -> None:
    result = ReviewerAgent().handle(
        AgentRequest(role=AgentRole.REVIEWER, intent="review", tenant=_tenant())
    )
    assert result.decision is not None and result.decision.verdict is AgentVerdict.ABSTAIN


def test_foreman_plans_in_capabilities_not_agents() -> None:
    plan = Foreman().plan_quality_review()
    assert [step.tool for step in plan.steps] == [
        AgentCapability.TESTING.value,
        AgentCapability.REVIEW.value,
    ]
    assert plan.execution_profile.value == "composite"  # multi-step, no gate


def test_foreman_fix_it_plan_has_a_single_gate_before_the_landing_sequence() -> None:
    plan = Foreman().plan_fix_it("null deref in parser")
    assert [step.tool for step in plan.steps] == [
        AgentCapability.IMPLEMENTATION.value,
        APPLY_PATCH,
        COMMIT_CHANGES,
        PUSH_BRANCH,
        OPEN_PR,
    ]
    # Exactly one human gate, before the first side effect — one approval lands the whole sequence.
    assert [step.tool for step in plan.steps if step.consequential] == [APPLY_PATCH]
    assert plan.has_gate is True


def test_agent_tool_runs_the_capability_agent_through_the_registry() -> None:
    # The one execution path: a plan routes PlanStep.tool = capability; the registry returns the
    # AgentTool, which resolves the capability to its agent and returns a canonical result.
    registry = build_agent_registry({AgentCapability.TESTING: QaAgent(_green)})
    tool = registry.get(AgentCapability.TESTING.value)
    result = ToolStepResult.from_payload(tool.invoke({PAYLOAD_INSTRUCTION: "qa"}, _tenant()))
    assert result.ok is True
    assert "suites green" in result.output


def test_agent_tool_hands_prior_output_to_the_agent() -> None:
    # The Reviewer reads the prior step (carried on PAYLOAD_PRIOR_CONTEXT) from its inbox: clean QA
    # yields APPROVE, a shortfall yields REQUEST_CHANGES — proving prior output reaches the agent.
    tool = AgentTool(
        AgentCapability.REVIEW, MapCapabilityResolver({AgentCapability.REVIEW: ReviewerAgent()})
    )
    green = _review_payload("QA: 2/2 suites green")
    short = _review_payload("QA: 1/2 suites green")
    approved = ToolStepResult.from_payload(tool.invoke(green, _tenant()))
    changes = ToolStepResult.from_payload(tool.invoke(short, _tenant()))
    assert approved.ok is True
    assert "approve" in approved.output.lower()
    assert "approve" not in changes.output.lower()


def test_agent_tool_fails_safe_on_an_unprovided_capability() -> None:
    tool = AgentTool(AgentCapability.TESTING, MapCapabilityResolver({}))
    with pytest.raises(KeyError):
        tool.invoke({PAYLOAD_INSTRUCTION: "x"}, _tenant())


def test_monitor_proceeds_when_quiet_and_escalates_on_alerts() -> None:
    request = AgentRequest(role=AgentRole.MONITOR, intent="watch", tenant=_tenant())
    quiet = MonitorAgent(_no_findings).handle(request)
    assert quiet.decision is not None and quiet.decision.verdict is AgentVerdict.PROCEED
    noisy = MonitorAgent(_alerts).handle(request)
    assert noisy.decision is not None and noisy.decision.verdict is AgentVerdict.ESCALATE
    assert len(noisy.findings) == 1


def test_security_proceeds_when_clean_and_blocks_on_high_severity() -> None:
    request = AgentRequest(role=AgentRole.SECURITY, intent="scan", tenant=_tenant())
    clean = SecurityAgent(_no_findings).handle(request)
    assert clean.decision is not None and clean.decision.verdict is AgentVerdict.PROCEED
    risky = SecurityAgent(_alerts).handle(request)
    assert risky.decision is not None and risky.decision.verdict is AgentVerdict.BLOCK


def test_developer_proposes_a_patch_or_abstains_without_touching_git() -> None:
    request = AgentRequest(role=AgentRole.DEVELOPER, intent="fix", tenant=_tenant())
    with_patch = DeveloperAgent(_with_patch).handle(request)
    assert with_patch.decision is not None and with_patch.decision.verdict is AgentVerdict.PROCEED
    assert any(artifact.kind == "diff" for artifact in with_patch.artifacts)

    diagnosis_only = DeveloperAgent(_no_patch).handle(request)
    assert diagnosis_only.decision is not None
    assert diagnosis_only.decision.verdict is AgentVerdict.ABSTAIN
