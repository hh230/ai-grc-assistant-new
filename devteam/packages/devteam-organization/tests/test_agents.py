"""The organization agents — real deterministic behaviour, verdicts, artifacts, and handoffs."""

from __future__ import annotations

from devteam_contracts import AgentFinding, FindingSeverity, platform_tenant
from devteam_organization.agents import (
    CEOAgent,
    CISOAgent,
    CTOAgent,
    DevTeamAgent,
    GRCExpertAgent,
    SupervisorAgent,
)
from devteam_organization.health import HealthReport
from devteam_protocol import (
    AgentArtifact,
    AgentHandoff,
    AgentRequest,
    AgentRole,
    AgentVerdict,
)


def _request(role: AgentRole, intent: str, *, inbox: str | None = None) -> AgentRequest:
    handoff = (
        AgentHandoff(
            from_role=AgentRole.CEO,
            to_role=role,
            artifacts=(AgentArtifact(kind="prior_step", title="prior", content=inbox),),
        )
        if inbox is not None
        else None
    )
    return AgentRequest(role=role, intent=intent, tenant=platform_tenant("test"), inbox=handoff)


def test_ceo_approves_a_real_mandate_and_hands_off_to_the_cto() -> None:
    result = CEOAgent().handle(_request(AgentRole.CEO, "Harden the login flow"))
    assert result.decision is not None
    assert result.decision.verdict is AgentVerdict.APPROVE
    assert result.handoff is not None and result.handoff.to_role is AgentRole.CTO
    assert any(a.kind == "strategy" for a in result.artifacts)


def test_ceo_escalates_when_there_is_nothing_to_delegate() -> None:
    result = CEOAgent().handle(_request(AgentRole.CEO, "   "))
    assert result.decision is not None
    assert result.decision.verdict is AgentVerdict.ESCALATE


def test_cto_approves_with_a_mandate_and_requests_changes_without_one() -> None:
    approved = CTOAgent().handle(_request(AgentRole.CTO, "Add MFA", inbox="CEO mandate: do it"))
    assert approved.decision is not None and approved.decision.verdict is AgentVerdict.APPROVE
    assert any(a.kind == "architecture" for a in approved.artifacts)

    empty = CTOAgent().handle(_request(AgentRole.CTO, "Add MFA"))
    assert empty.decision is not None
    assert empty.decision.verdict is AgentVerdict.REQUEST_CHANGES


def test_cto_requests_changes_when_upstream_reports_a_shortfall() -> None:
    result = CTOAgent().handle(
        _request(AgentRole.CTO, "Add MFA", inbox="CISO: security BLOCKED — 1 finding")
    )
    assert result.decision is not None
    assert result.decision.verdict is AgentVerdict.REQUEST_CHANGES


def test_ciso_signs_off_by_default_and_blocks_on_a_high_finding() -> None:
    clean = CISOAgent().handle(_request(AgentRole.CISO, "Add MFA", inbox="CTO: plan ready"))
    assert clean.decision is not None and clean.decision.verdict is AgentVerdict.APPROVE

    def review(_req: AgentRequest) -> tuple[AgentFinding, ...]:
        return (
            AgentFinding(
                kind="vuln",
                severity=FindingSeverity.HIGH,
                summary="hardcoded secret",
                source="ciso",
                detail="found a secret",
            ),
        )

    blocked = CISOAgent(review).handle(_request(AgentRole.CISO, "Add MFA", inbox="CTO: plan"))
    assert blocked.decision is not None and blocked.decision.verdict is AgentVerdict.BLOCK
    assert len(blocked.findings) == 1


def test_grc_expert_maps_real_controls_and_hands_off_to_qa() -> None:
    result = GRCExpertAgent().handle(
        _request(AgentRole.GRC_EXPERT, "Encrypt data at rest", inbox="CISO: approved")
    )
    assert result.decision is not None and result.decision.verdict is AgentVerdict.PROCEED
    mapping = next(a for a in result.artifacts if a.kind == "grc_mapping")
    # Encryption keywords must map to real controls (ISO A.8.24, GDPR Art 32, ...).
    assert mapping.source_ids  # real control identifiers, not empty
    assert result.handoff is not None and result.handoff.to_role is AgentRole.QA


def test_grc_expert_requests_evidence_on_an_upstream_shortfall() -> None:
    result = GRCExpertAgent().handle(
        _request(AgentRole.GRC_EXPERT, "Encrypt data", inbox="CISO: security BLOCKED")
    )
    assert result.decision is not None
    assert result.decision.verdict is AgentVerdict.REQUEST_CHANGES


def test_devteam_delivers_when_clean_and_holds_on_a_shortfall() -> None:
    clean = DevTeamAgent().handle(
        _request(AgentRole.DEVTEAM, "Ship it", inbox="QA: 2/2 suites green")
    )
    assert clean.decision is not None and clean.decision.verdict is AgentVerdict.PROCEED

    held = DevTeamAgent().handle(
        _request(AgentRole.DEVTEAM, "Ship it", inbox="QA: 1/2 suites green")
    )
    assert held.decision is not None and held.decision.verdict is AgentVerdict.REQUEST_CHANGES


def test_supervisor_agent_proceeds_when_healthy_and_escalates_when_not() -> None:
    healthy = HealthReport(
        healthy=True,
        checked_at=1.0,
        agents=(),
        missions=(),
        stalled_agents=(),
        stalled_missions=(),
        summary="all healthy",
    )
    result = SupervisorAgent(lambda: healthy).handle(_request(AgentRole.SUPERVISOR, "check"))
    assert result.decision is not None and result.decision.verdict is AgentVerdict.PROCEED

    degraded = HealthReport(
        healthy=False,
        checked_at=1.0,
        agents=(),
        missions=(),
        stalled_agents=("platform:cto",),
        stalled_missions=("mis_1",),
        summary="attention: 1 stalled agent(s), 1 stalled mission(s)",
    )
    escalate = SupervisorAgent(lambda: degraded).handle(_request(AgentRole.SUPERVISOR, "check"))
    assert escalate.decision is not None and escalate.decision.verdict is AgentVerdict.ESCALATE
