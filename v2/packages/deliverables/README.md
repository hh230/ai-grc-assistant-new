# deliverables (V2)

**Structured, exportable GRC deliverables** — product roadmap **P3**. A pure transformation layer that
turns a completed Mission's raw step outputs into a document a customer can act on and an auditor can
trust. It **consumes** `mission-engine` (the mission) and `framework-library` (control codes/titles);
no LLM, no Core change.

## Two deliverables

### Generic `Deliverable` (any capability)
`build_deliverable(mission, title=…)` → a structured document: one **`Section`** per mission step
(headed by its domain step name), each carrying the step's **citations** (`source_ids` — provenance)
and confidence. `render_markdown(deliverable)` exports an audit-ready Markdown document with the
goal / tenant / timestamp header. Every claim traces to its sources (CLAUDE.md §19).

### Flagship `GapMatrix` — **Evidence Mapping** (`control ↔ status ↔ evidence`)
`build_gap_matrix(mission, library)` puts the framework's **required** controls (from the
`identify_controls` step) next to the customer's **evidence** (from the `gather_evidence` step) and
marks each control **covered** or **gap**, with the supporting evidence sources. It reports the
headline **evidence coverage** (`covered / total`). `render_gap_matrix_markdown(matrix)` exports it.

**Honest naming — this is *evidence mapping*, not a compliance assessment.** The deterministic
status is *whether supporting evidence was found in the corpus* (a lexical mapping), **not** an
attestation of compliance. That is why the output is titled *Gap Matrix — Evidence Mapping* and
carries a disclaimer. The nuanced assessment is the mission's own `compute_gap` (LLM) synthesis.

```
| Control | Title                  | Status  | Evidence   |
|---------|------------------------|---------|------------|
| A.8.5   | Secure authentication  | covered | doc-acme-1 |
| A.8.24  | Use of cryptography    | gap     | —          |
```

**Coverage is deterministic and honest.** The default `lexical_coverage` is a transparent lexical
first pass (a control is covered when a significant word of its title appears in the gathered
evidence). It is **not** a legal attestation — it says which controls have *supporting evidence in the
corpus*. The mission's own `compute_gap` synthesis (an LLM step) gives the nuanced narrative, and a
smarter classifier can be injected via the `coverage` parameter.

## Export (DOCX + PDF)

`gap_matrix_to_docx` / `deliverable_to_docx` (via `python-docx`) and `gap_matrix_to_pdf` /
`deliverable_to_pdf` (via `reportlab`) each return the file as **`bytes`** — no filesystem I/O, so the
caller writes it to an HTTP response, an object store, or a file. All four mirror the Markdown exactly,
so every export carries the same content and provenance. These are the artifacts a customer downloads.

## A standalone layer — not coupled to the Assistant

`deliverables` depends only on `mission-engine` + `framework-library` — **not** on the Assistant or
any tool. It transforms `Mission → Deliverable → Markdown/DOCX`. Any consumer calls it directly (a
REST API, a CLI, a batch job, a scheduler), so it is deliberately not wired *inside* `grc-assistant`.

## Why now

P3 was deliberately sequenced **after** the capabilities read the customer's own data (P1
integration): a structured deliverable built on general knowledge is form without substance. The Gap
Matrix is meaningful because the evidence is the **customer's own**.

## Tests

`uv run pytest` drives a completed gap-assessment mission through the real Mission Engine (scripted
step results) and asserts the matrix marks covered vs. gap correctly, the coverage headline, a
pluggable classifier, and the Markdown exports. No LLM, no database. `ruff` + `mypy --strict` clean.
