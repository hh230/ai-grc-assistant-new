"""Validation — the final gate. A `ContextPackage` is rejected (its `valid` flag set False,
with concrete issues) when it:

  • exceeds the token budget,
  • has lost a citation (a block that no longer resolves to a real source + locator),
  • contains duplicates (same block id, or identical text under different ids),
  • contains an empty section.

An empty package (retrieval found nothing) is *valid but empty* — that is a legitimate
"insufficient evidence" outcome, not a builder failure.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from context_builder.citations import citation_is_complete
from context_builder.models import ContextPackage


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    issues: list[str] = field(default_factory=list)


def validate(package: ContextPackage) -> ValidationResult:
    issues: list[str] = []

    # 1. budget
    if package.token_count > package.budget.max_tokens:
        issues.append(
            f"over budget: {package.token_count} tokens > {package.budget.max_tokens} ceiling"
        )

    # 2. empty sections
    for section in package.sections:
        if not section.blocks:
            issues.append(f"empty section: {section.title!r}")

    blocks = package.all_blocks()

    # 3. citations preserved
    for block in blocks:
        if not citation_is_complete(block.citation):
            issues.append(f"lost/incomplete citation on block {block.block_id!r}")

    # 4. duplicates (by id and by content hash)
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    for block in blocks:
        if block.block_id in seen_ids:
            issues.append(f"duplicate block id {block.block_id!r}")
        seen_ids.add(block.block_id)
        if block.content_hash:
            if block.content_hash in seen_hashes:
                issues.append(f"duplicate content on block {block.block_id!r}")
            seen_hashes.add(block.content_hash)

    return ValidationResult(is_valid=not issues, issues=issues)
