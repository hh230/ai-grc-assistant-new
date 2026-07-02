"""Uniform error handling — every failure becomes an RFC 9457 ``application/problem+json``.

GRC is fail-safe (CLAUDE.md §6 #16): on uncertainty or error we stop with a precise, typed
problem rather than leaking internals. Application errors (raised by use cases, surfaced via the
bus ``Failure``) and domain errors (aggregate invariants / illegal transitions) are mapped to
stable HTTP status codes and machine-readable ``code``s. Every problem echoes the request/trace
id so a client can correlate it with server logs and the audit trail.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from grc_domain.shared.exceptions import (
    ApprovalRequired,
    DomainError,
    InvalidStateTransition,
    InvariantViolation,
    NotFoundError,
    TenantIsolationError,
)
from grc_services.shared.exceptions import ApplicationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..observability import current_request_context, get_logger

_logger = get_logger("grc_api.errors")

PROBLEM_CONTENT_TYPE = "application/problem+json"

# Application-error code -> HTTP status. The base falls back to 400.
_APPLICATION_STATUS: dict[str, int] = {
    "authorization_error": 403,
    "validation_error": 422,
    "not_found": 404,
    "conflict": 409,
    "concurrency_conflict": 409,
    "unit_of_work_error": 500,
    "unregistered_message": 500,
    "application_error": 400,
}

# Domain-error type -> (HTTP status, code).
_DOMAIN_STATUS: list[tuple[type[DomainError], int, str]] = [
    (InvariantViolation, 422, "invariant_violation"),
    (InvalidStateTransition, 409, "invalid_state_transition"),
    (ApprovalRequired, 409, "approval_required"),
    (TenantIsolationError, 403, "tenant_isolation_error"),
    (NotFoundError, 404, "not_found"),
    (DomainError, 422, "domain_error"),
]


class ApiError(Exception):
    """An error raised at the HTTP edge (e.g. authentication). Carries its own status."""

    status_code: int = 400
    code: str = "api_error"
    title: str = "Request failed"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or self.title)
        self.detail = detail or self.title


class AuthenticationError(ApiError):
    status_code = 401
    code = "authentication_required"
    title = "Authentication required"


class InvalidTokenError(AuthenticationError):
    code = "invalid_token"
    title = "Invalid or expired credentials"


class RateLimitedError(ApiError):
    status_code = 429
    code = "rate_limited"
    title = "Too many requests"


def _problem(
    *,
    status: int,
    title: str,
    code: str,
    detail: str | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    ctx = current_request_context()
    body: dict[str, Any] = {
        "type": f"about:blank#{code}",
        "title": title,
        "status": status,
        "code": code,
    }
    if detail:
        body["detail"] = detail
    if ctx is not None:
        body["request_id"] = ctx.request_id
        body["trace_id"] = ctx.trace_id
    if extra:
        body.update(extra)
    headers = {}
    if ctx is not None:
        headers["X-Request-Id"] = ctx.request_id
    return JSONResponse(
        status_code=status, content=body, media_type=PROBLEM_CONTENT_TYPE, headers=headers
    )


def application_error_to_problem(error: ApplicationError) -> JSONResponse:
    status = _APPLICATION_STATUS.get(error.code, 400)
    extra: dict[str, Any] = {}
    errors = getattr(error, "errors", None)
    if errors:
        extra["errors"] = errors
    title = error.code.replace("_", " ").title()
    return _problem(
        status=status, title=title, code=error.code, detail=str(error), extra=extra or None
    )


def _domain_error_to_problem(error: DomainError) -> JSONResponse:
    for error_type, status, code in _DOMAIN_STATUS:
        if isinstance(error, error_type):
            return _problem(
                status=status, title=code.replace("_", " ").title(), code=code, detail=str(error)
            )
    return _problem(status=422, title="Domain Error", code="domain_error", detail=str(error))


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _handle_api_error(_: Request, error: ApiError) -> JSONResponse:
        return _problem(
            status=error.status_code, title=error.title, code=error.code, detail=error.detail
        )

    @app.exception_handler(ApplicationError)
    async def _handle_application_error(_: Request, error: ApplicationError) -> JSONResponse:
        return application_error_to_problem(error)

    @app.exception_handler(DomainError)
    async def _handle_domain_error(_: Request, error: DomainError) -> JSONResponse:
        return _domain_error_to_problem(error)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_: Request, error: RequestValidationError) -> JSONResponse:
        return _problem(
            status=422,
            title="Validation Error",
            code="request_validation_error",
            detail="The request body or parameters failed validation.",
            extra={"errors": error.errors()},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(_: Request, error: StarletteHTTPException) -> JSONResponse:
        return _problem(
            status=error.status_code,
            title="HTTP Error",
            code="http_error",
            detail=str(error.detail),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, error: Exception) -> JSONResponse:
        # Fail safe: never leak internals. Log with correlation; return an opaque 500.
        _logger.error("unhandled_exception", exc_info=error)
        return _problem(
            status=500,
            title="Internal Server Error",
            code="internal_error",
            detail="An unexpected error occurred.",
        )
