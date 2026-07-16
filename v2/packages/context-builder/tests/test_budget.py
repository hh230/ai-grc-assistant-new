"""Token budgeting: counting, whole-block trimming, balanced fill."""

from __future__ import annotations

from context_builder.budget import HeuristicTokenCounter, assign_token_counts, enforce_budget, estimate_tokens
from context_builder.models import BlockRole, ContextSection, TokenBudget
from context_builder.builder import blocks_from_context
from tests.conftest import make_chunk, make_context


def _section(title, role, *blocks):
    return ContextSection(title=title, role=role, blocks=list(blocks))


def _blocks(n, words_each, role=BlockRole.REQUIREMENT):
    text = " ".join(["word"] * words_each)
    bs = blocks_from_context(make_context([make_chunk(f"c{i}", text, document_id=f"d{i}") for i in range(n)]))
    for b in bs:
        b.role = role
    return bs


def test_estimate_tokens_is_positive_and_monotonic():
    assert estimate_tokens("") == 0
    assert estimate_tokens("hello world") >= 1
    assert estimate_tokens("a b c d e f") > estimate_tokens("a b")


def test_trimming_drops_whole_blocks_never_truncates():
    counter = HeuristicTokenCounter()
    blocks = _blocks(5, 100)  # each ~130 tokens
    assign_token_counts(blocks, counter)
    per = blocks[0].token_count
    budget = TokenBudget(max_tokens=per * 2 + 1)  # room for exactly 2
    kept, trimmed = enforce_budget([_section("R", BlockRole.REQUIREMENT, *blocks)], budget)
    surviving = [b for s in kept for b in s.blocks]
    assert len(surviving) == 2 and trimmed == 3
    assert all(b.text.count("word") == 100 for b in surviving)  # untruncated
    assert budget.used_tokens <= budget.max_tokens


def test_empty_sections_are_removed():
    counter = HeuristicTokenCounter()
    blocks = _blocks(1, 10000)  # one giant block
    assign_token_counts(blocks, counter)
    budget = TokenBudget(max_tokens=5)  # nothing fits
    kept, trimmed = enforce_budget([_section("R", BlockRole.REQUIREMENT, *blocks)], budget)
    assert kept == [] and trimmed == 1


def test_balanced_fill_gives_both_sides_representation():
    counter = HeuristicTokenCounter()
    a = _blocks(10, 20, role=BlockRole.REQUIREMENT)
    b = _blocks(10, 20, role=BlockRole.EVIDENCE)
    assign_token_counts(a + b, counter)
    per = a[0].token_count
    budget = TokenBudget(max_tokens=per * 6)  # room for 6 total
    sec_a = _section("Side A", BlockRole.REQUIREMENT, *a)
    sec_b = _section("Side B", BlockRole.EVIDENCE, *b)
    kept, _ = enforce_budget([sec_a, sec_b], budget, balanced=True)
    counts = {s.title: len(s.blocks) for s in kept}
    # round-robin → 3 and 3, not 6 and 0
    assert counts["Side A"] == 3 and counts["Side B"] == 3


def test_sequential_fill_honours_section_priority():
    counter = HeuristicTokenCounter()
    a = _blocks(10, 20, role=BlockRole.REQUIREMENT)
    b = _blocks(10, 20, role=BlockRole.EVIDENCE)
    assign_token_counts(a + b, counter)
    per = a[0].token_count
    budget = TokenBudget(max_tokens=per * 6)
    kept, _ = enforce_budget(
        [_section("Side A", BlockRole.REQUIREMENT, *a), _section("Side B", BlockRole.EVIDENCE, *b)],
        budget, balanced=False,
    )
    counts = {s.title: len(s.blocks) for s in kept}
    assert counts.get("Side A") == 6 and "Side B" not in counts  # priority section fills first
