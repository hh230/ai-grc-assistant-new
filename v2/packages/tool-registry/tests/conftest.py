"""Shared fixtures + a reference Tool. `EchoTool` is a trivial read-only Tool used only to
exercise the Registry — it is test scaffolding, not a production tool, so it lives here rather
than in the package's public surface (which stays contracts + registry only)."""

from dataclasses import dataclass

import pytest
from pipeline_contracts import TenantContext
from tool_registry import SideEffectProfile, ToolRegistry, ToolSpec


@dataclass(frozen=True)
class EchoTool:
    """A reference Tool: echoes its payload. Satisfies the `Tool` protocol structurally."""

    spec: ToolSpec

    def invoke(self, payload: dict[str, object], tenant: TenantContext) -> dict[str, object]:
        return {"echo": payload, "tenant": tenant.tenant_id}


def make_tool(
    name: str,
    version: int = 1,
    *,
    side_effect: SideEffectProfile = SideEffectProfile.READ_ONLY,
    required_roles: tuple[str, ...] = (),
) -> EchoTool:
    return EchoTool(
        ToolSpec(
            name=name,
            version=version,
            side_effect=side_effect,
            required_roles=required_roles,
        )
    )


@pytest.fixture
def tenant() -> TenantContext:
    # Only used to exercise a resolved tool's `invoke` — the catalog itself needs no tenant.
    return TenantContext(tenant_id="org_acme", principal_id="u1", roles=("analyst",))


@pytest.fixture
def registry() -> ToolRegistry:
    return ToolRegistry()
