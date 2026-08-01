"""Context contract behaviour: the token budget, the role/profile mapping, and the
`ContextPackage` accessors the prompt layer reads a package through.
"""

from __future__ import annotations

import json

from pipeline_contracts import (
    BUDGET_PRESETS,
    BlockRole,
    BuildMetrics,
    ContextBlock,
    ContextPackage,
    ContextSection,
    Intent,
    TokenBudget,
    WorkflowPolicy,
    role_for_profile,
)

from tests.conftest import make_citation


def make_block(block_id: str = "b1", *, role: BlockRole = BlockRole.REQUIREMENT,
               tokens: int = 10, **citation_overrides) -> ContextBlock:
    citation = make_citation(**citation_overrides)
    return ContextBlock(
        block_id=block_id,
        document_id="doc-pdpl",
        role=role,
        text="Personal data may only be processed with consent.",
        citation=citation,
        heading_path=citation.heading_path,
        page_start=citation.page_start,
        page_end=citation.page_end,
        code=citation.code,
        document_profile=citation.document_profile,
        score=0.9,
        confidence=0.8,
        token_count=tokens,
    )


# ── TokenBudget ───────────────────────────────────────────────────────────────
def test_budget_tracks_what_is_left():
    budget = TokenBudget(max_tokens=1000, used_tokens=250)
    assert budget.remaining == 750


def test_budget_fits_is_inclusive_at_the_ceiling():
    """A block that exactly fills the budget is admitted — the ceiling is a limit, not a
    thing to stay under."""
    budget = TokenBudget(max_tokens=100, used_tokens=90)
    assert budget.fits(10)
    assert not budget.fits(11)


def test_budget_fits_from_empty_and_when_full():
    assert TokenBudget(max_tokens=100).fits(100)
    assert not TokenBudget(max_tokens=100, used_tokens=100).fits(1)
    assert TokenBudget(max_tokens=100, used_tokens=100).fits(0)


def test_an_overspent_budget_reports_a_negative_remainder():
    """Reported honestly rather than clamped to zero — a builder that overshot must be able
    to see by how much."""
    assert TokenBudget(max_tokens=100, used_tokens=130).remaining == -30


def test_budget_serializes_with_its_computed_remainder():
    data = TokenBudget(max_tokens=1000, used_tokens=400).to_dict()
    assert data == {"max_tokens": 1000, "used_tokens": 400, "remaining": 600}
    json.dumps(data)


def test_the_budget_presets_are_the_documented_ladder():
    assert BUDGET_PRESETS == (2000, 4000, 8000, 16000, 32000)


# ── WorkflowPolicy ────────────────────────────────────────────────────────────
def test_workflow_policy_resolves_from_an_intent_enum_a_string_or_nothing():
    assert WorkflowPolicy.from_intent(Intent.LOOKUP) is WorkflowPolicy.LOOKUP
    assert WorkflowPolicy.from_intent("comparison") is WorkflowPolicy.COMPARISON
    assert WorkflowPolicy.from_intent(None) is WorkflowPolicy.GENERAL


def test_an_unmapped_intent_falls_back_to_the_balanced_policy():
    assert WorkflowPolicy.from_intent("risk_analysis") is WorkflowPolicy.GENERAL
    assert WorkflowPolicy.from_intent("not_a_policy") is WorkflowPolicy.GENERAL


# ── BlockRole / profiles ──────────────────────────────────────────────────────
def test_normative_sources_are_requirements_and_the_org_s_own_docs_are_not():
    for profile in ("law", "regulation", "iso_standard", "control_framework"):
        assert role_for_profile(profile) is BlockRole.REQUIREMENT
    assert role_for_profile("corporate_policy") is BlockRole.POLICY
    for profile in ("contract", "spreadsheet"):
        assert role_for_profile(profile) is BlockRole.EVIDENCE


def test_an_unknown_or_absent_profile_is_general_never_a_requirement():
    """Mis-classifying an unknown document as normative would let it outrank real law in
    every requirement-first workflow."""
    assert role_for_profile("unmapped") is BlockRole.GENERAL
    assert role_for_profile("something_new") is BlockRole.GENERAL
    assert role_for_profile(None) is BlockRole.GENERAL
    assert role_for_profile("") is BlockRole.GENERAL


def test_every_role_has_a_section_title():
    for role in BlockRole:
        assert role.title


# ── ContextSection / ContextPackage ───────────────────────────────────────────
def test_section_token_count_sums_its_blocks():
    section = ContextSection(title="Requirements", role=BlockRole.REQUIREMENT,
                             blocks=[make_block("b1", tokens=10), make_block("b2", tokens=15)])
    assert section.token_count == 25


def test_an_empty_section_counts_zero():
    assert ContextSection(title="Empty", role=BlockRole.GENERAL).token_count == 0


def test_package_flattens_blocks_across_sections_in_order():
    package = ContextPackage(
        query="q", workflow="lookup", budget=TokenBudget(max_tokens=1000),
        sections=[
            ContextSection("Requirements", BlockRole.REQUIREMENT, [make_block("b1"), make_block("b2")]),
            ContextSection("Evidence", BlockRole.EVIDENCE, [make_block("b3", role=BlockRole.EVIDENCE)]),
        ],
    )
    assert [b.block_id for b in package.all_blocks()] == ["b1", "b2", "b3"]
    assert package.token_count == 30


def test_package_exposes_a_citation_per_block():
    """One citation per block, always — the structural half of "no citation is ever lost"."""
    package = ContextPackage(
        query="q", workflow="lookup", budget=TokenBudget(max_tokens=1000),
        sections=[ContextSection("Requirements", BlockRole.REQUIREMENT,
                                 [make_block("b1", code="5-1"), make_block("b2", code="5-2")])],
    )
    assert len(package.all_citations()) == len(package.all_blocks())
    assert [c.code for c in package.all_citations()] == ["5-1", "5-2"]


def test_an_empty_package_is_valid_and_counts_nothing():
    """A conversation, or a genuine insufficient-evidence retrieval, produces an empty
    package — that is a handled outcome, not an invalid one."""
    package = ContextPackage(query="q", workflow="conversation", budget=TokenBudget(max_tokens=2000))
    assert package.all_blocks() == []
    assert package.all_citations() == []
    assert package.token_count == 0
    assert package.valid is True


def test_package_serializes_wholly_to_plain_json():
    package = ContextPackage(
        query="q", workflow="lookup", budget=TokenBudget(max_tokens=1000, used_tokens=10),
        sections=[ContextSection("Requirements", BlockRole.REQUIREMENT, [make_block("b1")])],
        metrics=BuildMetrics(chunks_in=3, chunks_selected=1),
        warnings=["trimmed"],
    )
    data = package.to_dict()
    assert data["sections"][0]["role"] == "requirement"       # enum → value
    assert data["sections"][0]["token_count"] == 10           # computed key
    assert data["sections"][0]["blocks"][0]["citation"]["code"] == "5-1"
    assert data["metrics"]["chunks_in"] == 3
    json.dumps(data)


def test_block_hides_its_internal_content_hash_from_the_wire():
    data = make_block().to_dict()
    assert "content_hash" not in data
    assert data["block_id"] == "b1"
