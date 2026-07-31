"""IntakeSignal — the single normalized shape every TriggerSource produces (ADR 0063/0064).

A thin envelope of reused parts: the platform TenantContext (entered at the boundary, never the
payload — ADR 0040), a reused CapabilityIntent (what's wanted), the normalized AgentFinding(s), a
stable correlation_ref (the external entity id used to correlate — ADR 0064), and an audit-only
origin label the Foreman never reads.
"""

from __future__ import annotations

from dataclasses import dataclass

from assistant_runtime.intent import CapabilityIntent
from devteam_contracts import AgentFinding
from pipeline_contracts import TenantContext


@dataclass(frozen=True)
class IntakeSignal:
    """One normalized trigger. correlation_ref is required — it is how the Correlator relates this
    trigger to a mission (ADR 0064); its granularity is the source's correlation policy."""

    tenant: TenantContext
    intent: CapabilityIntent
    correlation_ref: str
    origin: str = ""
    findings: tuple[AgentFinding, ...] = ()

    def __post_init__(self) -> None:
        if not self.correlation_ref or not self.correlation_ref.strip():
            raise ValueError("an IntakeSignal must carry a non-empty correlation_ref")
        object.__setattr__(self, "findings", tuple(self.findings))
