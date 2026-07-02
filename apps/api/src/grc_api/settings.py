"""Application settings for the Backend API (the public entry point).

Configuration is **external** (CLAUDE.md §22 / Handbook §14.13): every value comes from the
environment or a secret manager, never from source. Secrets (API keys, auth tokens) are read
from the environment and never logged. The API is provider- and store-agnostic: which
``UnitOfWork`` and which LLM provider are bound is a composition-root decision driven by these
settings, so swapping Postgres for the in-memory store, or a fake LLM for OpenAI, never touches
business code.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "development", "testing", "staging", "production"]
StoreBackend = Literal["memory", "sqlalchemy"]
LlmProvider = Literal["fake", "openai"]


class Settings(BaseSettings):
    """Typed, validated runtime configuration. Instances are immutable per process."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- App / process ----
    app_env: Environment = "local"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_title: str = "AI GRC Assistant API"
    api_root_path: str = ""  # set when served behind a gateway prefix
    log_level: str = "INFO"
    log_json: bool = True

    # ---- CORS (comma-separated origins; "*" allows all — dev only) ----
    cors_allow_origins: str = "*"

    # ---- Persistence binding (composition-root selector) ----
    # "memory": the in-process reference UnitOfWork (default; no external deps).
    # "sqlalchemy": the production Postgres/pgvector binding — gated on ADL-0008
    #               (knowledge-persistence re-alignment) and therefore not yet selectable
    #               at runtime; the composition root rejects it with a clear error.
    store_backend: StoreBackend = "memory"
    database_url: str = ""

    # ---- Authentication ----
    # Dev/test bearer tokens as a JSON object mapping token -> principal claims:
    #   {"<token>": {"user_id": "...", "organization_id": "...", "roles": ["admin"]}}
    # In production this is empty and an OIDC/JWT authenticator is wired instead (default deny).
    api_auth_tokens: str = ""
    # Only honored outside production: seeds a usable default principal + token for local dev.
    auth_seed_dev_principal: bool = True

    # ---- LLM provider (orchestrator / agents). ADL-0009: OpenAI is the approved provider. ----
    # Default "fake" keeps the API runnable and deterministic with no egress and no key
    # (CLAUDE.md §22: mock LLM calls outside live/eval suites). "openai" requires OPENAI_API_KEY.
    llm_provider: LlmProvider = "fake"
    openai_api_key: str = Field(default="", repr=False)
    openai_chat_model: str = "gpt-4o-mini"
    openai_base_url: str = ""

    # ---- Rate limiting (per principal+route; 0 disables) ----
    rate_limit_per_minute: int = 0

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        return value.upper()

    @property
    def is_production(self) -> bool:
        return self.app_env in ("staging", "production")

    @property
    def cors_origins(self) -> list[str]:
        raw = self.cors_allow_origins.strip()
        if not raw or raw == "*":
            return ["*"]
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    def auth_token_map(self) -> dict[str, dict[str, object]]:
        """Parse the configured dev/test bearer-token map. Empty/invalid -> no tokens."""
        raw = self.api_auth_tokens.strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:  # fail safe: misconfigured auth = no tokens
            raise ValueError(f"API_AUTH_TOKENS is not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("API_AUTH_TOKENS must be a JSON object {token: principal}")
        return parsed


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings singleton (cached). Override in tests via dependency_overrides."""
    return Settings()
