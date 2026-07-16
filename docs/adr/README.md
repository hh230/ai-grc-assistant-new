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
| [0017](./0017-policy-intelligence-runtime-and-web-postgres-bridge.md) | Policy Intelligence AI runtime — Tool Registry, roster extension, web↔Postgres bridge | Accepted | §9, §10, §11, §20 |
| [0018](./0018-regulatory-intelligence-engine.md) | Regulatory Intelligence engine — obligation pipeline, Tool-audited LLM | Accepted | §5, §9, §12, §13, §16, §19 |
| [0019](./0019-regulatory-connectors-and-crawlers.md) | Regulatory connectors & crawlers — source registry, polite crawling, change detection | Accepted | §5, §13, §16, §17, §19 |
| [0020](./0020-policy-hunter-agent.md) | Policy Hunter Agent — coverage-gap detection, read-only Tools | Accepted | §5, §9, §11, §15, §19 |
| [0021](./0021-policy-analyst-agent.md) | Policy Analyst Agent — policy-quality review, read-only Tools | Accepted | §5, §9, §11, §15, §19 |
| [0022](./0022-policy-intelligence-api-exposure.md) | Policy Intelligence API exposure — a thin, read-only `apps/api` router | Accepted | §5, §6, §9, §10, §19 |
| [0023](./0023-policy-intelligence-frontend-proxy.md) | Policy Intelligence frontend — a server-side proxy, not a second implementation | Accepted | §5, §6, §18, §20 |
| [0024](./0024-policy-builder-agent.md) | Policy Builder Agent — deterministic starter drafts, zero write path | Accepted | §5, §9, §11, §15, §19 |
| [0025](./0025-autonomous-knowledge-engine.md) | Autonomous Knowledge Engine (KI-P1) — catalog-driven questions, Tool-audited discovery | Accepted | §5, §9, §11, §12, §13, §19 |
| [0026](./0026-autonomous-knowledge-research.md) | Autonomous Knowledge Research (KI-P2) — trusted-source planning, grounded discovery | Accepted | §5, §7, §11, §12, §13, §16, §19 |
| [0027](./0027-domain-ontology-engine.md) | Domain Ontology Engine (KI-P3) — GRC taxonomy & question generation | Accepted | §5, §13, §15, §16 |
| [0028](./0028-autonomous-knowledge-worker.md) | Autonomous Knowledge Worker (KI-P4) — scheduler over the gap-research pipeline | Accepted | §5, §7, §9, §11, §12, §13, §16, §19 |
| [0029](./0029-ai-worker-control-center.md) | AI Worker Control Center (KI-P5) — admin control, activity timeline, reporting | Accepted | §5, §7, §9, §16, §18, §19 |
| [0030](./0030-saudi-regulations-ingestion-pipeline.md) | Saudi Regulations Ingestion Pipeline (KI-P6) — fetch, Arabic legal parsing, pending review | Accepted | §5, §9, §12, §13, §15, §16, §19 |
| [0031](./0031-regulation-review-and-embeddings.md) | Regulation Review & Embeddings (KI-P7) — approval gate, post-approval embeddings | Accepted | §9, §12, §16, §19, §20 |
| [0032](./0032-regulation-retrieval-priority-merge.md) | Retrieval priority merge — internal DB → trusted-source research → LLM fallback | Proposed — deferred | §6, §12 |
| [0034](./0034-invite-based-access.md) | Invite-based access & organization onboarding (KI-P9) | Accepted | §9, §14, §15, §20 |
| [0035](./0035-v2-knowledge-library.md) | V2 — Knowledge library | Proposed — architecture only | §12, §13 |
| [0036](./0036-v2-context-builder.md) | V2 — Context Builder | Accepted — implemented (Phase 10) | §12 |
| [0037](./0037-v2-prompt-orchestrator.md) | V2 — Prompt Orchestrator | Accepted — implemented (Phase 11) | §7, §19 |
| [0038](./0038-v2-pipeline-contracts-and-ai-orchestrator.md) | V2 — pipeline-contracts + ai-orchestrator (composition root) | Accepted — implemented (Phase 12) | §3, §5, §6, §7 |
| [0039](./0039-v2-platform-hardening.md) | V2 — platform hardening (validation, tracing, event bus & audit, provider expansion) | Accepted — implemented (Phase 13) | §9, §16, §19 |
| [0040](./0040-v2-tenancy-model.md) | V2 — the tenancy model (contract only; implementation deferred to Phase 15+) | Accepted — contract only | §3, §8, §9, §16, §19, §20 |
| [0041](./0041-knowledge-source-storage.md) | Knowledge source storage | Accepted | §12 |
| [0042](./0042-v2-mission-engine.md) | V2 — the Mission Engine (governed unit of work; architecture only, pending review) | Proposed — architecture only | §3, §7, §8, §9, §11, §16, §19, §20 |

There is no ADR 0033 — the number was skipped, not lost.
