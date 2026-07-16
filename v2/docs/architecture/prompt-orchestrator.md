# Rasheed V2 — Prompt Orchestrator Architecture

- Status: **Implemented (Phase 11).** Package: `v2/packages/prompt-orchestrator/`.
- Date: 2026-07-14
- Companions: [Decision Engine](decision-engine.md) (supplies the `DecisionPlan`),
  [Context Builder](context-builder.md) (supplies the `ContextPackage`),
  [Retrieval Engine](retrieval-engine.md), [ADR 0037](../../../docs/adr/0037-v2-prompt-orchestrator.md).
- Scope boundary: **v2/ only.** Sits between the read path and the (future) generation phase.
  It does **not** name or call any LLM provider (OpenAI/Claude/Gemini/Ollama), generate
  answers, validate answers, or do RAG.

---

## 0. Why a Prompt Orchestrator

Prompts are where correctness, safety, and auditability are won or lost in an LLM system, yet
they tend to sprawl as f-strings across a codebase. In a regulated GRC platform that is
unacceptable: the system prompt, the citation rules, and the "don't give legal advice" guard
must be **one versioned artifact**, identical on every call, and reconstructable for audit.

So prompt construction is its own stage and its own package. Nothing else in the platform
builds a prompt. The orchestrator's contract is `DecisionPlan + ContextPackage + UserRequest
→ LLMRequest`, and the `LLMRequest` names no provider — the same object can later be sent to
any model.

---

## 1. Output — the LLMRequest

Structured, layered, provider-agnostic (never a single string):

```
LLMRequest
  ├─ PromptSegment[]   (ordered; each has role + kind + versioned source + token estimate)
  │     System Prompt → Developer Instructions → Workflow Prompt →
  │     Policies → Context → User Request → Response Contract
  ├─ ResponseContract
  ├─ PromptMetrics
  └─ params (provider-neutral hints) + warnings + valid
```

`messages()` folds the segments into the conventional `[{system}, {user}]` shape (system =
identity + developer + workflow + policies + contract; user = context + request). The full
segment list is retained for audit and for providers that support a developer role.

---

## 2. The seven layers

1. **System prompt** (`rasheed_system.v1`) — identity, role (amplify humans, never
   auto-approve), scope (GRC only, no legal advice), reasoning rules (ground or say
   "insufficient evidence"), citation requirements, forbidden behaviour, and a
   language-specific answer directive.
2. **Developer instructions** — routes the request ("this is a gap_assessment, decided
   because …") and points at the layers below.
3. **Workflow prompt** — the task template for the intent (assess / compare / extract /
   summarise / clarify / …). One per Decision Engine intent, versioned.
4. **Policies** — reusable modules selected per request: Grounding, Citation, Safety,
   Reasoning, Formatting, Arabic, English. A conversation drops grounding/citation; an Arabic
   request adds the Arabic policy.
5. **Context** — the `ContextPackage` rendered with a citation marker ([S1], [S2], …) on
   **every** block plus a Sources legend. Assigning a marker per block is what guarantees no
   citation is dropped between the Context Builder and the prompt.
6. **User request** — the raw query, with an attachment note when a document accompanies it.
7. **Response contract** — required sections, citation style, formatting, whether confidence
   is required, and forbidden outputs — rendered into the prompt *and* kept structured for a
   later answer-validation phase.

---

## 3. Policies & language

Policies declare *when* they apply and *what* they contribute, so the orchestrator composes
the right set. Language is detected by script mix (`detect_language`): Arabic, English, or
Mixed. Mixed applies both language policies and instructs the model to mirror the user's
language while keeping framework codes Latin and rendering RTL cleanly. The system prompt's
answer directive changes with the detected language.

## 4. Response contracts

Each workflow declares its contract (`contracts.py`), keyed by Decision Engine intent.
Assertive workflows (compliance review, gap assessment, risk analysis, policy review) require
an explicit **confidence** level and forbid attesting/approving/accepting on the user's
behalf. Grounded workflows require citations; conversation and the non-answer outcomes
(clarification, out-of-scope) do not.

## 5. Validation (the guarantee)

A request is rejected (`valid=False`, reasons in `warnings`) when it **misses the workflow**,
**misses the response contract**, **loses context** (package blocks that didn't all reach the
prompt), **loses a citation** (an incomplete citation, or a marker whose source is absent from
the rendered context), or was built from an **invalid ContextPackage**. A legitimately empty
context — a conversation, or a genuine "insufficient evidence" retrieval — is handled (the
context layer states there is no evidence) rather than rejected.

## 6. Metrics & reproducibility

Every request carries `PromptMetrics`: prompt/context chars, estimated tokens (via the Context
Builder's estimator, for consistency), system/context token split, segment count, workflow,
language, policies applied, and **prompt versions** for every template/policy used — so any
produced prompt can be reconstructed for audit (CLAUDE.md §19).

---

## 7. Measured behaviour (real corpus, full V2 chain)

100 real end-to-end requests (retrieval → context → prompt) across all workflows and
languages:

- **100/100 valid.** Orchestration **p50 ~0.2 ms** (pure assembly), ~4,700 req/s.
- Prompt tokens mean ~5,800 (context ~4,700); language split 80 EN / 15 AR / 5 mixed detected
  correctly; safety/grounding/citation/reasoning/formatting on every grounded request.

---

## 8. Extensibility & non-goals

`PromptFamily` reserves **Agent / Mission / Tool / Reflection / Reviewer** prompt families for
later phases; only ANSWER is built now. New workflows, policies, and contracts are added by
registering data, not by editing the orchestrator.

Out of scope, by design: no LLM provider, no model call, no generation, no answer validation,
no hallucination detection, no RAG. The orchestrator produces the request; sending it and
grounding an answer on it is the next phase.

*Living document. Implemented in `v2/packages/prompt-orchestrator/`; keep them in sync.*
