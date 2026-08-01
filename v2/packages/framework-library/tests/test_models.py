"""The pure domain: lookups by code / theme / keyword, and clean serialization."""

from __future__ import annotations

from framework_library import Control, Framework, Requirement


def _fw() -> Framework:
    return Framework(
        id="framework:demo",
        name="Demo",
        version="1",
        controls=(
            Control(id="demo:A.1", code="A.1", title="Access control", domain="Organizational"),
            Control(id="demo:A.2", code="A.2", title="Secure authentication",
                    domain="Technological"),
            Control(id="demo:A.3", code="A.3", title="Logging", domain="Technological"),
        ),
    )


def test_get_by_code_is_case_insensitive() -> None:
    fw = _fw()
    assert fw.get("a.2") is fw.controls[1]
    assert fw.get("A.9") is None


def test_by_domain_returns_all_in_theme() -> None:
    fw = _fw()
    tech = fw.by_domain("technological")
    assert tuple(c.code for c in tech) == ("A.2", "A.3")


def test_search_matches_code_or_title() -> None:
    fw = _fw()
    assert tuple(c.code for c in fw.search("auth")) == ("A.2",)   # title
    assert tuple(c.code for c in fw.search("A.1")) == ("A.1",)    # code
    assert fw.search("nonexistent") == ()
    assert fw.search("   ") == ()                                  # blank → no matches


def test_domains_are_distinct_in_first_seen_order() -> None:
    assert _fw().domains == ("Organizational", "Technological")


def test_control_serializes_nested_requirements() -> None:
    control = Control(
        id="demo:A.1", code="A.1", title="Access control",
        requirements=(Requirement(code="A.1", text="shall restrict access"),),
    )
    data = control.to_dict()
    assert data["code"] == "A.1"
    assert data["requirements"] == [{"code": "A.1", "text": "shall restrict access"}]
