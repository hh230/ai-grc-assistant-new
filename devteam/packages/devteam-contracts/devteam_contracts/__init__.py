"""Autonomous Platform Dev Team — shared contracts (ADR 0061).

Pure value objects the dev team speaks, depending only on ``pipeline_contracts``. No mission
engine, tool registry, event bus, or I/O lives here — this is the bottom of the dev-team
dependency graph, exactly as ``pipeline-contracts`` is for the v2 Core.
"""

from devteam_contracts.findings import AgentFinding, FindingSeverity
from devteam_contracts.tenant import FOREMAN_PRINCIPAL, PLATFORM_TENANT_ID, platform_tenant

__all__ = [
    "FOREMAN_PRINCIPAL",
    "PLATFORM_TENANT_ID",
    "platform_tenant",
    "AgentFinding",
    "FindingSeverity",
]
