"""Backward-compatibility shim (Phase 12). The `GenerationProvider` port moved to
`pipeline_contracts.generation` — the single source of truth both the AI Orchestrator and
the Generation Engine depend on. Import it from `pipeline_contracts` in new code."""

from __future__ import annotations

from pipeline_contracts import GenerationProvider

__all__ = ["GenerationProvider"]
