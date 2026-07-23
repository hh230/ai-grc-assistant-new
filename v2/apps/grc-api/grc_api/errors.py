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
