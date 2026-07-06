"""The real, always-on Knowledge Worker process (Knowledge Intelligence KI-P4, ADR-0028):
wires the pure ``grc_knowledge_worker.AutonomousKnowledgeWorker`` against apps/web's live
Postgres schema, the Tool-Registry-audited OpenAI synthesizer, and a real (polite,
robots.txt-respecting) HTTP research crawler — then drives it from an actual infinite loop
with graceful shutdown on SIGINT/SIGTERM.

This module is the composition root (CLAUDE.md §5): it is the *only* place in the Knowledge
Intelligence line that constructs concrete infrastructure (a real ``Database`` pool, a real
``OpenAIChatModel``, a real ``UrllibHttpFetcher``) and wires it behind the ports every other
package already depends on only structurally. Every business rule — gap detection, research
planning, extraction validation, idempotent storage — lives in the packages this module only
imports and assembles; nothing is reimplemented here.

Every synthesis call this process makes still flows through the Tool Registry
(``synthesize_knowledge_answer.v1``), so it is authorized, validated, and unconditionally
audited exactly like any other Tool invocation (CLAUDE.md §19) — this composition root does
not create a second, unaudited path to the LLM.
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
from pathlib import Path

from grc_knowledge_intelligence import KnowledgeDiscoveryEngine, KnowledgeQuestion, build_catalog
from grc_knowledge_intelligence_adapters import LlmKnowledgeExtractor, SynthesizeKnowledgeAnswerTool
from grc_knowledge_ontology import build_ontology
from grc_knowledge_research import CatalogedSource, ResearchCoordinator
from grc_knowledge_research_adapters import (
    HttpResearchCrawler,
    KnowledgeGapResearchRunner,
    build_trusted_source_catalog,
)
from grc_knowledge_worker import (
    AutonomousKnowledgeWorker,
    LearningCycleScheduler,
    combine_question_sources,
)
from grc_llm import ChatModel, OpenAIChatModel, OpenAISettings
from grc_persistence_web import Database, KnowledgeItemRepository, PostgresToolInvocationRecorder
from grc_regulatory_crawlers.http_fetcher import UrllibHttpFetcher
from grc_tools import ToolCaller, ToolContext, ToolRegistry

logger = logging.getLogger("grc_worker.knowledge_learning_loop")

_DEFAULT_CYCLE_INTERVAL_HOURS = 24.0
_DEFAULT_POLL_INTERVAL_SECONDS = 3600.0

# The one capability this process invokes through the Tool Registry, permission-gated exactly
# like every other caller of ``synthesize_knowledge_answer`` (ADR-0025).
_GRANTED_TOOL_PERMISSIONS = frozenset({"knowledge_intelligence"})


class WorkerConfigurationError(RuntimeError):
    """The environment does not carry enough configuration to run the Knowledge Worker."""


def _repo_root() -> Path:
    """``apps/worker/src/grc_worker/knowledge_learning_loop.py`` -> repo root, four levels
    up. Overridable via ``GRC_DATA_ROOT`` for deployments that lay the repo out differently
    (e.g. a container image that copies only the data directories alongside the app)."""
    return Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class WorkerSettings:
    """Everything the composition root needs from the environment. Fails fast (CLAUDE.md §22)
    rather than falling back silently — a misconfigured worker should refuse to start, not
    run against the wrong database or an empty data catalog."""

    database_url: str
    data_root: Path
    cycle_interval: timedelta
    poll_interval_seconds: float

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> WorkerSettings:
        environ: Mapping[str, str] = os.environ if env is None else env

        database_url = environ.get("DATABASE_URL", "").strip()
        if not database_url:
            raise WorkerConfigurationError(
                "DATABASE_URL is not set; the Knowledge Worker needs a connection to apps/web's "
                "schema (the same one apps/api's Policy Intelligence wiring uses)"
            )

        data_root = Path(environ.get("GRC_DATA_ROOT", str(_repo_root()))).resolve()
        _require_data_directories(data_root)

        cycle_interval = timedelta(
            hours=float(
                environ.get(
                    "GRC_KNOWLEDGE_WORKER_CYCLE_INTERVAL_HOURS",
                    str(_DEFAULT_CYCLE_INTERVAL_HOURS),
                )
            )
        )
        poll_interval_seconds = float(
            environ.get(
                "GRC_KNOWLEDGE_WORKER_POLL_INTERVAL_SECONDS",
                str(_DEFAULT_POLL_INTERVAL_SECONDS),
            )
        )
        return cls(
            database_url=database_url,
            data_root=data_root,
            cycle_interval=cycle_interval,
            poll_interval_seconds=poll_interval_seconds,
        )


def _require_data_directories(data_root: Path) -> None:
    for name in ("knowledge-catalog", "ontology", "trusted-sources"):
        if not (data_root / name).is_dir():
            raise WorkerConfigurationError(
                f"expected {data_root / name} to exist — GRC_DATA_ROOT ({data_root}) does not "
                "look like the repo root"
            )


def _ontology_topic_files(ontology_dir: Path) -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(ontology_dir.glob("*.json"))
        if path.name not in {"contracts.json", "relationships.json"}
    )


def load_questions(data_root: Path) -> tuple[KnowledgeQuestion, ...]:
    """Every question this cycle checks coverage for: KI-P1's curated catalog plus every
    question KI-P3's ontology can mechanically generate."""
    ontology_dir = data_root / "ontology"
    catalog = build_catalog(sorted((data_root / "knowledge-catalog").glob("*.json")))
    ontology = build_ontology(
        topic_files=_ontology_topic_files(ontology_dir),
        contract_type_files=(ontology_dir / "contracts.json",),
        relationship_files=(ontology_dir / "relationships.json",),
    )
    return combine_question_sources(catalog_questions=catalog, ontology=ontology)


def load_trusted_sources(data_root: Path) -> tuple[CatalogedSource, ...]:
    """The curated, authority-typed research catalog (KI-P2) — never an open search; see
    ADR-0026."""
    return build_trusted_source_catalog(sorted((data_root / "trusted-sources").rglob("*.json")))


def _tool_context() -> ToolContext:
    """This process is not acting on behalf of any one tenant or human user — it researches
    platform-scope GRC/compliance/legal reference knowledge (ADR-0025 §5), the same scope
    ``knowledge_items`` itself is stored at. ``ToolCaller.SCHEDULED_JOB`` is one of the six
    callers CLAUDE.md §9 names explicitly."""
    return ToolContext(
        caller=ToolCaller.SCHEDULED_JOB,
        tenant_id=None,
        user_id="knowledge-worker",
        roles=_GRANTED_TOOL_PERMISSIONS,
        agent="knowledge_worker",
    )


def build_worker(
    settings: WorkerSettings,
    *,
    database: Database,
    chat_model: ChatModel,
) -> AutonomousKnowledgeWorker:
    """Assemble the real learning loop: the Tool-audited LLM extractor, the polite HTTP
    research crawler, the (unmodified) gap-research runner, and the scheduler — every piece
    reused exactly as KI-P1/KI-P2/KI-P3/KI-P4 built it, nothing reimplemented here."""
    questions = load_questions(settings.data_root)
    catalog = load_trusted_sources(settings.data_root)

    registry = ToolRegistry(recorder=PostgresToolInvocationRecorder(database))
    registry.register(SynthesizeKnowledgeAnswerTool(chat_model))
    extractor = LlmKnowledgeExtractor(registry, context=_tool_context())
    discovery_engine = KnowledgeDiscoveryEngine(extractor=extractor)
    crawler = HttpResearchCrawler(UrllibHttpFetcher())
    coordinator = ResearchCoordinator(crawler=crawler, discovery_engine=discovery_engine)
    runner = KnowledgeGapResearchRunner(
        catalog=catalog, coordinator=coordinator, store=KnowledgeItemRepository(database)
    )

    return AutonomousKnowledgeWorker(
        questions=questions,
        runner=runner,
        scheduler=LearningCycleScheduler(interval=settings.cycle_interval),
    )


async def run_forever(
    worker: AutonomousKnowledgeWorker,
    *,
    poll_interval_seconds: float,
    stop_event: asyncio.Event,
) -> None:
    """The real "repeat" step. Unlike the pure package's bounded, test-oriented
    ``run_loop``, this is genuinely unbounded and fail-safe at the process boundary
    (CLAUDE.md §16): one tick raising an exception the injected runner did not already isolate
    (e.g. the database connection itself dropping) is logged and the loop continues at the
    next poll rather than crashing the whole worker process. Waits on ``stop_event`` instead of
    a plain sleep so SIGINT/SIGTERM can interrupt a poll immediately rather than waiting out a
    full interval.
    """
    while not stop_event.is_set():
        now = datetime.now(timezone.utc)
        try:
            outcome = await worker.tick(now=now)
        except Exception:  # noqa: BLE001 - fail-safe: one bad tick must not kill the process
            logger.exception("knowledge worker tick failed; will retry next poll")
        else:
            if outcome.ran:
                logger.info(
                    "knowledge worker cycle ran: %d question(s) researched, %d stored",
                    len(outcome.outcomes),
                    outcome.stored_count,
                )
            else:
                logger.debug("knowledge worker cycle skipped: %s", outcome.reason)

        # A timeout here is the normal case: no shutdown signal arrived within this poll
        # interval, so the loop simply continues to the next tick.
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=poll_interval_seconds)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = WorkerSettings.from_env()

    database = await Database.connect(settings.database_url)
    chat_model = OpenAIChatModel(OpenAISettings.from_env())
    worker = build_worker(settings, database=database, chat_model=chat_model)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    logger.info(
        "knowledge worker starting: cycle_interval=%s poll_interval_seconds=%s",
        settings.cycle_interval,
        settings.poll_interval_seconds,
    )
    try:
        await run_forever(
            worker, poll_interval_seconds=settings.poll_interval_seconds, stop_event=stop_event
        )
    finally:
        await database.close()
        logger.info("knowledge worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
