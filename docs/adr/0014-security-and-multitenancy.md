# ADR 0014: Security principles & multi-tenancy

- Status: Accepted
- Date: 2026-06-26
- Deciders: Architecture team, Security
- Related: CLAUDE.md §20, §22, §23; ADR 0008, 0012, 0015

## Context

The platform is a global, multi-tenant Enterprise SaaS holding some of customers' most
sensitive data (compliance evidence, control posture, risk findings) under many regulators.
A single cross-tenant leak or privilege escalation is an existential failure. Security and
isolation must be structural, not conventional.

## Decision

We adopt **security and tenant isolation as binding constraints at every layer**:

- **Absolute tenant isolation.** Every query, retrieval, event, mission, memory, and log
  is tenant-scoped. **Default deny.** Cross-tenant access is impossible by construction,
  not by convention.
- **Identity & access.** OIDC/SSO with RBAC (and ABAC where needed). Least privilege for
  users, agents, tools, and plugins alike.
- **Least-privilege agents/tools/plugins.** Each declares the data and tools it may touch;
  consequential actions require human gates.
- **Data residency & regionalization.** Regional data handling and localization for
  regulators such as NCA/SAMA/PDPL.
- **Secure by default.** Encryption in transit and at rest; secrets only from a secret
  manager (never in code/config); dependency and secret scanning in CI; least-privilege
  infra access; threat-model any feature touching auth, tenancy, or data egress before
  building it.
- **Fail safe, not open.** On uncertainty or error in a compliance-relevant path, stop and
  ask a human.

## Consequences

**Positive**
- Strong, structural guarantees suitable for regulated, multi-regulator customers.
- Clear, enforceable rules reviewers and CI can check.

**Negative / costs**
- Tenant-scoping and least-privilege add boilerplate and review overhead on every path.
- Data residency/regionalization complicates deployment topology.

## Alternatives considered

- **Convention-based tenant scoping (app-level discipline only).** Rejected: too easy to
  violate; we enforce by construction and default deny.
- **Single-tenant deployments per customer.** Rejected: does not scale to thousands of
  tenants; conflicts with the SaaS goal (kept only for specific enterprise needs if ever
  required, via ADR).
