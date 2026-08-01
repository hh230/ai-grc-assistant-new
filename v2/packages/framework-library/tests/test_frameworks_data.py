"""The bundled library ships **three real frameworks as data** — ISO 27001:2022, CIS v8, NIST CSF
2.0 — loaded with zero framework-specific code (CLAUDE.md §13). Adding each was a data file only."""

from __future__ import annotations

import pytest
from framework_library import ControlLibraryTool, FrameworkLibrary
from pipeline_contracts import TenantContext
from tool_registry import PAYLOAD_INSTRUCTION, ToolStepResult

_EXPECTED = {
    "framework:iso_27001": ("ISO/IEC 27001:2022", 93),
    "framework:cis": ("CIS Critical Security Controls v8", 18),
    "framework:nist_csf": ("NIST Cybersecurity Framework 2.0", 22),
}


def test_all_bundled_frameworks_load_with_expected_shape(library: FrameworkLibrary) -> None:
    assert set(library.framework_ids) == set(_EXPECTED)
    for fid, (name, count) in _EXPECTED.items():
        fw = library.get(fid)
        assert fw.name == name
        assert len(fw.controls) == count


def test_nist_categories_are_themed_by_function(library: FrameworkLibrary) -> None:
    nist = library.get("framework:nist_csf")
    assert nist.domains == ("Govern", "Identify", "Protect", "Detect", "Respond", "Recover")
    assert nist.get("PR.AA").title == "Identity Management, Authentication, and Access Control"


def test_cis_controls_resolve_by_code(library: FrameworkLibrary) -> None:
    cis = library.get("framework:cis")
    assert cis.get("3").title == "Data Protection"
    assert cis.get("18").title == "Penetration Testing"


def test_the_tool_serves_a_non_default_framework(library: FrameworkLibrary) -> None:
    # Same tool class, pointed at CIS — no code change (the frameworks-as-data payoff).
    tool = ControlLibraryTool(library, default_framework_id="framework:cis")
    tenant = TenantContext(tenant_id="org_acme", principal_id="u1")
    result = ToolStepResult.from_payload(tool.invoke({PAYLOAD_INSTRUCTION: "5"}, tenant))
    assert "5 Account Management" in result.output
    assert result.source_ids == ("cis_v8:5",)


def test_keyword_search_works_across_a_data_only_framework(library: FrameworkLibrary) -> None:
    tool = ControlLibraryTool(library, default_framework_id="framework:nist_csf")
    tenant = TenantContext(tenant_id="org_acme", principal_id="u1")
    result = ToolStepResult.from_payload(tool.invoke({PAYLOAD_INSTRUCTION: "recovery"}, tenant))
    assert set(result.source_ids) == {"nist_csf:RC.RP", "nist_csf:RC.CO"}


@pytest.mark.parametrize("fid", list(_EXPECTED))
def test_every_framework_has_unique_ids_and_codes(library: FrameworkLibrary, fid: str) -> None:
    controls = library.get(fid).controls
    assert len({c.id for c in controls}) == len(controls)
    assert len({c.code for c in controls}) == len(controls)
