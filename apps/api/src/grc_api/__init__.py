"""grc_api — the Backend API: the public entry point to the AI GRC Assistant (ADR-0013, 0017).

A thin, versioned, secure, async, observable FastAPI interface over the mission-centric
Application core. It validates inbound payloads, authenticates and scopes every request to a
tenant, dispatches to the Application layer through the Command/Query buses (and the AI
Orchestrator), and shapes typed responses — holding no business logic itself. Build the ASGI app
with :func:`grc_api.app.create_app`.
"""

from __future__ import annotations

from .app import API_VERSION, create_app

__all__ = ["create_app", "API_VERSION"]
__version__ = "0.0.0"
