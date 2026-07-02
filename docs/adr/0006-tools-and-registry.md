# ADR 0006: Tools as first-class units & the Tool Registry

- Status: Accepted
- Date: 2026-06-26
- Deciders: Architecture team
- Related: CLAUDE.md §9, §10, §17; ADR 0004, 0005, 0010

## Context

Business capabilities must be reusable across the Orchestrator, the API, the UI, the
Workflow Engine, scheduled jobs, and tests — without duplication and without logic trapped
inside a UI handler, an agent, or a prompt. We also need capabilities to be discoverable,
versioned, access-controlled, and auditable, and to be the only path to side effects.

## Decision

Every business function is an independent, schema-validated **Tool** with a typed I/O
contract, declared side-effect profile (read-only vs. consequential), required tenant/auth
context, idempotency for consequential actions, human-gate awareness, and built-in
observability. Tools depend on the Services Layer — never on a route handler, UI, or LLM
SDK directly. Every Tool is callable, with identical semantics, from the **six callers**
(Orchestrator, API, UI, Workflow, Scheduled Jobs, Tests).

Tools are discovered and invoked through a central **Tool Registry** that owns
registration, discovery, versioning (`map_frameworks.v2`), capability metadata for
Orchestrator planning, access control, and audit. Nothing calls a capability out of band;
the Registry is the single source of truth for what the platform can do, and the entry
point for plugin Tools.

## Consequences

**Positive**
- One implementation, six callers — composable, testable (tested directly), automatable.
- Side effects funnel through a governed, auditable boundary with human gates.
- New capabilities (incl. third-party) appear by registration, not core edits.

**Negative / costs**
- Contract overhead for every capability (schemas, idempotency, registration).
- Requires governance to reject "out of band" capabilities in review.

## Alternatives considered

- **Logic inside API/UI handlers or agents.** Rejected: not reusable, untestable headless,
  bypasses gates/audit.
- **Ad-hoc service functions without a registry.** Rejected: no discovery, versioning, or
  access control for planning and plugins.
