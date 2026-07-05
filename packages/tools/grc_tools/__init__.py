"""grc_tools — Tools (first-class business capabilities) and the Tool Registry (CLAUDE.md §9-10).

Business capabilities are implemented as ``Tool`` subclasses and invoked exclusively through a
``ToolRegistry``, so the Orchestrator, the API, the UI, the Workflow Engine, Scheduled Jobs, and
Tests all call the same capability the same way. Concrete tools live in outer packages (e.g.
``packages/regulatory-intelligence-adapters``); this package only defines the contract and the
registry, and never imports an LLM SDK or a concrete persistence adapter directly.
"""

from __future__ import annotations

from .context import ToolCaller, ToolContext
from .exceptions import (
    ToolError,
    ToolInputValidationError,
    ToolNotFoundError,
    ToolPermissionDeniedError,
)
from .invocation import (
    InvocationStatus,
    NullToolInvocationRecorder,
    ToolInvocationRecord,
    ToolInvocationRecorder,
)
from .registry import ToolRegistry
from .tool import Tool, ToolOutcome

__all__ = [
    "ToolCaller",
    "ToolContext",
    "Tool",
    "ToolOutcome",
    "ToolRegistry",
    "ToolError",
    "ToolNotFoundError",
    "ToolPermissionDeniedError",
    "ToolInputValidationError",
    "InvocationStatus",
    "ToolInvocationRecord",
    "ToolInvocationRecorder",
    "NullToolInvocationRecorder",
]
