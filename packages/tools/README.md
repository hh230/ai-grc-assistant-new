# grc-tools

Tools (first-class business capabilities) and the Tool Registry (CLAUDE.md §9-10).

- `context.py` — `ToolContext` (tenant/auth) and `ToolCaller` (the six callers).
- `tool.py` — the `Tool` contract: a `grc_domain.platform.ToolDescriptor` (governance metadata),
  typed Pydantic input/output models, and an async `run` returning a `ToolOutcome` (output plus
  confidence/citations/model/usage for the audit trail).
- `invocation.py` — `ToolInvocationRecord` + the `ToolInvocationRecorder` port. Concrete
  recorders (e.g. against `packages/persistence-web`) are bound at the composition root.
- `registry.py` — `ToolRegistry`: register/get/list, and `invoke()`, which authorizes,
  validates, executes, and unconditionally audits every call — including denied/failed ones.

Concrete tool implementations (Policy Intelligence, Regulatory Intelligence, ...) live in
outer packages and depend on this one; this package never imports an LLM SDK or a concrete
persistence adapter.

See [`docs/architecture/PROJECT_SKELETON.md`](../../docs/architecture/PROJECT_SKELETON.md),
[`CLAUDE.md`](../../CLAUDE.md), and `docs/adr/0017-tool-registry-and-policy-intelligence-roster.md`.
