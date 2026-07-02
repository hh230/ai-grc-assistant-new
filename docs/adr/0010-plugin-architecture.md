# ADR 0010: Plugin architecture for extensibility

- Status: Accepted
- Date: 2026-06-26
- Deciders: Architecture team
- Related: CLAUDE.md §17; ADR 0006, 0005, 0007

## Context

A platform meant to live 10+ years and serve thousands of tenants must grow at the edges —
new Tools, Agents, Frameworks, and Connectors (evidence sources, ticketing, identity,
cloud posture) — without editing core control flow (Orchestrator, Services, Domain). Growth
by core surgery is slow, risky, and does not scale to partner/third-party contributions.

## Decision

We adopt a **Plugin Architecture**. New capabilities are *added*, not *patched in*:

- **Tools as plugins** — implement the Tool contract and register in the Tool Registry;
  the Orchestrator discovers them automatically.
- **Agents as plugins** — register and declare needed Tools and data scopes.
- **Frameworks as plugins** — added as data to the Framework Engine.
- **Connectors as plugins** — behind connector interfaces with an anti-corruption layer
  translating external data into clean domain models.

Plugins run with least privilege, declared permissions, resource budgets, and tenant
scoping; they can never bypass the Orchestrator's policy, human gates, or tenant isolation.
Plugins declare versions and compatibility. If extending the platform requires editing the
core, that is a design smell to reconsider.

## Consequences

**Positive**
- Safe, fast extension by internal teams and third parties without core changes.
- Clear isolation and least-privilege boundaries for untrusted/partner code.

**Negative / costs**
- Requires a stable plugin SDK, versioning/compatibility policy, and sandboxing.
- Anti-corruption layers add translation code at every connector boundary.

## Alternatives considered

- **Extend by editing core control flow.** Rejected: slow, risky, doesn't scale to partners.
- **Fork-per-customer customization.** Rejected: incompatible with multi-tenant SaaS.
