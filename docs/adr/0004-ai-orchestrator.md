# ADR 0004: The AI Orchestrator is the brain — not the LLM

- Status: Accepted
- Date: 2026-06-26
- Deciders: Architecture team
- Related: CLAUDE.md §3(1), §7; ADR 0005, 0015

## Context

LLMs are powerful but non-deterministic, provider-specific, and unsafe as a seat of
control. If planning, routing, memory, and policy live inside raw model calls, the system
becomes unauditable, vendor-locked, and unable to enforce tenancy, budgets, or human
gates. We need a durable, testable control plane that treats the model as a replaceable
capability.

## Decision

We introduce an **AI Orchestrator** as the brain of the system. It owns mission planning
and decomposition, routing (which agent/tool runs each step), short- and long-term memory
(tenant-isolated), policy and guardrails (safety, budget, tenancy, compliance), human-gate
control, provider abstraction (LLMs behind a swappable interface with retry/fallback/
budgets), and durable mission state for pause/resume/replay.

Hard rules: business logic never calls an LLM directly; the LLM may *suggest* but the
Orchestrator *decides* and validates; the LLM never mutates state directly — side effects
happen only through Tools behind validation and human gates; every Orchestrator decision
is logged for audit.

## Consequences

**Positive**
- Deterministic, testable control flow around a non-deterministic model.
- Provider independence; models swap without touching agents or tools.
- A single place to enforce budgets, tenancy, policy, and reproducibility.

**Negative / costs**
- The Orchestrator is a critical, complex component requiring careful design and testing.
- Adds a hop versus calling a model directly (justified by safety/auditability).

## Alternatives considered

- **Let the LLM/agent framework drive control flow.** Rejected: unauditable, vendor-locked,
  cannot guarantee gates/tenancy.
- **Hardcoded pipelines per use case.** Rejected: not composable or extensible across many
  missions and frameworks.
