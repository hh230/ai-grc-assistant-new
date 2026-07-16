"""Token budgeting.

Two concerns live here:

1. **Counting tokens** — behind a `TokenCounter` port so a real tokenizer (tiktoken, an LLM
   provider's counter) can be injected in a later phase without touching the builder. The
   default is a deterministic, dependency-free heuristic tuned to *over*-estimate slightly
   for mixed Arabic/English GRC text, so we never silently overflow a real model's window.

2. **Enforcing the budget** — trimming to fit while **keeping whole blocks**: we drop
   entire lowest-priority blocks rather than truncating a chunk mid-sentence (which would
   corrupt its citation's page/section span). "Prefer complete sections over partial
   chunks", per the phase spec.
"""

from __future__ import annotations

from math import ceil
from typing import Protocol

from context_builder.models import ContextBlock, ContextSection, TokenBudget


class TokenCounter(Protocol):
    def count(self, text: str) -> int: ...


def estimate_tokens(text: str) -> int:
    """Deterministic heuristic token estimate. Blends a char model (~4 chars/token) with a
    word model (~1.3 tokens/word) and takes the max, so we lean conservative rather than
    under-count. Good enough for budgeting; swappable for a real tokenizer via the port."""
    if not text:
        return 0
    chars = len(text)
    words = len(text.split())
    return max(1, ceil(chars / 4), ceil(words * 1.3))


class HeuristicTokenCounter:
    """The default `TokenCounter`. No dependencies, deterministic, language-agnostic."""

    def count(self, text: str) -> int:
        return estimate_tokens(text)


def assign_token_counts(blocks: list[ContextBlock], counter: TokenCounter) -> None:
    """Populate each block's `token_count` in place."""
    for b in blocks:
        b.token_count = counter.count(b.text)


def enforce_budget(
    sections: list[ContextSection], budget: TokenBudget, *, balanced: bool = False
) -> tuple[list[ContextSection], int]:
    """Admit blocks until the budget is exhausted, keeping whole blocks (never truncating —
    that would corrupt a citation's page/section span). Empty sections are removed.

    - **Sequential** (default): fill section-by-section in the workflow's priority order, so
      an evidence-first / requirement-first ordering is honoured and the low-priority tail
      is what gets trimmed.
    - **Balanced** (`balanced=True`, used by comparison): admit one block from each section
      in round-robin turns, so both sides of a comparison get even representation instead of
      the first side consuming the whole budget.

    Returns the surviving sections and the number of blocks trimmed.
    """
    budget.used_tokens = 0
    kept_blocks: dict[int, list[ContextBlock]] = {i: [] for i in range(len(sections))}

    if balanced:
        cursors = [0] * len(sections)
        progressed = True
        while progressed:
            progressed = False
            for i, section in enumerate(sections):
                if cursors[i] >= len(section.blocks):
                    continue
                progressed = True
                block = section.blocks[cursors[i]]
                cursors[i] += 1
                if budget.fits(block.token_count):
                    budget.used_tokens += block.token_count
                    kept_blocks[i].append(block)
    else:
        for i, section in enumerate(sections):
            for block in section.blocks:
                if budget.fits(block.token_count):
                    budget.used_tokens += block.token_count
                    kept_blocks[i].append(block)

    total_in = sum(len(s.blocks) for s in sections)
    kept: list[ContextSection] = []
    total_kept = 0
    for i, section in enumerate(sections):
        if kept_blocks[i]:
            section.blocks = kept_blocks[i]
            total_kept += len(kept_blocks[i])
            kept.append(section)
    return kept, total_in - total_kept
