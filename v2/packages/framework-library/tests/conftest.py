"""Shared fixtures. The bundled library (ISO 27001:2022) loads from data with no I/O beyond the
package's own files, so every suite runs anywhere — no database, no network, no LLM."""

from __future__ import annotations

import pytest
from framework_library import ControlLibraryTool, FrameworkLibrary
from pipeline_contracts import TenantContext
from tool_registry import ToolRegistry


@pytest.fixture
def library() -> FrameworkLibrary:
    return FrameworkLibrary.from_bundled()


@pytest.fixture
def tool(library: FrameworkLibrary) -> ControlLibraryTool:
    return ControlLibraryTool(library)


@pytest.fixture
def registry(tool: ControlLibraryTool) -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(tool)
    return reg


@pytest.fixture
def tenant() -> TenantContext:
    return TenantContext(tenant_id="org_acme", principal_id="u1", roles=("analyst",))
