"""Rasheed V1 Product API Host (ADR 0052) — the single FastAPI surface for REST_API_CONTRACT_V1.

A composition root over `v2/packages/*`. `create_app` builds the wired app; `app` is the ASGI
instance uvicorn serves. Both `grc_api:app` (here) and `grc_api.app:app` are runnable unseeded
entrypoints; the seeded demo app is `grc_api.dev:app`.
"""

from __future__ import annotations

from grc_api.app import app, create_app

__all__ = ["app", "create_app"]
