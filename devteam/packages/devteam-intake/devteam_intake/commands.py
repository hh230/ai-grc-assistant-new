"""The intake commands — what Mission Intake receives, never a raw event (ADR 0064).

The Correlator turns a signal into exactly one: CreateMission (no live mission for the ref) or
UpdateMission (a live mission exists). Mission Intake acts on the command; it never has to know how
correlation was decided.
"""

from __future__ import annotations

from dataclasses import dataclass

from devteam_intake.signal import IntakeSignal


@dataclass(frozen=True)
class CreateMission:
    """No live mission for this correlation ref — open a new one from the signal."""

    signal: IntakeSignal


@dataclass(frozen=True)
class UpdateMission:
    """A live mission exists for this correlation ref — absorb the signal into it (ADR 0064)."""

    mission_id: str
    signal: IntakeSignal


IntakeCommand = CreateMission | UpdateMission
