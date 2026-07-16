"""The Prompt Orchestrator — the one place the platform builds prompts.

Given a `DecisionPlan` (what to do), a `ContextPackage` (what we know), and a `UserRequest`
(what was asked), it selects the system prompt, developer instructions, workflow template,
the applicable policies, and the response contract; renders the context with citation
markers; assembles them into an ordered, provider-agnostic `LLMRequest`; computes metrics;
and validates the result.

No provider is chosen, no model is called — the output is the complete request, ready for a
later phase to send to whatever LLM the platform is configured to use.
"""

from __future__ import annotations

from pipeline_contracts import ContextPackage, DecisionPlan, Intent, UserRequest, spec_for

from prompt_orchestrator import engine, renderer
from prompt_orchestrator.engine import LayerContent
from prompt_orchestrator.models import (
    Language,
    LLMRequest,
    PromptFamily,
    PromptMetrics,
    SegmentKind,
)
from prompt_orchestrator.policies import PolicyContext, detect_language, select_policies
from prompt_orchestrator.templates import SYSTEM_TEMPLATE
from prompt_orchestrator.validation import validate
from prompt_orchestrator.workflow_templates import template_for


class PromptOrchestrator:
    """Stateless. Call `orchestrate(...)` per request."""

    def orchestrate(
        self,
        plan: DecisionPlan,
        context: ContextPackage | None,
        request: UserRequest,
        *,
        language: Language | None = None,
        family: PromptFamily = PromptFamily.ANSWER,
    ) -> LLMRequest:
        # the typed Intent flows through unchanged; only display strings use `.value`. The
        # spec (registry) supplies the contract, template, and output profile; an unknown
        # intent keeps its raw label while the spec falls back (historic behaviour).
        intent = plan.intent
        intent_label = intent.value if isinstance(intent, Intent) else str(intent)
        spec = spec_for(intent)
        lang = language or detect_language(request.query)
        warnings: list[str] = []
        if family is not PromptFamily.ANSWER:
            warnings.append(f"family '{family.value}' not implemented this phase; building an answer prompt")

        contract = spec.response_contract
        has_context = context is not None and bool(context.all_blocks())
        requires_citations = contract.required_citations

        # ── render each layer ──
        system_text = SYSTEM_TEMPLATE.render(lang)
        developer_text = renderer.render_developer_instructions(plan.reason, plan.workflow or intent_label, lang)
        wf = template_for(intent)
        workflow_text = wf.render(lang)

        policy_ctx = PolicyContext(language=lang, has_context=has_context,
                                   requires_citations=requires_citations, intent=intent)
        policies = select_policies(policy_ctx)
        policies_text = renderer.render_policies(policies, lang)

        # context layer: present whenever we have a package or retrieval was expected
        rendered = None
        if context is not None or plan.requires_retrieval:
            rendered = renderer.render_context(context)
            if not has_context:
                warnings.append("no grounding evidence available; prompt instructs insufficient-evidence handling")

        contract_text = renderer.render_contract(contract)
        user_text = renderer.render_user_request(request.query, request.has_document, lang)

        # ── assemble ──
        layers: dict[SegmentKind, LayerContent] = {
            SegmentKind.IDENTITY: LayerContent(system_text, SYSTEM_TEMPLATE.id),
            SegmentKind.DEVELOPER_INSTRUCTIONS: LayerContent(developer_text, "developer_instructions.v1"),
            SegmentKind.WORKFLOW: LayerContent(workflow_text, wf.id),
            SegmentKind.POLICIES: LayerContent(policies_text, "policies.v1"),
            SegmentKind.USER_REQUEST: LayerContent(user_text, "user_request.v1"),
            SegmentKind.RESPONSE_CONTRACT: LayerContent(contract_text, f"{intent_label}_contract.v1"),
        }
        if rendered is not None:
            layers[SegmentKind.CONTEXT] = LayerContent(rendered.text, "context.v1")

        segments = engine.assemble(layers)

        # ── metrics ──
        context_segment = next((s for s in segments if s.kind == SegmentKind.CONTEXT), None)
        identity_segment = next((s for s in segments if s.kind == SegmentKind.IDENTITY), None)
        versions = {"system": SYSTEM_TEMPLATE.id, "workflow": wf.id}
        versions.update({p.name: p.version for p in policies})
        metrics = PromptMetrics(
            prompt_chars=sum(len(s.content) for s in segments),
            context_chars=len(context_segment.content) if context_segment else 0,
            estimated_tokens=sum(s.estimated_tokens for s in segments),
            system_tokens=identity_segment.estimated_tokens if identity_segment else 0,
            context_tokens=context_segment.estimated_tokens if context_segment else 0,
            segment_count=len(segments),
            workflow=plan.workflow or intent_label,
            language=lang.value,
            policies_applied=[p.id for p in policies],
            prompt_versions=versions,
        )

        # provider-neutral generation hints from the intent's registered output profile
        params: dict[str, object] = {
            "temperature": spec.output_profile.temperature,
            "max_output_tokens": spec.output_profile.max_output_tokens,
        }

        llm_request = LLMRequest(
            family=family,
            workflow=intent,
            language=lang,
            segments=segments,
            response_contract=contract,
            metrics=metrics,
            params=params,
            warnings=warnings,
        )

        # ── validate ──
        result = validate(llm_request, context, rendered)
        llm_request.valid = result.is_valid
        if not result.is_valid:
            llm_request.warnings.extend(f"validation: {issue}" for issue in result.issues)
        return llm_request
