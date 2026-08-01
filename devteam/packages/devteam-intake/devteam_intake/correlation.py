"""Mission Correlation — relate a trigger to an existing mission (ADR 0064).

MissionCorrelator is the boundary Mission Intake depends on: it decides create vs update.
Correlation storage sits behind it — a small in-package CorrelationRepository, not a Port
(Port-Worthiness: one production form). If multiple genuinely different correlation strategies
emerge, we revisit the boundary in a new ADR.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from event_bus.events import DomainEvent
from pipeline_contracts import TenantContext

from devteam_intake.commands import CreateMission, IntakeCommand, UpdateMission
from devteam_intake.signal import IntakeSignal

# Mission lifecycle events that free a correlation entry (the mission is no longer active).
_TERMINAL_EVENTS = frozenset({"mission.completed", "mission.failed", "mission.cancelled"})


class CorrelationRepository:
    """Active correlations: correlation_ref -> the open mission for it, tenant-scoped. A small
    in-package repository, not a Port. In-memory today; a durable form is a later persistence
    decision, never a pre-built abstraction."""

    def __init__(self) -> None:
        self._by_tenant: dict[str, dict[str, str]] = {}

    def register(self, tenant: TenantContext, correlation_ref: str, mission_id: str) -> None:
        self._by_tenant.setdefault(tenant.tenant_id, {})[correlation_ref] = mission_id

    def find_active(self, tenant: TenantContext, correlation_ref: str) -> str | None:
        return self._by_tenant.get(tenant.tenant_id, {}).get(correlation_ref)

    def deactivate(self, tenant: TenantContext, mission_id: str) -> None:
        refs = self._by_tenant.get(tenant.tenant_id, {})
        for ref, active in list(refs.items()):
            if active == mission_id:
                del refs[ref]


@runtime_checkable
class MissionCorrelator(Protocol):
    """The boundary: turn an IntakeSignal into CreateMission or UpdateMission (ADR 0064). Storage is
    a detail behind this seam; realizations may use repository lookup or richer strategies."""

    def correlate(self, signal: IntakeSignal) -> IntakeCommand: ...


class StoreMissionCorrelator:
    """First MissionCorrelator: a live mission for the ref -> UpdateMission, else CreateMission."""

    def __init__(self, repository: CorrelationRepository) -> None:
        self._repository = repository

    def correlate(self, signal: IntakeSignal) -> IntakeCommand:
        active = self._repository.find_active(signal.tenant, signal.correlation_ref)
        if active is None:
            return CreateMission(signal)
        return UpdateMission(mission_id=active, signal=signal)


class CorrelationDeactivator:
    """Frees a correlation entry when its mission ends (ADR 0064). Subscribe handle to the bus; a
    recurrence after closure then opens a fresh mission, not a resurrection of a terminal one."""

    def __init__(self, repository: CorrelationRepository) -> None:
        self._repository = repository

    def handle(self, event: DomainEvent) -> None:
        if event.name in _TERMINAL_EVENTS and event.mission_id:
            self._repository.deactivate(TenantContext(tenant_id=event.tenant_id), event.mission_id)
