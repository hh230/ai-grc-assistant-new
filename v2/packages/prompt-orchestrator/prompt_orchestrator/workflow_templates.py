"""Workflow templates — the task-specific instruction layer, one per Decision Engine intent.

Each template tells the model *what job to do* for this workflow (assess, compare, extract,
summarise, clarify, …). It sits between the global system prompt and the policies. The
required output shape is not repeated here — that is the Response Contract's job
(`contracts.py`). Versioned and keyed by `Intent`.

The instruction *bodies* live in the shared Intent Registry
(`pipeline_contracts.intent_registry`) — the single source of truth for per-intent
behaviour. This module owns only the rendering machinery (`WorkflowTemplate`) and the
version stamping.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pipeline_contracts import Intent, spec_for
from pipeline_contracts.intent_registry import INTENT_REGISTRY

from prompt_orchestrator.models import Language


@dataclass(frozen=True)
class WorkflowTemplate:
    name: str
    version: str
    intent: Intent
    render: Callable[[Language], str]

    @property
    def id(self) -> str:
        return f"{self.name}.{self.version}"


def _static(text: str) -> Callable[[Language], str]:
    return lambda _language: text


TEMPLATE_VERSION = "v1"


WORKFLOW_TEMPLATES: dict[Intent, WorkflowTemplate] = {
    intent: WorkflowTemplate(
        name=f"{intent.value}_workflow",
        version=TEMPLATE_VERSION,
        intent=intent,
        render=_static(spec.template_body),
    )
    for intent, spec in INTENT_REGISTRY.items()
}


def template_for(intent: Intent | str) -> WorkflowTemplate:
    return WORKFLOW_TEMPLATES[spec_for(intent).intent]
