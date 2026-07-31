"""The Supervisor — one controller above all agents (§11).

The organization's health authority. It **supervises agents; it never replaces the Runtime** (owner
constraint): it reads the FROZEN ``RuntimeStateView``, computes health, detects stalled agents and
missions, escalates them, and drives an observable heartbeat mission. Recovery is an injected seam —
when wired, it acts through the Mission Engine's own public API (e.g. ``cancel`` a stalled mission),
never by reaching inside the engine. Detection is separate from recovery; a healthy run does nothing
but heartbeat.

This is the controller face of supervision; the ``SupervisorAgent`` (the SUPERVISION step the
heartbeat runs) is the observable face. Both read the same ``HealthReport``.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from devteam_contracts import platform_tenant
from mission_engine.lifecycle import is_terminal
from mission_engine.mission import Mission

from devteam_organization.health import HealthReport, assess_health
from devteam_organization.runtime import OrganizationRuntime

_LOG = logging.getLogger("devteam.organization.supervisor")

# Given a stalled mission id, attempt recovery; return True if it was recovered. Injected so that
# the default (escalate-only) stays safe, and a composition can wire a real engine-backed recovery.
RecoveryAction = Callable[[str], bool]


@dataclass(frozen=True)
class SupervisionOutcome:
    """What one supervision pass observed and did — all real, all from the view."""

    report: HealthReport
    escalated_agents: tuple[str, ...]
    escalated_missions: tuple[str, ...]
    recovered_missions: tuple[str, ...]

    @property
    def healthy(self) -> bool:
        return self.report.healthy


def _log_alert(message: str) -> None:
    _LOG.warning("supervisor: %s", message)


class Supervisor:
    """Watches the organization's health over the live view. Construct with the runtime it
    supervises; call ``supervise`` for one pass, ``heartbeat`` for an observable health mission."""

    def __init__(
        self,
        runtime: OrganizationRuntime,
        *,
        on_alert: Callable[[str], None] = _log_alert,
        recover: RecoveryAction | None = None,
        clock: Callable[[], float] = time.time,
        stall_after_s: float = 900.0,
    ) -> None:
        self._runtime = runtime
        self._on_alert = on_alert
        self._recover = recover
        self._clock = clock
        self._stall_after_s = stall_after_s

    def check(self) -> HealthReport:
        """One read-only health assessment over the live view — the heartbeat's facts."""
        return assess_health(
            self._runtime.view, now=self._clock(), stall_after_s=self._stall_after_s
        )

    def supervise(self) -> SupervisionOutcome:
        """One supervision pass: assess health, escalate every stall, and attempt recovery on
        stalled missions when a recovery action is wired. A healthy platform escalates nothing."""
        report = self.check()
        for agent_key in report.stalled_agents:
            self._on_alert(f"stalled agent {agent_key}")
        recovered: list[str] = []
        for mission_id in report.stalled_missions:
            self._on_alert(f"stalled mission {mission_id}")
            if self._recover is not None and self._recover(mission_id):
                recovered.append(mission_id)
        return SupervisionOutcome(
            report=report,
            escalated_agents=report.stalled_agents,
            escalated_missions=report.stalled_missions,
            recovered_missions=tuple(recovered),
        )

    def heartbeat(self) -> Mission:
        """Run the Supervisor's health check as a real, observed mission — its live pulse in the
        Dashboard. Real work over real runtime facts; never fabricated activity."""
        return self._runtime.run_health_check()


def engine_recovery(
    runtime: OrganizationRuntime, *, reason: str = "supervisor: stalled"
) -> RecoveryAction:
    """A recovery action that cancels a stalled mission through the Mission Engine's PUBLIC API
    (``get`` then ``cancel``) — fail-safe, never reaching inside the engine. Returns False when the
    mission is unknown or already terminal (nothing to recover)."""

    def recover(mission_id: str) -> bool:
        tenant = platform_tenant("org-supervisor")
        mission = runtime.engine.get(mission_id, tenant)
        if mission is None or is_terminal(mission.status):
            return False
        runtime.engine.cancel(mission, reason)
        return True

    return recover
