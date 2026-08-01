"""ToolSpec (CLAUDE.md §9, §10): stable versioned identity, declared side-effect, validated."""

import pytest
from tool_registry import InvalidToolSpec, SideEffectProfile, ToolSpec


def test_qualified_name_is_stable_and_versioned():
    spec = ToolSpec(name="analyze_control_gap", version=2)
    assert spec.qualified_name == "analyze_control_gap.v2"


def test_read_only_is_the_default_and_is_not_consequential():
    spec = ToolSpec(name="retrieve_evidence")
    assert spec.side_effect is SideEffectProfile.READ_ONLY
    assert not spec.is_consequential


def test_consequential_is_declared_not_enforced_here():
    spec = ToolSpec(name="generate_policy_draft", side_effect=SideEffectProfile.CONSEQUENTIAL)
    assert spec.is_consequential  # the Mission Engine enforces the gate, not the spec


def test_required_roles_normalize_to_a_tuple():
    spec = ToolSpec(name="t", required_roles=["admin", "auditor"])
    assert spec.required_roles == ("admin", "auditor")


@pytest.mark.parametrize("bad_name", ["", "   "])
def test_empty_name_is_rejected(bad_name):
    with pytest.raises(InvalidToolSpec):
        ToolSpec(name=bad_name)


def test_version_below_one_is_rejected():
    with pytest.raises(InvalidToolSpec):
        ToolSpec(name="t", version=0)


def test_to_dict_is_plain_json():
    data = ToolSpec(name="t", version=1, required_roles=("admin",)).to_dict()
    assert data["name"] == "t"
    assert data["side_effect"] == "read_only"
    assert data["required_roles"] == ["admin"]
