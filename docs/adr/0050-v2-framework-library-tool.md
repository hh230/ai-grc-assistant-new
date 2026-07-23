# ADR 0050: Framework Library tool — frameworks as data, the first real GRC tool (ISO 27001:2022)

- Status: **Accepted — implemented** (2026-07-20)
- Date: 2026-07-20
- Deciders: Architecture (autonomous execution mandate)
- Related: CLAUDE.md §13 (Framework Engine — "frameworks are data, not code"), §9/§10 (Tools /
  Registry); ADR 0042 (`ExecutionPort`), ADR 0048 (per-step `PlanStep.tool` — how a plan names this
  tool), ADR 0049 (the `ToolStepResult` contract this tool speaks); `tool-registry`, `pipeline-tool`
  (`RegistryExecutor`), `frameworks/iso-27001/2022/definition.json` (the reused data schema).

---

## Context

The Execution Platform is wired (grc-assistant Step A) and a plan step can name its tool (ADR 0048),
but the only real tool is `PipelineTool` (grounded RAG over source documents). The roadmap's Phase 3
("Real Tools") begins with **control libraries** (ISO / NIST / CIS / PCI / SOC2). These are *not* a
RAG concern: a control library is **deterministic structured reference data** — a catalog of control
codes, titles and themes you look up exactly, with provenance — distinct from the grounded normative
text the Pipeline Tool already retrieves from the imported PDFs.

CLAUDE.md §13 is explicit: **frameworks are data, not code** — "adding or updating a framework is a
data/config operation, never an architectural change," and "no framework name is hardcoded into
control flow." The repo already defines the data schema
(`frameworks/iso-27001/2022/definition.json`: `{id, name, version, region, languages,
controls[{id, code, title, domain, requirements[], evidence_expectations[]}]}`).

## Decision

Add a new leaf package **`framework-library`** that represents compliance frameworks as data and
exposes **one deterministic, read-only Tool** over them — many frameworks, one tool.

1. **Domain (pure dataclasses):** `Framework` (id, name, version, region, languages, controls) and
   `Control` (id, code, title, domain/theme, optional requirements & evidence_expectations). Reuses
   the existing `definition.json` schema so V1 seed data and V2 bundled data are the same shape.
2. **`FrameworkLibrary`** loads framework **definitions from JSON data files** — a bundled `data/`
   directory plus any caller-supplied paths. Lookup/search is pure: by code, by theme, by title
   keyword. **A new framework (NIST, CIS, PCI, SOC2) is added by dropping in a data file — no code
   change** (§13 hard rule, enforced by a test).
3. **Bundled data:** the **complete ISO/IEC 27001:2022 Annex A catalog — all 93 controls** (A.5
   Organizational ×37, A.6 People ×8, A.7 Physical ×14, A.8 Technological ×34): code, title, and
   theme. The verbatim normative control **text is deliberately not reproduced** (copyright) — that
   grounded text is the Pipeline Tool's job, retrieved from the imported source document. The library
   is the *catalog*; the pipeline is the *grounded prose*.
4. **`ControlLibraryTool`** implements the frozen `tool_registry.Tool` protocol (`spec` READ_ONLY;
   `invoke(payload, tenant) -> dict`). It reads the step's opaque `instruction` as a control query —
   an exact code (`A.8.5`), a theme (`Technological`), or a title keyword — and returns a
   `ToolStepResult` (ADR 0049): a readable summary in `output`, the matched control ids in
   `source_ids` (provenance), and a warning when nothing matches. Deterministic ⇒ `confidence` stays
   `None`; grounding is the exact `source_ids`, not a probability.
5. **Dependencies:** runtime = `tool-registry` + `pipeline-contracts` **only** — no LLM stack (the
   payoff of ADR 0049). `mission-engine`/`pipeline-tool` are **dev-only**, used by the E2E test that
   drives a real Mission through `RegistryExecutor`, the tool named by `PlanStep.tool` (ADR 0048).

## Out of scope / deferred

- **Cross-framework mapping** (ISO ↔ NIST ↔ NCA, §13) — a later tool/data addition; this slice is a
  single-framework catalog + lookup.
- **The verbatim requirement text / evidence expectations** for all 93 controls — the model carries
  the fields (and the 2-control seed populates them) but the bundled full catalog leaves them empty;
  grounded text comes from the Pipeline Tool.
- **NIST / CIS / PCI / SOC2 data** — added next as data files, no code change (the whole point).
- **Wiring the tool into the Risk Assessment capability's `collect_context` step** — a capability
  change (its own slice), not this tool's.

## Consequences

**Positive** — the first real, non-LLM GRC tool; proves the "frameworks as data" architecture end to
end (a mission step returns real ISO 27001 controls); establishes the pattern every further framework
reuses as pure data. **Negative** — a bundled 93-row data file must be kept correct against the
standard; it carries codes/titles/themes only (reference metadata), reducing that surface.

## Implementation Status

**Implemented (2026-07-20).** New `v2/packages/framework-library` package: `models.py`, `library.py`,
`tool.py`, `errors.py`, bundled `data/iso_27001_2022.json` (93 controls). Tests: models, library
(load/lookup/search + "a new framework is data, not code"), tool invoke (code/theme/keyword/no-match),
and a mission E2E through the real `RegistryExecutor` with the tool named by `PlanStep.tool`. `ruff` +
`mypy --strict` clean; all green.
