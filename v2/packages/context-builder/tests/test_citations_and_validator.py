"""Citation preservation helpers and the validation gate."""

from __future__ import annotations

from dataclasses import replace

from context_builder.citations import citation_is_complete, citation_key, clause_key, missing_facets, respan
from context_builder.models import BlockRole, ContextBlock, ContextPackage, ContextSection, TokenBudget
from context_builder.validator import validate
from tests.conftest import make_citation


def _block(block_id, text, citation, *, content_hash="h", tokens=5):
    return ContextBlock(
        block_id=block_id, document_id="d", role=BlockRole.REQUIREMENT, text=text, citation=citation,
        heading_path=citation.heading_path, page_start=citation.page_start, page_end=citation.page_end,
        code=citation.code, document_profile=citation.document_profile, score=1.0, confidence=1.0,
        token_count=tokens, content_hash=content_hash,
    )


def _package(blocks, *, max_tokens=1000):
    used = sum(b.token_count for b in blocks)
    section = ContextSection(title="R", role=BlockRole.REQUIREMENT, blocks=blocks)
    return ContextPackage(
        query="q", workflow="general", budget=TokenBudget(max_tokens=max_tokens, used_tokens=used),
        sections=[section] if blocks else [],
    )


def test_citation_completeness_requires_source_and_locator():
    assert citation_is_complete(make_citation())
    assert not citation_is_complete(replace(make_citation(), source_filename=""))
    # no code, no page, but has heading → still a locator
    assert citation_is_complete(make_citation(code=None, page_start=None))
    # nothing to locate
    assert not citation_is_complete(make_citation(code=None, page_start=None, heading_path=()))


def test_respan_widens_pages_and_preserves_all_other_facets():
    c = make_citation(page_start=3, page_end=3)
    widened = respan(c, 3, 5)
    assert widened.page_start == 3 and widened.page_end == 5
    assert "pp. 3–5" in widened.formatted
    assert widened.code == c.code and widened.heading_path == c.heading_path and widened.title == c.title


def test_keys_distinguish_place_vs_clause():
    a = make_citation(page_start=3, page_end=3)
    b = make_citation(page_start=4, page_end=4)
    assert citation_key(a) != citation_key(b)  # different pages → different place
    assert clause_key(a) == clause_key(b)      # same clause regardless of page


def test_missing_facets_reports_absent_fields():
    absent = missing_facets(make_citation(code=None, page_start=None))
    assert "code" in absent and "page" in absent


def test_validator_accepts_a_clean_package():
    pkg = _package([_block("a", "text a", make_citation(), content_hash="h1"),
                    _block("b", "text b", make_citation(code="A.6"), content_hash="h2")])
    result = validate(pkg)
    assert result.is_valid and result.issues == []


def test_validator_rejects_over_budget():
    pkg = _package([_block("a", "t", make_citation(), tokens=2000)], max_tokens=100)
    assert not validate(pkg).is_valid


def test_validator_rejects_duplicates():
    pkg = _package([_block("a", "same", make_citation(), content_hash="dup"),
                    _block("b", "same", make_citation(code="A.6"), content_hash="dup")])
    result = validate(pkg)
    assert not result.is_valid and any("duplicate content" in i for i in result.issues)


def test_validator_rejects_lost_citation():
    bad = replace(make_citation(), source_filename="")
    pkg = _package([_block("a", "t", bad, content_hash="h1")])
    assert not validate(pkg).is_valid


def test_validator_rejects_empty_section():
    pkg = ContextPackage(query="q", workflow="general", budget=TokenBudget(1000),
                         sections=[ContextSection(title="empty", role=BlockRole.REQUIREMENT, blocks=[])])
    result = validate(pkg)
    assert not result.is_valid and any("empty section" in i for i in result.issues)


def test_empty_package_is_valid_but_empty():
    assert validate(_package([])).is_valid
