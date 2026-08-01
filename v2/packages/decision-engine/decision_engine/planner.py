"""Turns a `Classification` into a `DecisionPlan` by applying the workflow catalog and the
routing/budget rules from the architecture (§5 routing, §6 tools, §7 context). Pure and
deterministic — no I/O, no model. Retrieval is never assumed: conversation, unsupported,
and document-analysis plans carry `requires_retrieval = false`.
"""

from __future__ import annotations

from decision_engine.classifier import Classification
from decision_engine.models import DecisionPlan, Intent, UserRequest
from decision_engine.rules import profiles_from_hits
from decision_engine.workflows import MAX_MULTISTEP_BUDGET, WORKFLOWS

# intents whose comparison-style fan-out scales with the number of subjects mentioned
_SUBJECT_SCALED = {Intent.COMPARISON, Intent.CROSS_FRAMEWORK_MAPPING}
_MAX_PASSES = 5


def build_plan(request: UserRequest, classification: Classification) -> DecisionPlan:
    primary = classification.primary
    workflow = WORKFLOWS[primary]

    requires_retrieval = workflow.requires_retrieval
    requires_reranker = workflow.requires_reranker
    requires_human_gate = workflow.requires_human_gate
    requires_document = workflow.requires_document or classification.mentions_document
    passes = workflow.retrieval_passes
    budget = workflow.context_budget

    # target profiles: from detected frameworks, else the workflow's defaults
    profiles = profiles_from_hits(classification.frameworks) or list(workflow.default_profiles)

    # comparison / cross-mapping scale passes with the number of subjects mentioned
    if primary in _SUBJECT_SCALED:
        subjects = len(classification.frameworks)
        passes = min(_MAX_PASSES, max(passes, subjects))

    # summarization / document analysis of an *attachment*: read the doc, not the corpus
    if requires_document and primary in {Intent.SUMMARIZATION, Intent.DOCUMENT_ANALYSIS}:
        requires_retrieval = False
        requires_reranker = False
        passes = 0
        budget = 0

    # multi-step composite: fold in each secondary workflow's routing/budget/gates
    multi_step = bool(classification.secondaries)
    if multi_step:
        for secondary in classification.secondaries:
            sw = WORKFLOWS[secondary]
            requires_retrieval = requires_retrieval or sw.requires_retrieval
            requires_reranker = requires_reranker or sw.requires_reranker
            requires_human_gate = requires_human_gate or sw.requires_human_gate
            passes += sw.retrieval_passes
            budget += sw.context_budget
            if sw.default_profiles:
                for p in sw.default_profiles:
                    if p not in profiles:
                        profiles.append(p)
        budget = min(budget, MAX_MULTISTEP_BUDGET)
        passes = min(_MAX_PASSES, passes)

    # a non-retrieval plan never carries passes or a (corpus) context budget
    if not requires_retrieval:
        passes = 0
        if not requires_document:
            budget = 0

    return DecisionPlan(
        intent=primary,
        workflow=workflow.name,
        requires_retrieval=requires_retrieval,
        requires_document=requires_document,
        requires_reranker=requires_reranker,
        requires_human_gate=requires_human_gate,
        multi_step=multi_step,
        retrieval_passes=passes,
        context_budget=budget,
        target_profiles=profiles,
        confidence=classification.confidence,
        reason=classification.reason,
        detected_frameworks=[f.label for f in classification.frameworks],
        secondary_intents=list(classification.secondaries),
        matched_cues=classification.matched_cues,
        language=classification.language,
    )
