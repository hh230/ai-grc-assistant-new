"""The real, always-on Saudi Regulations Ingestion process (Knowledge Intelligence KI-P6,
ADR-0030): wires the pure ``grc_regulation_ingestion.AutonomousRegulationIngestionWorker``
against apps/web's live Postgres schema, a real Google Drive index-catalog download, and a
real (polite, robots.txt-respecting) fetch of the official Board of Experts law portal — then
drives it from an actual infinite loop with graceful shutdown on SIGINT/SIGTERM.

A second, independent composition root alongside ``knowledge_learning_loop.py`` — not folded
into the Knowledge Worker's own tick — because these are a different content type (whole
regulations, not individual GRC question answers) on an independent cadence, sharing only the
underlying architecture (scheduler, control seam, event sink) and the same database, per
explicit instruction not to build a parallel worker system.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from grc_knowledge_worker import LearningCycleScheduler
from grc_persistence_web import (
    Database,
    NewRegulationSection,
    RegulationDocumentRepository,
    RegulationSectionRepository,
    RegulationSourceRepository,
    RegulationSourceVersionRepository,
    WorkerControlRepository,
    WorkerEventRepository,
)
from grc_regulation_ingestion import AutonomousRegulationIngestionWorker
from grc_regulation_ingestion_adapters import (
    BoeRegulationPageFetcher,
    DriveIndexCatalogSource,
    RegulationGapRunner,
)
from grc_regulatory_crawlers.http_fetcher import UrllibHttpFetcher

from .knowledge_learning_loop import _load_dev_env  # reuse, not reimplement

logger = logging.getLogger("grc_worker.regulation_ingestion_loop")

_DEFAULT_CYCLE_INTERVAL_HOURS = 24.0
_DEFAULT_POLL_INTERVAL_SECONDS = 3600.0


class RegulationWorkerConfigurationError(RuntimeError):
    """The environment does not carry enough configuration to run the ingestion pipeline."""


@dataclass(frozen=True)
class RegulationWorkerSettings:
    """Everything the composition root needs from the environment. Fails fast (CLAUDE.md §22)
    rather than falling back silently."""

    database_url: str
    drive_file_id: str
    cycle_interval: timedelta
    poll_interval_seconds: float

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> RegulationWorkerSettings:
        environ: Mapping[str, str] = os.environ if env is None else env

        database_url = environ.get("DATABASE_URL", "").strip()
        if not database_url:
            raise RegulationWorkerConfigurationError(
                "DATABASE_URL is not set; the Regulation Ingestion pipeline needs a connection "
                "to apps/web's schema (the same one the Knowledge Worker uses)"
            )
        drive_file_id = environ.get("GRC_REGULATION_INDEX_DRIVE_FILE_ID", "").strip()
        if not drive_file_id:
            raise RegulationWorkerConfigurationError(
                "GRC_REGULATION_INDEX_DRIVE_FILE_ID is not set; the pipeline needs the Google "
                "Drive file id of the Saudi regulations index PDF"
            )
        cycle_interval = timedelta(
            hours=float(
                environ.get(
                    "GRC_REGULATION_WORKER_CYCLE_INTERVAL_HOURS",
                    str(_DEFAULT_CYCLE_INTERVAL_HOURS),
                )
            )
        )
        poll_interval_seconds = float(
            environ.get(
                "GRC_REGULATION_WORKER_POLL_INTERVAL_SECONDS",
                str(_DEFAULT_POLL_INTERVAL_SECONDS),
            )
        )
        return cls(
            database_url=database_url,
            drive_file_id=drive_file_id,
            cycle_interval=cycle_interval,
            poll_interval_seconds=poll_interval_seconds,
        )


def build_worker(
    settings: RegulationWorkerSettings, *, database: Database
) -> AutonomousRegulationIngestionWorker:
    """Assemble the real ingestion loop: the real Drive index download, the polite BOE page
    fetcher/parser, the fetch/parse/store runner, and the scheduler — reusing
    ``grc_regulation_ingestion``/``grc_regulation_ingestion_adapters`` exactly as built, and
    the same ``grc_knowledge_worker`` scheduler/control/event types the Knowledge Worker
    uses, nothing reimplemented here."""
    catalog_source = DriveIndexCatalogSource(UrllibHttpFetcher(), file_id=settings.drive_file_id)
    fetcher = BoeRegulationPageFetcher(UrllibHttpFetcher())
    events = WorkerEventRepository(database)
    runner = RegulationGapRunner(
        fetcher=fetcher,
        sources=RegulationSourceRepository(database),
        versions=RegulationSourceVersionRepository(database),
        documents=RegulationDocumentRepository(database),
        sections=RegulationSectionRepository(database),
        new_section=_new_regulation_section_factory(),
        event_sink=events,
    )

    return AutonomousRegulationIngestionWorker(
        catalog_source=catalog_source,
        runner=runner,
        scheduler=LearningCycleScheduler(interval=settings.cycle_interval),
        control=WorkerControlRepository(database, table="regulation_worker_control"),
        event_sink=events,
    )


def _new_regulation_section_factory() -> type[NewRegulationSection]:
    """``grc_regulation_ingestion_adapters`` (an adapters package) never imports
    ``grc_persistence_web`` (a sibling adapters package) directly — its ``RegulationGapRunner``
    only depends on ``NewSectionFactory``'s Protocol shape. Only this composition root, which
    already depends on both packages, wires the concrete dataclass in."""
    return NewRegulationSection


async def run_forever(
    worker: AutonomousRegulationIngestionWorker,
    *,
    poll_interval_seconds: float,
    stop_event: asyncio.Event,
) -> None:
    """The real "repeat" step — same fail-safe shape as
    ``knowledge_learning_loop.run_forever``: one tick raising an exception the injected runner
    did not already isolate is logged and the loop continues at the next poll rather than
    crashing the whole process."""
    while not stop_event.is_set():
        now = datetime.now(timezone.utc)
        try:
            outcome = await worker.tick(now=now)
        except Exception:  # noqa: BLE001 - fail-safe: one bad tick must not kill the process
            logger.exception("regulation ingestion tick failed; will retry next poll")
        else:
            if outcome.ran:
                logger.info(
                    "regulation ingestion cycle ran: %d regulation(s) processed, %d stored",
                    len(outcome.outcomes),
                    outcome.stored_count,
                )
            else:
                logger.debug("regulation ingestion cycle skipped: %s", outcome.reason)

        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=poll_interval_seconds)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    _load_dev_env()
    settings = RegulationWorkerSettings.from_env()

    database = await Database.connect(settings.database_url)
    worker = build_worker(settings, database=database)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    logger.info(
        "regulation ingestion worker starting: cycle_interval=%s poll_interval_seconds=%s",
        settings.cycle_interval,
        settings.poll_interval_seconds,
    )
    try:
        await run_forever(
            worker, poll_interval_seconds=settings.poll_interval_seconds, stop_event=stop_event
        )
    finally:
        await database.close()
        logger.info("regulation ingestion worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
