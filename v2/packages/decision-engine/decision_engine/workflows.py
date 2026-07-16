"""The workflow catalog — one workflow per intent, with its routing/budget defaults. This
is the "workflows as data" table from the architecture (§4): a class maps to exactly one
workflow, and the workflow declares whether retrieval runs, how many passes, whether a
reranker or human gate is needed, the context budget, and the default target profiles when
no framework is named in the request.

The data itself now lives in the shared Intent Registry (`pipeline_contracts.
intent_registry`) — the single source of truth for per-intent behaviour across the whole
pipeline. This module is the decision-engine view of it, keeping the historic
`Workflow` / `WORKFLOWS` names importable.
"""

from __future__ import annotations

from pipeline_contracts.intent_registry import INTENT_REGISTRY, RoutingPolicy

from decision_engine.models import Intent

Workflow = RoutingPolicy

WORKFLOWS: dict[Intent, Workflow] = {intent: spec.routing for intent, spec in INTENT_REGISTRY.items()}

# The composite context-budget ceiling for multi-step plans, so a decomposed request can't
# request unbounded context.
MAX_MULTISTEP_BUDGET = 80

__all__ = ["Workflow", "WORKFLOWS", "MAX_MULTISTEP_BUDGET"]
