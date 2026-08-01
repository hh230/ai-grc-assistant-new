"""The Tool contract (CLAUDE.md §9).

A **Tool** is a self-contained, schema-validated business capability with a declared
side-effect profile, invoked with a required `TenantContext` (ADR 0040 §5 — a tool called
from any of the six callers always carries a tenant). It does one cohesive thing and depends
on the Services Layer, never on a route handler, a UI, or an LLM SDK.

The Registry **catalogs and resolves** tools; it never invokes them (ADR 0042 §5, §9). A
resolved `Tool` is invoked by its *caller* — in a later step, the executor behind the Mission
Engine's `ExecutionPort`. Keeping invocation out of the Registry is what lets the Registry
know nothing about execution or missions.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pipeline_contracts import TenantContext

from tool_registry.spec import ToolSpec


@runtime_checkable
class Tool(Protocol):
    """A callable capability plus its catalog metadata. Implementations validate `payload`
    against their own input schema and return a schema-valid result (CLAUDE.md §9); the
    Registry does not perform that validation and never calls `invoke` itself."""

    @property
    def spec(self) -> ToolSpec: ...

    def invoke(
        self, payload: dict[str, object], tenant: TenantContext
    ) -> dict[str, object]: ...
