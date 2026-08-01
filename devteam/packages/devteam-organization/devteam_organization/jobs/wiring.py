"""Compose the jobs and the scheduler — jobs consume connectors from the registry (§11).

Builds all twelve departmental jobs from the config's cadences/thresholds, handing each the shared
``ConnectorRegistry`` (jobs fetch evidence through it — never a direct integration), then a
``JobScheduler`` wired to the existing runtime. Adding a job is a line here.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from mission_engine.mission import Mission

from devteam_organization.connectors import ConnectorConfig, ConnectorRegistry
from devteam_organization.jobs.agent_jobs import (
    CEOJob,
    CTOJob,
    DevTeamJob,
    GRCExpertJob,
    QAJob,
    SupervisorJob,
)
from devteam_organization.jobs.ciso_jobs import (
    DependencySecurityJob,
    RuntimeHealthJob,
    SecretExposureJob,
    SecurityHeadersJob,
    TlsCertificateJob,
    WebsiteHealthJob,
)
from devteam_organization.jobs.framework import Job, Schedule
from devteam_organization.jobs.journal import JobJournalSink
from devteam_organization.jobs.scheduler import JobScheduler, open_mission_via_runtime


def build_default_jobs(config: ConnectorConfig, registry: ConnectorRegistry) -> list[Job]:
    """Every departmental job, cadence-configured, each wired to the connector registry it reads.
    Per-job cadence overrides (keyed by job id) win over the named defaults."""

    def sched(job_id: str, base: float, *, every_tick: bool = False) -> Schedule:
        return Schedule(config.cadence_for(job_id, base), every_tick=every_tick)

    default, hourly, slow = config.cadence_default, config.cadence_hourly, config.cadence_slow
    return [
        WebsiteHealthJob(
            registry,
            schedule=sched(WebsiteHealthJob.id, default),
            failure_threshold=config.website_failure_threshold,
        ),
        SecurityHeadersJob(registry, schedule=sched(SecurityHeadersJob.id, default)),
        TlsCertificateJob(
            registry,
            schedule=sched(TlsCertificateJob.id, slow),
            warn_days=config.tls_expiry_warn_days,
        ),
        DependencySecurityJob(registry, schedule=sched(DependencySecurityJob.id, slow)),
        SecretExposureJob(registry, schedule=sched(SecretExposureJob.id, hourly)),
        RuntimeHealthJob(registry, schedule=sched(RuntimeHealthJob.id, default)),
        CTOJob(registry, schedule=sched(CTOJob.id, default)),
        QAJob(registry, schedule=sched(QAJob.id, default)),
        GRCExpertJob(registry, schedule=sched(GRCExpertJob.id, default)),
        DevTeamJob(registry, schedule=sched(DevTeamJob.id, default)),
        CEOJob(
            registry,
            schedule=sched(CEOJob.id, default),
            open_missions_threshold=config.ceo_open_missions_threshold,
            incident_threshold=config.ceo_incident_threshold,
        ),
        SupervisorJob(registry, schedule=sched(SupervisorJob.id, 0.0, every_tick=True)),
    ]


def build_scheduler(
    run_mission: Callable[..., Mission],
    config: ConnectorConfig,
    registry: ConnectorRegistry,
    *,
    repo_root: Path | str = ".",
    journal: JobJournalSink | None = None,
    clock: Callable[[], float] = time.time,
) -> JobScheduler:
    """Wire the scheduler: jobs read the registry and open real missions via ``run_mission``. No new
    runtime — the scheduler only schedules."""
    jobs = build_default_jobs(config, registry)
    return JobScheduler(
        jobs,
        open_mission=open_mission_via_runtime(run_mission),
        repo_root=repo_root,
        journal=journal,
        clock=clock,
    )
