# framework-library (V2)

The **first real GRC tool** (ADR 0050) — and the home of "frameworks are data, not code"
(CLAUDE.md §13). It represents compliance frameworks as **data** and exposes one deterministic,
read-only `Tool` over them: look up controls by **code**, **theme**, or **title keyword**, with the
matched control ids returned as provenance.

```
instruction ("A.8.5" | "Technological" | "authentication" | "")
        │
        ▼
ControlLibraryTool.invoke ─→ FrameworkLibrary.get(framework) ─→ Control lookup ─→ ToolStepResult
```

It plugs into the frozen execution path unchanged: it satisfies `tool_registry.Tool`, is registered
in the `ToolRegistry`, and a plan step routes to it by name via `PlanStep.tool` (ADR 0048):

    Mission → ExecutionPort → RegistryExecutor → ToolRegistry → ControlLibraryTool → real controls

## What it is (and is not)

- **Is:** a deterministic **catalog** — control codes, titles, and themes — you look up exactly. No
  LLM, no database, no network. Runtime dependencies are the pure `tool-registry` +
  `pipeline-contracts` only (ADR 0049 is what lets a leaf tool speak the tool-step contract without
  the LLM stack).
- **Is not:** the source of verbatim normative control **text**. That copyrighted prose is the
  **Pipeline Tool**'s grounded-retrieval job (RAG over the imported standard). The library is the
  *catalog*; the pipeline is the *grounded prose*.

## Frameworks are data

A framework is a JSON file matching the repo's definition schema
(`{id, name, version, region, languages, controls[{id, code, title, domain, requirements[],
evidence_expectations[]}]}`). `FrameworkLibrary.from_bundled()` loads every file in `data/`.

**Adding a framework is dropping a data file into `data/` — no code change** (enforced by
`test_a_new_framework_is_added_as_data_not_code`; CIS v8 and NIST CSF 2.0 below were each added as a
single JSON file, no loader or tool change).

**Bundled frameworks** (all loaded from `data/` with zero framework-specific code):

| id | framework | rows |
|---|---|---|
| `framework:iso_27001` | ISO/IEC 27001:2022 — full Annex A | **93** controls (Org 37 · People 8 · Physical 14 · Tech 34) |
| `framework:cis` | CIS Critical Security Controls v8 | **18** controls |
| `framework:nist_csf` | NIST Cybersecurity Framework 2.0 | **22** categories (themed by Function: Govern/Identify/Protect/Detect/Respond/Recover) |

## Usage

```python
from framework_library import ControlLibraryTool, FrameworkLibrary
from tool_registry import ToolRegistry

registry = ToolRegistry()
registry.register(ControlLibraryTool(FrameworkLibrary.from_bundled()))

# …then a mission step names it: PlanStep(instruction="A.8.5", tool="framework_control_library")
```

## Tests

`uv run pytest` — models (lookups), library (bundled catalog complete + correct, malformed fails
loud, a new framework is data not code), tool (code/theme/keyword/empty/no-match), and a mission
**E2E** through the real `RegistryExecutor` with the tool named by `PlanStep.tool`. No Postgres
needed. `ruff` + `mypy --strict` clean.
