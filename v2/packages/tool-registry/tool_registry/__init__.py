"""Rasheed V2 Tool Registry (Phase 15, step 2) — the central catalog of every business
capability (CLAUDE.md §10; ADR 0042 §9).

A **Tool** is a self-contained, schema-validated capability with a declared side-effect
profile, invoked with a `TenantContext`. The **ToolRegistry** is a **pure catalog**: it
registers, versions, discovers, and resolves tools and their metadata. It performs **no
authorization** (no RBAC engine, permission evaluator, or policy framework — that is a future
phase), it never invokes a tool, and it neither imports nor is imported by the Mission Engine.
A caller (the executor behind the Mission Engine's `ExecutionPort`, a later step) resolves a
step to tools via this Registry and invokes them.

Pure domain: no database, no LLM SDK, no framework, no mission/agent/pipeline knowledge.
"""

from tool_registry.errors import (
    InvalidToolSpec,
    ToolAlreadyRegistered,
    ToolNotFound,
    ToolRegistryError,
)
from tool_registry.registry import ToolRegistry
from tool_registry.spec import SideEffectProfile, ToolSpec
from tool_registry.tool import Tool

__all__ = [
    # registry
    "ToolRegistry",
    # contracts
    "Tool",
    "ToolSpec",
    "SideEffectProfile",
    # errors
    "ToolRegistryError",
    "InvalidToolSpec",
    "ToolNotFound",
    "ToolAlreadyRegistered",
]
