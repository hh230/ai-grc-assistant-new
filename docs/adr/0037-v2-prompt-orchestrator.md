# ADR 0037: Rasheed V2 — the Prompt Orchestrator as the single, provider-agnostic prompt builder

- Status: Accepted — implemented (Phase 11)
- Date: 2026-07-14
- Deciders: Product Owner (via direct working session), Architecture
- Related: CLAUDE.md §3, §5, §7, §19, §22; ADR 0035, 0036; architecture docs
  [prompt-orchestrator](../../v2/docs/architecture/prompt-orchestrator.md),
  [context-builder](../../v2/docs/architecture/context-builder.md),
  [decision-engine](../../v2/docs/architecture/decision-engine.md)

## Context

The V2 platform can now decide what to do (Decision Engine), retrieve cited knowledge
(Retrieval Engine + pgvector), and assemble a clean, structured context (Context Builder). The
next capability is grounded generation. Before wiring in any LLM, there is one more
provider-independent responsibility to isolate: **building the prompt.**

In most LLM systems prompts accrete as inline f-strings scattered across handlers, which is
incompatible with a regulated GRC platform. The system prompt, citation rules, safety guards,
and per-workflow output contracts must be a single set of **versioned artifacts**, identical
on every call and reconstructable for audit (CLAUDE.md §19). Prompt construction must also be
independent of the eventual provider — the platform is explicitly not coupled to any single
LLM (CLAUDE.md §4, §7).

## Decision

We introduce a **Prompt Orchestrator** as its own stage and package
(`v2/packages/prompt-orchestrator/`). Its contract is `DecisionPlan + ContextPackage +
UserRequest → LLMRequest`, and **nothing else in the platform builds prompts.**

Key decisions:

1. **A provider-agnostic `LLMRequest`.** Structured and layered (System Prompt → Developer
   Instructions → Workflow Prompt → Policies → Context → User Request → Response Contract),
   never a single string and naming no provider. A `messages()` view folds the layers into the
   conventional system+user shape any provider can consume.
2. **One global system prompt**, versioned (`rasheed_system.v1`): identity, role, GRC scope,
   reasoning rules, citation requirements, and forbidden behaviour.
3. **Workflow templates + response contracts per intent**, keyed to the Decision Engine's
   `Intent`, so the plan selects both directly. Contracts declare required sections,
   citations, formatting, confidence, and forbidden outputs — rendered into the prompt and
   kept structured for a later answer-validation phase.
4. **Composable, versioned prompt policies** (Grounding, Citation, Safety, Reasoning,
   Formatting, Arabic, English) selected per request.
5. **Automatic language handling** — Arabic / English / Mixed detected by script, driving the
   answer directive and language policies.
6. **A validation gate** rejecting any request that loses context, loses a citation, misses
   the workflow, misses the contract, or was built from an invalid ContextPackage. Every
   block gets a citation marker, so citation preservation is structural.
7. **Extensibility reserved, not built** — a `PromptFamily` enum reserves Agent / Mission /
   Tool / Reflection / Reviewer prompt families for later phases.

## Consequences

- Prompts are auditable and reproducible: every request records the versioned templates and
  policies used, plus token/size metrics. 100 real end-to-end requests build valid,
  provider-agnostic LLMRequests across all workflows and languages, p50 ~0.2 ms.
- The boundary before generation is explicit and testable; the generation phase receives a
  complete, validated request and only has to choose a provider and send it.
- Adds two intra-V2 path dependencies (prompt-orchestrator → decision-engine, context-builder)
  to consume their outputs; V1 is untouched. No provider SDK is imported anywhere in the
  package.
