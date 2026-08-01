"""Rasheed V2 Context Builder (Phase 10).

Transforms a Retrieval Engine `RetrievedContext` into a structured, citation-preserving
`ContextPackage` — deduplicated, parent-expanded, merged, workflow-ordered, token-budgeted,
and validated. No prompting, no LLM, no answers, no RAG.
"""

from context_builder.engine import ContextBuilder
from context_builder.expansion import CorpusParentResolver, ParentResolver
from context_builder.models import (
    BlockRole,
    BuildMetrics,
    ContextBlock,
    ContextPackage,
    ContextSection,
    TokenBudget,
    WorkflowPolicy,
    BUDGET_PRESETS,
)
from context_builder.validator import ValidationResult, validate

__all__ = [
    "ContextBuilder",
    "ContextPackage",
    "ContextSection",
    "ContextBlock",
    "BlockRole",
    "WorkflowPolicy",
    "TokenBudget",
    "BuildMetrics",
    "BUDGET_PRESETS",
    "CorpusParentResolver",
    "ParentResolver",
    "validate",
    "ValidationResult",
]
