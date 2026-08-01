# ADR 0035: Rasheed V2 — the Knowledge Library as V2's foundation

- Status: Proposed — architecture only, nothing described here is implemented yet
- Date: 2026-07-11
- Deciders: Product Owner (via direct working session), Architecture
- Related: CLAUDE.md §3, §6, §12, §13, §23; ADR 0007, 0008, 0025–0032; ADL-0007, ADL-0008

## Context

A repository-wide knowledge sources audit (this session) found that every AI-facing feature
in Rasheed today is grounded in a thin slice of real content: three frameworks with
representative (not exhaustive) control samples, one regulation pipeline that produced real
embeddings once but that nothing retrieves from, and a well-designed Python Knowledge domain
model (`packages/domain/grc_domain/knowledge/`, `packages/extraction*`,
`packages/framework-engine/`, `packages/knowledge-ontology/`) that is mature, tested, and
**never deployed** — no Dockerfile, no scheduler, no production callers. The audit's
conclusion, consistent with ADL-0007 and ADL-0008: the gap is operational, not architectural.

Separately, the Product Owner has directed that Rasheed V2 begin, with production
(`apps/web`) frozen except critical bug fixes, and all new work confined to an isolated V2
codebase.

Every planned V2 AI feature — grounded chat, framework coverage, obligation matching, policy
review — depends on the same thing: a real, deployed, comprehensive knowledge base. Building
that once, correctly, before any feature work starts, avoids repeating the current split
between a hardcoded catalog, an empty domain model, and orphaned embeddings.

## Decision

We will treat the **Knowledge Library** as the foundational layer of Rasheed V2, designed in
full before any V2 feature code is written. The complete design — vision, schema, domain
models, ingestion pipeline, retrieval flow, and extensibility plan — is recorded in
[`v2/docs/architecture/knowledge-library.md`](../../v2/docs/architecture/knowledge-library.md)
rather than in this ADR's body, since it is substantially larger than a typical decision
record; this ADR is the governance record that the decision was made, and the pointer to
where the binding detail lives.

The core architectural bet, stated here because it is the one decision every later V2 phase
depends on: **V2 promotes and finishes the existing `packages/domain`/`packages/extraction`/
`packages/framework-engine`/`packages/knowledge-ontology`/`packages/rag` design into a new,
isolated `v2/` root, rather than redesigning from scratch.** That design was already sound;
what it lacked was a production persistence adapter, a scheduler, and a deployment target —
all three are now in scope for V2, not deferred again.

Production `apps/web` and every existing `packages/*` path are unmodified by this decision —
promotion means copying/renaming into `v2/` as its own reviewable work, never editing the
frozen code in place.

## Consequences

**Positive**
- V2 starts from a design that's already been reviewed, tested, and validated in prior ADRs
  (0007, 0008, 0025–0032) instead of re-litigating settled decisions.
- The specific failure mode found in the audit — excellent domain modeling with zero
  production callers — is named as the thing V2 must not repeat, with a concrete owner
  (§9/§11 of the design doc: real deployment and scheduling are first-class V2 deliverables).
- One knowledge model for both global (framework/regulation) and tenant-scoped content,
  closing the "two disconnected knowledge stores" gap the audit found.

**Negative / costs**
- Promotion work (moving and finishing `packages/domain`'s knowledge slice, `packages/extraction`,
  etc. into `v2/`) is real engineering effort, not a relabeling exercise — the persistence
  adapter and scheduler genuinely don't exist yet.
- Two knowledge-adjacent Python trees now exist during the transition (legacy `packages/*`,
  frozen, and `v2/packages/*`, active) until promotion completes package by package.

## Alternatives considered

- **Design a new Knowledge Library from scratch**, ignoring the existing domain model.
  Rejected: the existing design already satisfies this document's requirements and has test
  coverage; discarding it would repeat design work with no corresponding benefit, and would
  orphan the one regulation pipeline that has already produced real, verified content.
- **Fix the existing `packages/*` in place and skip the `v2/` isolation.** Rejected: the
  Product Owner's explicit instruction was to freeze production and confine new work to a
  V2-only area; editing `packages/*` in place blurs that boundary and risks the frozen system
  being affected by in-progress V2 changes.
- **Write the full design inline in this ADR.** Rejected: the design spans eleven substantial
  sections including a complete schema — ADRs in this repo (per `docs/adr/README.md`) record
  decisions concisely; a companion document is the better fit, matching how ADR 0031 already
  defers to code/migrations for implementation detail rather than inlining it.
