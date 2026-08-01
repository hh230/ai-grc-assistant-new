"""Parent expansion: resolver port, depth guard, no-op without a resolver, no duplication."""

from __future__ import annotations

from context_builder.builder import blocks_from_context
from context_builder.expansion import CorpusParentResolver, expand_parents
from context_builder.models import ContextBlock, role_for_profile
from retrieval_engine import CorpusChunk
from retrieval_engine.providers.corpus import InMemoryCorpus
from tests.conftest import make_chunk, make_context


def _corpus_chunk(chunk_id, text, heading_path, *, document_id="doc-iso", page_start=1, code=None):
    return CorpusChunk(
        chunk_id=chunk_id, document_id=document_id, text=text, document_profile="iso_standard",
        structure_profile="standard_clause", category="ISO", language="en", code=code,
        title=None, heading_path=tuple(heading_path), page_start=page_start, page_end=page_start,
        source_filename="iso27001.pdf", checksum=f"sum-{chunk_id}", content_type="section",
    )


def test_no_resolver_is_a_noop():
    blocks = blocks_from_context(make_context([make_chunk("a", "child text")]))
    out, added = expand_parents(blocks, None)
    assert added == 0 and out == blocks


def test_parent_heading_is_added_for_child():
    corpus = InMemoryCorpus.from_chunks([
        _corpus_chunk("parent", "Section 5 intro on access control.", ("5 Controls",), page_start=10),
        _corpus_chunk("child", "5.15 detailed rule.", ("5 Controls", "5.15 Access control"), page_start=12),
    ])
    resolver = CorpusParentResolver(corpus)
    child_block = blocks_from_context(make_context([
        make_chunk("child", "5.15 detailed rule.", heading_path=("5 Controls", "5.15 Access control")),
    ]))
    out, added = expand_parents(child_block, resolver)
    assert added == 1
    parent = next(b for b in out if b.is_parent)
    assert parent.block_id == "parent"
    assert parent.heading_path == ("5 Controls",)


def test_top_level_child_has_no_parent():
    corpus = InMemoryCorpus.from_chunks([_corpus_chunk("c", "top level", ("Only heading",))])
    resolver = CorpusParentResolver(corpus)
    blocks = blocks_from_context(make_context([make_chunk("c", "top level", heading_path=("Only heading",))]))
    _, added = expand_parents(blocks, resolver)
    assert added == 0  # depth < 2, no parent heading exists


def test_parent_already_present_is_not_duplicated():
    corpus = InMemoryCorpus.from_chunks([
        _corpus_chunk("parent", "Section 5 intro.", ("5 Controls",), page_start=10),
        _corpus_chunk("child", "5.15 rule.", ("5 Controls", "5.15 Access control"), page_start=12),
    ])
    resolver = CorpusParentResolver(corpus)
    blocks = blocks_from_context(make_context([
        make_chunk("parent", "Section 5 intro.", heading_path=("5 Controls",)),
        make_chunk("child", "5.15 rule.", heading_path=("5 Controls", "5.15 Access control")),
    ]))
    _, added = expand_parents(blocks, resolver)
    assert added == 0  # parent id already in the set


def test_expansion_cap_is_respected():
    corpus = InMemoryCorpus.from_chunks([
        _corpus_chunk(f"parent{i}", f"intro {i}", (f"H{i}",), document_id=f"d{i}", page_start=1) for i in range(5)
    ] + [
        _corpus_chunk(f"child{i}", f"rule {i}", (f"H{i}", f"H{i}.1"), document_id=f"d{i}", page_start=2) for i in range(5)
    ])
    resolver = CorpusParentResolver(corpus)
    blocks = blocks_from_context(make_context([
        make_chunk(f"child{i}", f"rule {i}", document_id=f"d{i}", heading_path=(f"H{i}", f"H{i}.1"), score=1.0 - i * 0.1)
        for i in range(5)
    ]))
    _, added = expand_parents(blocks, resolver, max_expansions=2)
    assert added == 2  # capped
