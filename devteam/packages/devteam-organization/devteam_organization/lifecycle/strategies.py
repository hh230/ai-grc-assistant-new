"""The concrete remediation strategies (ADR 0065). Mission type → Strategy → Approval → Execution.

Each declares WHEN it applies (by context, so one mission type can be served by several) and the
approval it needs (from the Strategy + severity, never the mission type). The owner's table:

    Mission Type   Strategy                Approval (by severity)
    security       code_remediation        standard (→ executive if critical)
    security/ops   infrastructure_change   standard (→ executive if critical)
    compliance     evidence_collection     none (read-only)
    compliance     policy_update           owner: policy_owner
    audit          documentation           none (→ owner: audit_owner if high/critical)
    risk           risk_acceptance         executive: risk_owner (→ ceo if critical)
    operations     runbook_execution       standard (→ executive if critical)
"""

from __future__ import annotations

from devteam_organization.lifecycle.correlation import ProblemSignal, Severity
from devteam_organization.lifecycle.strategy import (
    ApprovalPolicy,
    RemediationStrategy,
    StrategyRegistry,
)


class MissionType:
    """The domain a problem belongs to — an open vocabulary (a new domain is a new string, no core
    change). Broad on purpose: the specific problem lives in the asset + evidence."""

    SECURITY = "security"
    COMPLIANCE = "compliance"
    AUDIT = "audit"
    RISK = "risk"
    OPERATIONS = "operations"


_CODE_HINTS = ("header", "dependency", "vuln", "cve", "package", "code", "secret")
_INFRA_HINTS = ("tls", "cert", "worker", "runtime", "service", "host", "dns", "endpoint", "network")
_POLICY_HINTS = ("policy", "contradiction", "outdated", "procedure")


def _mentions(signal: ProblemSignal, keywords: tuple[str, ...]) -> bool:
    text = f"{signal.asset} {signal.evidence_signature}".lower()
    return any(keyword in text for keyword in keywords)


def _gated(signal: ProblemSignal, reason: str) -> ApprovalPolicy:
    """A consequential remediation: a human gate normally, the executive tier when critical."""
    if signal.severity is Severity.CRITICAL:
        return ApprovalPolicy.executive(reason=reason)
    return ApprovalPolicy.standard(reason=reason)


class CodeRemediationStrategy:
    id = "code_remediation"

    def applies_to(self, signal: ProblemSignal) -> bool:
        return signal.mission_type == MissionType.SECURITY and _mentions(signal, _CODE_HINTS)

    def approval_for(self, signal: ProblemSignal) -> ApprovalPolicy:
        # A code change reaches production; a human signs the merge (executive when critical).
        return _gated(signal, "code change merged to production requires approval")

    def instruction_for(self, signal: ProblemSignal) -> str:
        return f"Fix-it code change for {signal.asset}: {signal.evidence_signature}."


class InfrastructureChangeStrategy:
    id = "infrastructure_change"

    def applies_to(self, signal: ProblemSignal) -> bool:
        infra_domain = signal.mission_type in (MissionType.SECURITY, MissionType.OPERATIONS)
        return infra_domain and _mentions(signal, _INFRA_HINTS)

    def approval_for(self, signal: ProblemSignal) -> ApprovalPolicy:
        return _gated(signal, "infrastructure change requires approval")

    def instruction_for(self, signal: ProblemSignal) -> str:
        return f"Infrastructure change for {signal.asset}: {signal.evidence_signature}."


class PolicyUpdateStrategy:
    id = "policy_update"

    def applies_to(self, signal: ProblemSignal) -> bool:
        return signal.mission_type == MissionType.COMPLIANCE and _mentions(signal, _POLICY_HINTS)

    def approval_for(self, signal: ProblemSignal) -> ApprovalPolicy:
        # A policy edit is owned — the policy owner approves it, whatever the severity.
        return ApprovalPolicy.owner("policy_owner", "a policy change is approved by its owner")

    def instruction_for(self, signal: ProblemSignal) -> str:
        return f"Policy update for {signal.asset}: {signal.evidence_signature}."


class EvidenceCollectionStrategy:
    id = "evidence_collection"

    def applies_to(self, signal: ProblemSignal) -> bool:
        # Compliance gaps that are not policy issues are closed by collecting the missing evidence.
        return signal.mission_type == MissionType.COMPLIANCE

    def approval_for(self, signal: ProblemSignal) -> ApprovalPolicy:
        # Collecting evidence is read-only — no gate (approval binds to the strategy, not the type).
        return ApprovalPolicy.none("evidence collection is read-only")

    def instruction_for(self, signal: ProblemSignal) -> str:
        return f"Collect evidence for {signal.asset}: {signal.evidence_signature} (read-only)."


class DocumentationStrategy:
    id = "documentation"

    def applies_to(self, signal: ProblemSignal) -> bool:
        return signal.mission_type == MissionType.AUDIT

    def approval_for(self, signal: ProblemSignal) -> ApprovalPolicy:
        if signal.severity in (Severity.HIGH, Severity.CRITICAL):
            return ApprovalPolicy.owner("audit_owner", "material audit docs are owner-reviewed")
        return ApprovalPolicy.none("routine documentation is low-risk")

    def instruction_for(self, signal: ProblemSignal) -> str:
        return f"Audit documentation for {signal.asset}: {signal.evidence_signature}."


class RiskAcceptanceStrategy:
    id = "risk_acceptance"

    def applies_to(self, signal: ProblemSignal) -> bool:
        return signal.mission_type == MissionType.RISK

    def approval_for(self, signal: ProblemSignal) -> ApprovalPolicy:
        # Accepting a risk is an executive decision — the risk owner, or the CEO when critical.
        approver = "ceo" if signal.severity is Severity.CRITICAL else "risk_owner"
        return ApprovalPolicy.executive(approver, "accepting a risk requires executive sign-off")

    def instruction_for(self, signal: ProblemSignal) -> str:
        return f"Record risk acceptance for {signal.asset}: {signal.evidence_signature}."


class RunbookExecutionStrategy:
    id = "runbook_execution"

    def applies_to(self, signal: ProblemSignal) -> bool:
        return signal.mission_type == MissionType.OPERATIONS

    def approval_for(self, signal: ProblemSignal) -> ApprovalPolicy:
        return _gated(signal, "runbook execution changes running systems")

    def instruction_for(self, signal: ProblemSignal) -> str:
        return f"Run the ops runbook for {signal.asset}: {signal.evidence_signature}."


def default_strategies() -> tuple[RemediationStrategy, ...]:
    """The built-in strategies in selection order (most specific first). A new one plugs in here
    or via ``StrategyRegistry.register`` — no core change (CLAUDE.md §17)."""
    return (
        CodeRemediationStrategy(),
        InfrastructureChangeStrategy(),
        PolicyUpdateStrategy(),
        EvidenceCollectionStrategy(),
        DocumentationStrategy(),
        RiskAcceptanceStrategy(),
        RunbookExecutionStrategy(),
    )


def default_strategy_registry() -> StrategyRegistry:
    """A registry preloaded with the built-in strategies."""
    registry = StrategyRegistry()
    for strategy in default_strategies():
        registry.register(strategy)
    return registry
