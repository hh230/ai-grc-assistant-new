# ADR 0003: Mission-Centric design (not Chat-Centric)

- Status: Accepted
- Date: 2026-06-26
- Deciders: Architecture team
- Related: CLAUDE.md §3, §8, §18; ADR 0016

## Context

GRC work is consequential and auditable: a control sign-off or risk acceptance can affect
an audit outcome. A chat-centric model (stateless turns, ephemeral transcripts) cannot
provide the plan, lifecycle, approval gates, and reconstructable history this domain
requires. We need a unit of work that is governed, resumable, and audit-ready.

## Decision

The fundamental unit of work is a **Mission**: a goal-directed, governed, auditable task
with an explicit lifecycle (Created → Planned → Executing → Awaiting Approval →
Resumed/Re-planned → Completed / Failed / Archived). A Mission is a first-class domain
entity carrying tenant, owner, goal, plan, steps, tools/agents used, inputs/outputs,
citations, approval gates, status, and full event history. Chat is one interface that can
*open* or *steer* a mission — never the seat of state.

Missions are resumable, replayable, and idempotent; every transition emits an event and is
recorded for audit. Nothing consequential proceeds without passing a human gate.

## Consequences

**Positive**
- Long-running, multi-step GRC work is observable, steerable, and recoverable.
- Auditors can replay exactly what happened, with which inputs, models, sources, and
  approvals.
- Human gates are a structural part of the model, not an afterthought.

**Negative / costs**
- More upfront modeling than a chat loop (lifecycle, persistence, replay semantics).
- Requires the Workflow Engine (ADR 0009-adjacent) and durable state to honor resume/retry.

## Alternatives considered

- **Chat-centric assistant.** Rejected: no durable plan, weak auditability, unsafe for
  consequential actions.
- **Stateless request/response tasks.** Rejected: cannot model approval pauses, long runs,
  or replay.
