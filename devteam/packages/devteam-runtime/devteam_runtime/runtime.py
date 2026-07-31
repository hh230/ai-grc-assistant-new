"""``DevMissionRuntime`` — the dev team's composition root over the FROZEN v2 Core (ADR 0061).

Phase 0 wires the in-memory composition (no Postgres): the frozen ``MissionEngine`` driving the
frozen lifecycle over ``InMemoryMissionStore``, a ``DevToolExecutor`` resolving Dev Tools via the
frozen ``ToolRegistry``, the frozen ``InProcessEventBus``, and the frozen ``MissionAuditSink``
recording every mission event. Dev work runs as a governed Mission under ``tenant:platform``,
inheriting the lifecycle, human-gate, events, and audit for free — no new lifecycle/engine/
registry/bus.

The durable composition (Postgres + Transactional Outbox) is ``mission_integration.MissionRuntime``
with ``executor=DevToolExecutor(...)``; it lands in a later phase behind the same seam and needs a
database. This module keeps Phase 0 runnable and green with no external services.
"""

from __future__ import annotations

from pathlib import Path

from devteam_contracts import platform_tenant
from devteam_tools import CHECK_REPO_HEALTH, CheckRepoHealthTool
from event_bus import ALL_EVENTS, InProcessEventBus
from mission_engine import MissionEngine
from mission_engine.adapters import InMemoryMissionStore
from mission_engine.mission import Mission
from mission_engine.plan import Plan, PlanStep
from mission_integration.audit import MissionAuditSink
from tool_registry import ToolRegistry

from devteam_runtime.executor import DevToolExecutor


def build_dev_registry(repo_root: Path | str) -> ToolRegistry:
    """Register the Phase-0 Dev Tools. New tools appear by registering here — the plugin entry point
    (CLAUDE.md §17); no core change."""
    registry = ToolRegistry()
    registry.register(CheckRepoHealthTool(repo_root))
    return registry


class DevMissionRuntime:
    """In-memory composition of the frozen Core for dev missions. Construct once with the repo the
    team maintains; call ``run_plan`` to drive a dev mission end to end. ``audit`` exposes the
    recorded mission-event stream (the reused audit terminal)."""

    def __init__(self, repo_root: Path | str) -> None:
        self._registry = build_dev_registry(repo_root)
        self._events = InProcessEventBus()
        self._audit = MissionAuditSink()
        self._events.subscribe(ALL_EVENTS, self._audit.record)
        self._engine = MissionEngine(
            InMemoryMissionStore(),
            DevToolExecutor(self._registry, default_tool=CHECK_REPO_HEALTH),
            events=self._events,
        )

    @property
    def audit(self) -> MissionAuditSink:
        return self._audit

    @property
    def engine(self) -> MissionEngine:
        return self._engine

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    def run_plan(
        self,
        goal: str,
        steps: tuple[PlanStep, ...],
        *,
        principal_id: str = "devteam-foreman",
    ) -> Mission:
        """Open a dev mission under tenant:platform, plan it, and drive it to completion (or the
        first human gate). The full governed path — create → plan → execute — persisted and audited
        exactly like any product mission."""
        tenant = platform_tenant(principal_id)
        mission = self._engine.create(goal, tenant)
        self._engine.plan(mission, Plan(steps=steps))
        return self._engine.execute(mission)
