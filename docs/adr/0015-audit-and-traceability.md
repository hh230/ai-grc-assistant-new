# ADR 0015: Audit & traceability (AI transparency)

- Status: Accepted
- Date: 2026-06-26
- Deciders: Architecture team, Compliance
- Related: CLAUDE.md §19; ADR 0003, 0004, 0008

## Context

We operate in a regulated domain where every AI-driven output may later be reviewed by an
external auditor. Trust is the product: outputs must be explainable, traceable to sources,
and reproducible. Without a structural audit trail, the platform cannot be used for
consequential GRC decisions.

## Decision

**Transparency and auditability are mandatory, structural requirements.** For every
AI-driven step the system records and can surface: what was asked (goal + resolved inputs
or hashes), what was retrieved (exact source IDs, sections, framework references), which
model and **versioned prompt** were used, which Tools ran (inputs/outputs, side-effect
profile), the confidence signal and citations, cost/performance (tokens, latency, cost),
and decisions/gates (Orchestrator decisions and every human approval/rejection with who and
when).

Rules: outputs are **reproducible** from logged inputs, versions, and sources; we expose
grounded reasoning, sources, and decisions but **never raw chain-of-thought or internal
prompts** to end users; LLM output is treated as untrusted input (validate, sanitize, never
`eval`, guard against prompt injection from retrieved documents); the audit trail is
append-only and tenant-scoped (tamper-evident), suitable for external review.

## Consequences

**Positive**
- Every consequential output is reconstructable and defensible in an audit.
- Strong guardrails against hallucination, injection, and silent model changes.

**Negative / costs**
- Pervasive logging/tracing adds storage, performance, and privacy-handling overhead.
- Requires careful redaction/hashing of sensitive inputs in logs.

## Alternatives considered

- **Best-effort logging.** Rejected: insufficient for regulated, audit-bound decisions.
- **Exposing full chain-of-thought for "transparency".** Rejected: leaks internal/unsafe
  reasoning; we expose grounded sources and decisions instead.
