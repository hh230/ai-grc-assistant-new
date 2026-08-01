from __future__ import annotations

import pytest
from devteam_contracts import (
    PLATFORM_TENANT_ID,
    AgentFinding,
    FindingSeverity,
    platform_tenant,
)


def test_platform_tenant_is_the_reserved_nonwildcard_tenant() -> None:
    tenant = platform_tenant()
    assert tenant.tenant_id == PLATFORM_TENANT_ID == "platform"
    assert tenant.principal_id == "devteam-foreman"
    assert tenant.roles == ()


def test_platform_tenant_accepts_a_specific_principal_and_roles() -> None:
    tenant = platform_tenant("qa-agent", roles=("platform_engineer",))
    assert tenant.principal_id == "qa-agent"
    assert tenant.has_role("platform_engineer")


def test_dev_finding_requires_kind_and_summary() -> None:
    with pytest.raises(ValueError):
        AgentFinding(kind="", severity=FindingSeverity.LOW, summary="x")
    with pytest.raises(ValueError):
        AgentFinding(kind="ci_failure", severity=FindingSeverity.LOW, summary="  ")


def test_dev_finding_serializes_with_string_severity() -> None:
    finding = AgentFinding(
        kind="ci_failure",
        severity=FindingSeverity.HIGH,
        summary="python job failed on main",
        source="monitor",
        refs=("run/123",),
    )
    data = finding.to_dict()
    assert data["kind"] == "ci_failure"
    assert data["severity"] == "high"
    assert data["summary"] == "python job failed on main"
    assert data["source"] == "monitor"
