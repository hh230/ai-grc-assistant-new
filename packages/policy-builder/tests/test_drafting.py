"""Unit tests for the pure, deterministic Policy Builder drafting engine: grounded content,
placeholder sections, and determinism.

The required-section keywords and ambiguous-phrase list below are intentionally duplicated
from ``grc_policy_analyst.quality_engine`` rather than imported — the same
independent-packages-don't-cross-depend choice ADR-0021 made for its own word-overlap helper,
so this package never breaks because a private symbol elsewhere was renamed. Keeping the
copies here documents *why* the draft template is worded the way it is: a saved draft should
visibly need human attention rather than falsely look complete to Policy Analyst's own
completeness check.
"""

from __future__ import annotations

from grc_policy_builder import ObligationForDrafting, draft_policy

# Mirrors grc_policy_analyst.quality_engine._REQUIRED_SECTIONS' keyword sets.
_REQUIRED_SECTION_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("purpose", ("purpose",)),
    ("scope", ("scope",)),
    ("ownership", ("owner", "ownership")),
    ("responsibilities", ("responsibilit",)),
    ("controls", ("control",)),
    ("review cycle", ("review cycle", "reviewed annually", "periodic review", "review period")),
    ("exceptions", ("exception", "exemption")),
)

# Mirrors grc_policy_analyst.quality_engine._AMBIGUOUS_PHRASES.
_AMBIGUOUS_PHRASES: tuple[str, ...] = (
    "as appropriate",
    "as needed",
    "where feasible",
    "where practicable",
    "may consider",
    "if possible",
    "from time to time",
    "best effort",
)


def _obligation(
    *,
    obligation_id: str = "ob-1",
    obligation_text: str = (
        "Entities shall encrypt data at rest using industry-standard algorithms."
    ),
    control_domain: str = "data_protection",
    suggested_policy_title: str = "Encryption Policy",
) -> ObligationForDrafting:
    return ObligationForDrafting(
        obligation_id=obligation_id,
        obligation_text=obligation_text,
        control_domain=control_domain,
        suggested_policy_title=suggested_policy_title,
        source_id="sa-sama",
        source_url="https://www.sama.gov.sa/circulars/1",
    )


def test_draft_title_matches_the_suggested_policy_title() -> None:
    draft = draft_policy(_obligation())
    assert draft.title == "Encryption Policy"


def test_draft_citation_matches_hunter_and_analyst_format() -> None:
    draft = draft_policy(_obligation())
    assert draft.citation == "sa-sama#ob-1"


def test_purpose_section_quotes_the_obligation_text_with_citation() -> None:
    draft = draft_policy(_obligation())
    assert "Entities shall encrypt data at rest using industry-standard algorithms." in draft.body
    assert "(sa-sama#ob-1)" in draft.body


def test_placeholder_sections_are_explicit_and_never_invented() -> None:
    draft = draft_policy(_obligation())
    assert draft.sections_requiring_human_input == (
        "scope",
        "ownership",
        "responsibilities",
        "controls",
        "review cycle",
        "exceptions",
    )
    assert draft.body.count("[Human input required") == len(draft.sections_requiring_human_input)
    # Purpose is grounded, not a placeholder.
    assert "purpose" not in draft.sections_requiring_human_input


def test_controls_section_surfaces_the_control_domain_as_a_hint_only() -> None:
    draft = draft_policy(_obligation(control_domain="access_control"))
    assert "Access control" in draft.body
    # A hint, not a fabricated specific control.
    assert "[Human input required" in draft.body.split("Controls:")[1]


def test_draft_is_deterministic() -> None:
    obligation = _obligation()
    assert draft_policy(obligation) == draft_policy(obligation)


def test_every_required_completeness_section_is_present_in_the_draft() -> None:
    """A human who saves this draft unmodified and runs Policy Analyst against it should see
    every section acknowledged as present (even though most just point back at them) — never
    a false 'missing_required_section' finding for a section Policy Builder already named."""
    draft = draft_policy(_obligation())
    lowered = draft.body.lower()
    for section_name, keywords in _REQUIRED_SECTION_KEYWORDS:
        assert any(keyword in lowered for keyword in keywords), section_name


def test_draft_never_uses_analyst_flagged_ambiguous_language() -> None:
    draft = draft_policy(_obligation())
    lowered = draft.body.lower()
    for phrase in _AMBIGUOUS_PHRASES:
        assert phrase not in lowered
