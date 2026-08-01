"""Remediation strategy + approval policy (ADR 0065) — Mission → Strategy → Approval → Execution.

These lock the owner's two S3 principles: remediation is a STRATEGY (one mission type can resolve
several ways by context, not one fixed workflow), and APPROVAL is bound to the strategy + severity,
never the mission type (read evidence → none; policy update → owner; prod merge → human; risk
acceptance → executive).
"""

from __future__ import annotations

from devteam_organization.lifecycle import (
    ApprovalRequirement,
    MissionType,
    ProblemSignal,
    RemediationPlanner,
    Severity,
    default_strategy_registry,
)


def _signal(
    mission_type: str,
    evidence: str,
    *,
    asset: str = "asset-1",
    severity: Severity = Severity.MEDIUM,
) -> ProblemSignal:
    return ProblemSignal(
        mission_type=mission_type, asset=asset, evidence_signature=evidence, severity=severity
    )


# --- strategy selection is context-driven (several strategies per mission type) ---


def test_security_selects_code_or_infra_by_context() -> None:
    registry = default_strategy_registry()
    code = registry.select(_signal(MissionType.SECURITY, "missing_header:HSTS"))
    infra = registry.select(_signal(MissionType.SECURITY, "tls_cert_expiry"))
    assert code is not None and code.id == "code_remediation"
    assert infra is not None and infra.id == "infrastructure_change"


def test_compliance_selects_policy_or_evidence_by_context() -> None:
    registry = default_strategy_registry()
    policy = registry.select(_signal(MissionType.COMPLIANCE, "policy_contradiction"))
    gap = registry.select(_signal(MissionType.COMPLIANCE, "control_unmet"))
    assert policy is not None and policy.id == "policy_update"
    assert gap is not None and gap.id == "evidence_collection"


def test_operations_selects_infra_or_runbook_by_context() -> None:
    registry = default_strategy_registry()
    infra = registry.select(_signal(MissionType.OPERATIONS, "worker_down"))
    runbook = registry.select(_signal(MissionType.OPERATIONS, "queue_backlog"))
    assert infra is not None and infra.id == "infrastructure_change"
    assert runbook is not None and runbook.id == "runbook_execution"


def test_audit_and_risk_select_their_strategies() -> None:
    registry = default_strategy_registry()
    doc = registry.select(_signal(MissionType.AUDIT, "doc_stale"))
    risk = registry.select(_signal(MissionType.RISK, "residual_high"))
    assert doc is not None and doc.id == "documentation"
    assert risk is not None and risk.id == "risk_acceptance"


def test_no_strategy_for_an_unknown_domain() -> None:
    assert default_strategy_registry().select(_signal("unknown_domain", "whatever")) is None


# --- approval is bound to the strategy + severity, NOT the mission type ---


def test_read_only_evidence_collection_needs_no_approval() -> None:
    plan = RemediationPlanner(default_strategy_registry()).plan(
        _signal(MissionType.COMPLIANCE, "control_unmet")
    )
    assert plan is not None
    assert plan.strategy_id == "evidence_collection"
    assert plan.approval.requirement is ApprovalRequirement.NONE
    assert plan.consequential is False  # read-only → no engine gate


def test_same_mission_type_different_strategy_different_approval() -> None:
    # COMPLIANCE resolves as evidence_collection (none) OR policy_update (owner): approval follows
    # the STRATEGY, not the mission type.
    planner = RemediationPlanner(default_strategy_registry())
    evidence = planner.plan(_signal(MissionType.COMPLIANCE, "control_unmet"))
    policy = planner.plan(_signal(MissionType.COMPLIANCE, "policy_outdated"))
    assert evidence is not None and evidence.approval.requires_gate is False
    assert policy is not None and policy.approval.requirement is ApprovalRequirement.OWNER
    assert policy.approval.approver == "policy_owner" and policy.consequential is True


def test_code_remediation_approval_escalates_with_severity() -> None:
    planner = RemediationPlanner(default_strategy_registry())
    high = planner.plan(_signal(MissionType.SECURITY, "missing_header", severity=Severity.HIGH))
    crit = planner.plan(_signal(MissionType.SECURITY, "missing_header", severity=Severity.CRITICAL))
    assert high is not None and high.approval.requirement is ApprovalRequirement.STANDARD
    assert crit is not None and crit.approval.requirement is ApprovalRequirement.EXECUTIVE


def test_risk_acceptance_is_executive_and_routes_ceo_when_critical() -> None:
    planner = RemediationPlanner(default_strategy_registry())
    normal = planner.plan(_signal(MissionType.RISK, "residual", severity=Severity.MEDIUM))
    crit = planner.plan(_signal(MissionType.RISK, "residual", severity=Severity.CRITICAL))
    assert normal is not None and normal.approval.requirement is ApprovalRequirement.EXECUTIVE
    assert normal.approval.approver == "risk_owner"
    assert crit is not None and crit.approval.approver == "ceo"


def test_documentation_gate_scales_with_severity() -> None:
    planner = RemediationPlanner(default_strategy_registry())
    routine = planner.plan(_signal(MissionType.AUDIT, "doc", severity=Severity.MEDIUM))
    material = planner.plan(_signal(MissionType.AUDIT, "doc", severity=Severity.HIGH))
    assert routine is not None and routine.consequential is False
    assert material is not None and material.approval.requirement is ApprovalRequirement.OWNER
    assert material.approval.approver == "audit_owner"


def test_plan_carries_instruction_and_is_none_without_a_strategy() -> None:
    planner = RemediationPlanner(default_strategy_registry())
    plan = planner.plan(_signal(MissionType.SECURITY, "cve-2024-1", asset="lib-x"))
    assert plan is not None and "lib-x" in plan.instruction
    assert planner.plan(_signal("unknown", "x")) is None


def test_signal_critical_derives_from_severity() -> None:
    assert _signal(MissionType.RISK, "x", severity=Severity.CRITICAL).critical is True
    assert _signal(MissionType.RISK, "x", severity=Severity.LOW).critical is False
