# Architecture Decision Records (ADRs)

This directory records the **architecturally significant decisions** for the AI GRC
Assistant. Each ADR captures the context, the decision, its consequences, and the
alternatives considered, so future engineers understand *why* the system is the way it is.

Process (see [CLAUDE.md §23](../../CLAUDE.md)): any change to the CLAUDE.md pillars, the
Tool contract, the agent roster, the Framework Engine model, or the Mission Lifecycle
requires a new ADR and an update to CLAUDE.md. ADRs are immutable once Accepted — to change
a decision, add a new ADR that supersedes the old one. Use [`template.md`](./template.md)
for new records.

## Index

| ADR | Title | Status | CLAUDE.md |
|-----|-------|--------|-----------|
| [0001](./0001-record-architecture-decisions.md) | Record architecture decisions | Accepted | §23 |
| [0002](./0002-monorepo-strategy.md) | Monorepo strategy | Accepted | §4, §6 |
| [0003](./0003-mission-centric-design.md) | Mission-Centric design (not Chat-Centric) | Accepted | §3, §8 |
| [0004](./0004-ai-orchestrator.md) | The AI Orchestrator is the brain — not the LLM | Accepted | §7 |
| [0005](./0005-multi-agent-architecture.md) | Multi-Agent architecture | Accepted | §11 |
| [0006](./0006-tools-and-registry.md) | Tools as first-class units & the Tool Registry | Accepted | §9, §10 |
| [0007](./0007-framework-engine.md) | Framework Engine — frameworks as data, not code | Accepted | §13 |
| [0008](./0008-knowledge-and-rag.md) | Knowledge & RAG architecture | Accepted | §12 |
| [0009](./0009-event-driven-architecture.md) | Event-Driven Architecture where it earns its keep | Accepted | §16 |
| [0010](./0010-plugin-architecture.md) | Plugin architecture for extensibility | Accepted | §17 |
| [0011](./0011-ddd-boundaries.md) | Domain-Driven Design boundaries | Accepted | §14, §15 |
| [0012](./0012-postgres-pgvector.md) | PostgreSQL + pgvector as the primary data store | Accepted | §4, §12 |
| [0013](./0013-fastapi-nextjs-stack.md) | FastAPI (backend) + Next.js (frontend) stack | Accepted | §4, §18 |
| [0014](./0014-security-and-multitenancy.md) | Security principles & multi-tenancy | Accepted | §20 |
| [0015](./0015-audit-and-traceability.md) | Audit & traceability (AI transparency) | Accepted | §19 |
| [0016](./0016-workspace-model.md) | Workspace model (Workspace-first UX) | Accepted | §18 |
