"""The application container — the wired object graph the API serves from.

Built once at startup by the composition root (:mod:`grc_api.composition`) and stored on
``app.state``. Holds the ports the routers and dependencies need: the Command/Query buses, the
authenticator, the event dispatcher, the AI Orchestrator, and the backing store. Routers never
construct infrastructure; they read it from here.
"""

from __future__ import annotations

from dataclasses import dataclass

from grc_agents.orchestrator import Orchestrator
from grc_services.shared.authorization import AuthorizationService
from grc_services.shared.bus import CommandBus, QueryBus

from .runtime import InMemoryDatabase, LoggingEventDispatcher
from .security.authentication import TokenAuthenticator
from .settings import Settings


@dataclass(frozen=True)
class AppContainer:
    settings: Settings
    command_bus: CommandBus
    query_bus: QueryBus
    authenticator: TokenAuthenticator
    authz: AuthorizationService
    events: LoggingEventDispatcher
    orchestrator: Orchestrator
    database: InMemoryDatabase | None
    llm_provider: str
    registered_commands: int
    registered_queries: int
