"""The Context Builder's data model.

The shapes themselves (`ContextPackage`, `ContextSection`, `ContextBlock`, `TokenBudget`,
`BuildMetrics`, the `WorkflowPolicy` / `BlockRole` enums, and the profile→role mapping)
are shared pipeline contracts and live in the `pipeline-contracts` package; this module
re-exports them so every existing `context_builder.models` import keeps working.

The Context Builder's whole job is to turn a `RetrievedContext` (from the Retrieval Engine)
into a **structured, citation-preserving `ContextPackage`** — never one big string:

    ContextPackage
      ├─ ContextSection (workflow-ordered: Requirements / Evidence / Policies / …)
      │    └─ ContextBlock  (one coherent unit of context)
      │         └─ Citation (document · page · heading · clause · code · profile)
      └─ BuildMetrics + TokenBudget + warnings

Citations are the retrieval contract's own `Citation` objects, carried through untouched —
so "no citation may be lost" is guaranteed by construction, not by copying fields around.

No prompting, no LLM, no answers — this package only *structures* context.
"""

from __future__ import annotations

from pipeline_contracts.context import (
    BUDGET_PRESETS,
    BlockRole,
    BuildMetrics,
    ContextBlock,
    ContextPackage,
    ContextSection,
    TokenBudget,
    WorkflowPolicy,
    role_for_profile,
)
from pipeline_contracts.retrieval import Citation

__all__ = [
    "BUDGET_PRESETS",
    "BlockRole",
    "BuildMetrics",
    "Citation",
    "ContextBlock",
    "ContextPackage",
    "ContextSection",
    "TokenBudget",
    "WorkflowPolicy",
    "role_for_profile",
]
