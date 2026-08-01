"""Runtime connector — read-only view of the running platform (§11).

Reads the local runtime: LaunchAgent worker status (via the shared worker probe) and, when a live
``RuntimeStateView`` is available, stalled agents/missions, open + awaiting-approval missions, and
incidents (blocked agents). Always available (reads local state), so it reports what it can
observe — the consuming jobs (CISO runtime, Supervisor, CEO, DevTeam) decide what matters.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from devteam_observability import RuntimeStateView
from devteam_protocol import AgentRole

from devteam_organization.connectors.framework import ConnectorResult, ConnectorType
from devteam_organization.connectors.probes import WorkerProbe
from devteam_organization.health import assess_health

_TERMINAL = frozenset({"completed", "failed", "cancelled"})


class RuntimeConnector:
    id = "runtime"
    name = "Runtime"
    type = ConnectorType.RUNTIME
    owner = AgentRole.SUPERVISOR

    def __init__(
        self,
        worker_probe: WorkerProbe,
        view_provider: Callable[[], RuntimeStateView | None] | None = None,
        *,
        stall_after_s: float = 900.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._worker_probe = worker_probe
        self._view_provider = view_provider
        self._stall_after_s = stall_after_s
        self._clock = clock

    @property
    def enabled(self) -> bool:
        return True  # local runtime is always observable

    def fetch(self) -> ConnectorResult:
        workers = [
            {"label": w.label, "running": w.running, "pid": w.pid} for w in self._worker_probe()
        ]
        data: dict[str, object] = {
            "workers": workers,
            "workers_down": [w["label"] for w in workers if not w["running"]],
            "stalled_agents": [],
            "stalled_missions": [],
            "open_missions": 0,
            "awaiting_missions": [],
            "incidents": 0,
        }
        view = self._view_provider() if self._view_provider is not None else None
        if view is not None:
            report = assess_health(view, now=self._clock(), stall_after_s=self._stall_after_s)
            missions = view.missions()
            data["stalled_agents"] = list(report.stalled_agents)
            data["stalled_missions"] = list(report.stalled_missions)
            data["open_missions"] = sum(
                1 for m in missions if str(m.get("status")) not in _TERMINAL
            )
            data["awaiting_missions"] = [
                str(m.get("mission_id"))
                for m in missions
                if m.get("status") == "awaiting_approval"
            ]
            data["incidents"] = sum(
                1 for a in view.agents() if a.get("status") == "blocked"
            )
        return ConnectorResult.okay(data)
