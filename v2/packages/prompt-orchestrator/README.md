# prompt-orchestrator (V2)

Phase 11. The **one place the platform builds prompts.** Converts a `DecisionPlan` +
`ContextPackage` + `UserRequest` into a **provider-agnostic `LLMRequest`** — the complete,
structured request a *later* phase will send to whatever LLM the platform is configured to
use.

**No LLM provider, no OpenAI/Claude/Gemini/Ollama, no generation, no answer validation, no
RAG.** Implements [v2/docs/architecture/prompt-orchestrator.md](../../docs/architecture/prompt-orchestrator.md).

V2-only, isolated: standalone `uv` project with path dependencies on `decision-engine` and
`context-builder`. Does not touch V1.

## The shape (never a single string, never a provider)

```
LLMRequest
  ├─ PromptSegment[]  ordered layers, each role + kind + versioned source:
  │     System Prompt → Developer Instructions → Workflow Prompt →
  │     Policies → Context → User Request → Response Contract
  ├─ ResponseContract   required sections / citations / formatting / confidence / forbidden
  ├─ PromptMetrics      sizes · tokens · policies applied · language · prompt versions
  └─ params + warnings + valid
```

`request.messages()` folds the layers into the conventional `[{system}, {user}]` shape any
provider can consume; the segments preserve the full structure for audit and for providers
with a distinct developer role.

## Usage

```python
from prompt_orchestrator import PromptOrchestrator

orchestrator = PromptOrchestrator()
llm_request = orchestrator.orchestrate(decision_plan, context_package, user_request)

assert llm_request.valid            # False + reasons in .warnings if it failed validation
messages = llm_request.messages()   # [{"role": "system", ...}, {"role": "user", ...}]
```

## Responsibilities

1. **System prompt** — the global Rasheed identity/role/scope/reasoning/citation/forbidden
   rules ([templates.py](prompt_orchestrator/templates.py), `rasheed_system.v1`).
2. **Workflow prompt** — a task template per intent (lookup, comparison, compliance_review,
   gap_assessment, policy_review, risk_analysis, summarization, document_analysis,
   cross_framework_mapping, conversation, …) ([workflow_templates.py](prompt_orchestrator/workflow_templates.py)).
3. **Prompt policies** — reusable Citation / Grounding / Safety / Reasoning / Formatting /
   Arabic / English modules, selected per request ([policies.py](prompt_orchestrator/policies.py)).
4. **Response contract** — required sections, citations, formatting, confidence, and
   forbidden outputs per workflow ([contracts.py](prompt_orchestrator/contracts.py)).
5. **Renderer** — combines system + workflow + policies + context + request into segments
   ([renderer.py](prompt_orchestrator/renderer.py), [engine.py](prompt_orchestrator/engine.py)).
6. **Validation** — rejects prompts that lose context, lose citations, miss the workflow, or
   miss the contract ([validation.py](prompt_orchestrator/validation.py)).
7. **Language** — auto-detects Arabic / English / Mixed and applies the right policies +
   answer directive.
8. **Metrics** — prompt size, context size, estimated tokens, workflow, policies applied,
   language, prompt versions.
9. **Extensibility** — `PromptFamily` reserves Agent / Mission / Tool / Reflection / Reviewer
   prompt families for later phases.
10. **Output** — the layered `LLMRequest` above.

## Language

`detect_language` classifies by script mix: Arabic, English, or Mixed. Mixed applies **both**
language policies and instructs the model to mirror the user's language; framework codes stay
Latin, RTL is handled cleanly.

## Run tests, benchmark, examples

```bash
cd v2/packages/prompt-orchestrator
uv sync
uv run pytest -q                              # every workflow · AR/EN/mixed · missing/invalid context · contracts
uv run python -m prompt_orchestrator.benchmark   # 100 real end-to-end requests: latency, tokens, policies
uv run python -m prompt_orchestrator.examples    # render full layered LLMRequests
```

## Guarantees (enforced by `validate`)

A request is rejected (`valid=False`, reasons in `warnings`) if it misses the workflow, misses
the response contract, loses context (package blocks that didn't reach the prompt), loses a
citation, or was built from an invalid `ContextPackage`. A legitimately empty context
(conversation, or genuine "insufficient evidence") is handled, not rejected.

## Not in this phase

No LLM provider, no model call, no generation, no answer validation, no hallucination
detection, no RAG. The orchestrator produces the request; a later phase sends it and grounds
the answer.
