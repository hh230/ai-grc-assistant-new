# ADR 0009: Event-Driven Architecture where it earns its keep

- Status: Accepted
- Date: 2026-06-26
- Deciders: Architecture team
- Related: CLAUDE.md §16; ADR 0003, 0015

## Context

Some platform behavior should not block the request path or tightly couple bounded
contexts: re-indexing after evidence ingestion, scheduled re-assessments, notifications,
audit streaming, and cross-context reactions. At the same time, over-using events for
simple in-transaction reads/writes adds accidental complexity and obscures control flow.

## Decision

We use **Event-Driven Architecture deliberately**, not everywhere. Meaningful state changes
emit immutable, past-tense **domain events** (`ControlAssessed`, `EvidenceIngested`,
`MissionCompleted`, `RiskAccepted`). Events are used for cross-context reactions,
long-running side effects, notifications, audit streaming, re-indexing, and scheduled
triggers. They are **not** used for simple synchronous reads/writes within one transaction.

Reliability: processing is idempotent and at-least-once; consumers tolerate duplicates and
out-of-order delivery; a transactional **outbox** prevents lost events on failure. Every
event carries tenant context and consumers stay tenant-scoped. The event log is itself an
audit asset.

## Consequences

**Positive**
- Decoupled contexts and non-blocking long-running work; better scalability.
- The event log doubles as a reconstructable tenant history for audit.

**Negative / costs**
- Eventual consistency and duplicate handling add cognitive load.
- Requires outbox, idempotency keys, and observability to debug async flows.

## Alternatives considered

- **Synchronous calls everywhere.** Rejected: blocks request paths, tightly couples
  contexts, harms scale.
- **Events for everything.** Rejected: needless complexity for simple in-transaction work.
