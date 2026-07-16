"""Core data model for the Decision Engine MVP.

The shapes themselves (`UserRequest`, `Intent`, `DecisionPlan`) are shared pipeline
contracts and live in the `pipeline-contracts` package; this module re-exports them so
every existing `decision_engine.models` import keeps working. The engine takes a
`UserRequest` and returns a `DecisionPlan` — a structured, fully explainable description
of *how* the request should be handled. It decides; it never executes. This mirrors the
approved architecture (v2/docs/architecture/decision-engine.md): classify → select
workflow → route → budget → govern → emit plan.
"""

from __future__ import annotations

from pipeline_contracts.decision import DecisionPlan, Intent, UserRequest

__all__ = ["DecisionPlan", "Intent", "UserRequest"]
