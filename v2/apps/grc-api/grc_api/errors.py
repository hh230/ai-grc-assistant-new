"""The uniform error envelope (REST_API_CONTRACT_V1 §5).

Every error the API returns has the same shape — `{"error": {"code", "message", "details"?}}` — so a
client parses failures one way. `ApiError` is the one exception the routes raise; the handlers here
turn it (and framework validation errors) into that envelope. `500` never leaks provider/SDK detail.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from mission_application import (
    ApplicationError,
    DeliverableNotReady,
    IllegalCommand,
    MissionNotFound,
    NotAuthorized,
    UnsupportedFormat,
)

# How a typed Application error (ADR 0054) maps to HTTP — the one place transport meets the layer's
# failure vocabulary. Order matters only in that each is a distinct subclass.
_APP_ERROR_HTTP: tuple[tuple[type[ApplicationError], int, str], ...] = (
    (NotAuthorized, 403, "forbidden"),
    (MissionNotFound, 404, "not_found"),
    (DeliverableNotReady, 409, "conflict"),
    (IllegalCommand, 409, "conflict"),
    (UnsupportedFormat, 400, "validation_error"),
)


class ApiError(Exception):
    """A typed HTTP error carrying the contract's `code`. Routes raise it; the handler shapes it."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def _envelope(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


def register_knowledge_error_handlers(app: FastAPI) -> None:
    """The knowledge layer (ADR 0067) raises its own typed failures, and so does the schema beneath
    it. They map here, in the one place transport meets a layer's failure vocabulary — the routes
    stay free of HTTP-shaped guards.

    **A constraint the database refuses is a `409`, not a `500`.** ADR 0067 deliberately states
    rules declaratively — activating a release that was never published is unrepresentable, a
    concluded assessment accepts no further writes — so those refusals arrive as psycopg errors
    rather than Python guards. Left unmapped, the strongest guarantees in the design would surface
    to a client as "internal error", which reads as *our* bug rather than a rule working.
    """
    import psycopg
    from governance_store.knowledge_services import NotAuthorized as KnowledgeNotAuthorized

    from grc_api.knowledge_generation import GeneratedKnowledgeRejected

    @app.exception_handler(KnowledgeNotAuthorized)
    async def _handle_knowledge_not_authorized(
        _: Request, exc: KnowledgeNotAuthorized
    ) -> JSONResponse:
        return JSONResponse(status_code=403, content=_envelope("forbidden", str(exc)))

    @app.exception_handler(psycopg.errors.RaiseException)
    async def _handle_trigger_refusal(_: Request, exc: Any) -> JSONResponse:
        # A trigger's RAISE message is written to be read by whoever hit it; the surrounding
        # CONTEXT and PL/pgSQL frame are not. Only the primary message is returned.
        message = getattr(exc.diag, "message_primary", "") or "the database refused this change"
        return JSONResponse(status_code=409, content=_envelope("conflict", message))

    @app.exception_handler(psycopg.errors.IntegrityError)
    async def _handle_integrity(_: Request, exc: Any) -> JSONResponse:
        # The constraint NAME is returned and the row values are not: the name says which rule was
        # broken, while Postgres' DETAIL would echo back data the caller may not be entitled to.
        constraint = getattr(exc.diag, "constraint_name", "") or "a database constraint"
        return JSONResponse(
            status_code=409,
            content=_envelope("conflict", f"the change violates {constraint}"),
        )

    @app.exception_handler(GeneratedKnowledgeRejected)
    async def _handle_generated_rejected(
        _: Request, exc: GeneratedKnowledgeRejected
    ) -> JSONResponse:
        # `502`, not `500`: the model answered and its answer was refused. The distinction matters
        # to whoever is paged — nothing in this deployment is broken.
        return JSONResponse(
            status_code=502,
            content=_envelope("upstream_rejected", f"the generated knowledge was rejected: {exc}"),
        )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=_envelope("validation_error", "malformed request", {"errors": exc.errors()}),
        )

    @app.exception_handler(ApplicationError)
    async def _handle_application_error(_: Request, exc: ApplicationError) -> JSONResponse:
        # A command raised a typed Application failure; map it to a status code. Commands never know
        # about HTTP — this handler is the only translation point (ADR 0054).
        for error_type, status_code, code in _APP_ERROR_HTTP:
            if isinstance(exc, error_type):
                return JSONResponse(status_code=status_code, content=_envelope(code, str(exc)))
        return JSONResponse(status_code=500, content=_envelope("internal_error", "unexpected"))
