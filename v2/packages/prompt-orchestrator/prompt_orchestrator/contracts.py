"""Response contracts — what a compliant answer must contain, per workflow.

The contract data itself lives in the shared Intent Registry
(`pipeline_contracts.intent_registry`) — the single source of truth for per-intent
behaviour. This module is the prompt-orchestrator view of it, keeping the historic
`CONTRACTS` / `contract_for` names.
"""

from __future__ import annotations

from pipeline_contracts import Intent, spec_for
from pipeline_contracts.intent_registry import CITATION_STYLE, INTENT_REGISTRY

from prompt_orchestrator.models import ResponseContract

CONTRACTS: dict[Intent, ResponseContract] = {
    intent: spec.response_contract for intent, spec in INTENT_REGISTRY.items()
}

__all__ = ["CONTRACTS", "CITATION_STYLE", "contract_for"]


def contract_for(intent: Intent | str) -> ResponseContract:
    return spec_for(intent).response_contract
