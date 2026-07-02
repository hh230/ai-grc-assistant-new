# ADR 0007: Framework Engine — frameworks as data, not code

- Status: Accepted
- Date: 2026-06-26
- Deciders: Architecture team, Compliance
- Related: CLAUDE.md §13; ADR 0006, 0008

## Context

The platform must support many compliance standards — NCA ECC, SAMA, PDPL, ISO 27001,
NIST CSF, CIS, COBIT, COSO — and unknown future ones, across regions and languages
(including Arabic). If framework names or rules are encoded in control flow
(`if framework == "iso_27001"`), every new regulator becomes an architectural change and a
regression risk. Frameworks also evolve by version, and assessments must pin the version
they ran against for audit integrity.

## Decision

We build a **Framework Engine** that represents any standard as structured **data**
(framework → domains → controls → requirements → evidence expectations) conforming to a
canonical schema. Definitions live under `/frameworks/<id>/<version>/` with metadata
(stable id like `framework:nca_ecc`, region, languages, status). The engine provides the
canonical model, cross-framework control-to-control **mapping** and coverage computation,
**versioning**, and **localization/regionalization**. It is exposed to agents as Tools
(`get_framework`, `map_frameworks`, `compute_coverage`) and feeds the RAG framework
library.

Hard rule: no framework name is hardcoded into control flow. Adding NCA ECC v3 or a new
regulator is a data PR touching only `/frameworks` — zero architectural change. If it
requires code, the engine has a bug.

## Consequences

**Positive**
- New frameworks/versions ship as reviewed data, by compliance experts, with no core risk.
- Cross-framework mapping lets one control/evidence satisfy multiple standards at once.
- Audit integrity via pinned framework versions.

**Negative / costs**
- Requires a robust, well-validated canonical schema and import/validation tooling.
- Mapping quality across frameworks needs ongoing expert curation.

## Alternatives considered

- **Hardcode each framework in code.** Rejected: every regulator is an architectural change;
  unmaintainable at thousands of tenants.
- **One framework only, generalize later.** Rejected: regional frameworks (NCA/SAMA/PDPL)
  are core requirements from day one.
