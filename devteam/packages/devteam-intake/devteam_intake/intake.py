"""Mission Intake — receives an IntakeCommand and produces a governed Dev Mission (ADR 0063/0064).

CreateMission -> build (goal, Plan) via the reused CapabilitySelector + MissionCatalog and drive it
through the MissionDriver (create + plan + execute, idempotent by the ref); the correlation ref is
registered as part of that transition, before execution. UpdateMission -> emit MissionSignalReceived
on the existing mission (record-only). Mission Intake never sees a raw event, nor the origin.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from assistant_runtime.mission_catalog import MissionCatalog
from assistant_runtime.ports import MissionDriver
from assistant_runtime.selector import CapabilitySelector
from event_bus.bus import EventBus
from mission_engine import MissionEngine
from mission_engine.mission import Mission
from pipeline_contracts import TenantContext

from devteam_intake.commands import CreateMission, IntakeCommand, UpdateMission
from devteam_intake.correlation import CorrelationRepository, MissionCorrelator
from devteam_intake.events import MissionSignalReceived
from devteam_intake.signal import IntakeSignal
from devteam_intake.triggers import TriggerSource


@dataclass(frozen=True)
class IntakeOutcome:
    """What admit returns: the mission id, and whether a mission was created or updated."""

    mission_id: str
    action: str  # "created" | "updated"


class MissionIntake:
    """Turns an IntakeCommand into a governed Dev Mission (create) or an audited signal against an
    existing one (update, record-only). It receives a command, never a raw event (ADR 0064)."""

    def __init__(
        self,
        *,
        selector: CapabilitySelector,
        mission_catalog: MissionCatalog,
        driver: MissionDriver,
        repository: CorrelationRepository,
        events: EventBus,
    ) -> None:
        self._selector = selector
        self._mission_catalog = mission_catalog
        self._driver = driver
        self._repository = repository
        self._events = events

    def admit(self, command: IntakeCommand) -> IntakeOutcome:
        if isinstance(command, CreateMission):
            return self._create(command.signal)
        return self._update(command)

    def _create(self, signal: IntakeSignal) -> IntakeOutcome:
        capability = self._selector.select(signal.intent)
        goal, plan = self._mission_catalog.build(
            capability.resolver, dict(signal.intent.inputs), signal.tenant
        )
        tenant: TenantContext = signal.tenant
        ref = signal.correlation_ref

        def _txn(engine: MissionEngine) -> Mission:
            # No idempotency_key: correlation (the CorrelationRepository) is the dev team's dedup, a
            # distinct concern from the Core's exact-event idempotency (ADR 0064). Register the ref
            # BEFORE execution so a terminal event during execute reaches the deactivator.
            mission = engine.create(goal, tenant)
            self._repository.register(tenant, ref, mission.id)
            engine.plan(mission, plan)
            return engine.execute(mission)

        mission = self._driver.run_transition(_txn)
        return IntakeOutcome(mission_id=mission.id, action="created")

    def _update(self, command: UpdateMission) -> IntakeOutcome:
        signal = command.signal
        finding = signal.findings[0] if signal.findings else None
        self._events.publish(
            MissionSignalReceived(
                trace_id=command.mission_id,
                tenant_id=signal.tenant.tenant_id,
                mission_id=command.mission_id,
                origin=signal.origin,
                finding_kind=finding.kind if finding is not None else "",
                finding_summary=finding.summary if finding is not None else "",
            )
        )
        return IntakeOutcome(mission_id=command.mission_id, action="updated")


class IntakeGateway:
    """The single entry point: normalize (per source) -> correlate -> admit. Mission Intake still
    only ever receives a command; this wires the boundary end to end (ADR 0063/0064)."""

    def __init__(self, *, correlator: MissionCorrelator, intake: MissionIntake) -> None:
        self._correlator = correlator
        self._intake = intake

    def submit(self, raw: Mapping[str, object], source: TriggerSource) -> IntakeOutcome:
        signal = source.normalize(dict(raw))
        return self._intake.admit(self._correlator.correlate(signal))
