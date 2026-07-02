# ADR 0005: Multi-Agent architecture

- Status: Accepted
- Date: 2026-06-26
- Deciders: Architecture team
- Related: CLAUDE.md §11; ADR 0004, 0006

## Context

GRC missions span distinct competencies — retrieval/grounding, policy authoring, control
and compliance analysis, risk assessment, reporting, and process orchestration. A single
monolithic prompt that tries to do all of this is hard to test, reason about, secure, and
extend, and it blurs least-privilege boundaries.

## Decision

We adopt a roster of **specialized agents** composed by the Orchestrator: **Knowledge**
(retrieval & grounding), **Policy**, **Compliance** (gap analysis, mapping, questionnaires,
coverage), **Risk** (identification, scoring, remediation), **Report** (audit-ready
deliverables), and **Workflow** (long-running processes, scheduling, hand-offs).

Rules: agents act **only through registered Tools**; they are composable (e.g. Knowledge →
Risk → Report), scoped (least-privilege tool/data access, tenant-bound), and governed
(run under Orchestrator policy and human gates; no self-authorized consequential action).
New agents (e.g. Audit, Vendor-Risk) are added by registration without restructuring the
system. Every agent decision is logged.

## Consequences

**Positive**
- Focused, independently testable reasoning units with clear responsibilities.
- Least-privilege by construction; smaller blast radius per agent.
- Extensible roster; new agents plug in (see ADR 0010).

**Negative / costs**
- Inter-agent coordination is the Orchestrator's responsibility (added complexity).
- More prompt/version artifacts to manage (mitigated by versioned prompts).

## Alternatives considered

- **Single general agent / one prompt.** Rejected: poor testability, weak scoping, hard to
  extend.
- **Hardcoded function pipeline.** Rejected: not composable across diverse missions.
