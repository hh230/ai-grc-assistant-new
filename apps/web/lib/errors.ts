/**
 * Typed application errors mapped to HTTP status codes. Services throw these; route
 * handlers translate them with `toErrorResponse`. Shared across all API surfaces.
 */

export class AppError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly code: string,
  ) {
    super(message);
    this.name = new.target.name;
  }
}

export class ValidationError extends AppError {
  constructor(message: string) {
    super(400, message, "validation_error");
  }
}

export class ForbiddenError extends AppError {
  constructor(message = "You are not permitted to perform this action.") {
    super(403, message, "forbidden");
  }
}

export class NotFoundError extends AppError {
  constructor(message = "Not found.") {
    super(404, message, "not_found");
  }
}

/** A downstream service (e.g. the `apps/api` FastAPI backend) failed or returned an
 * unexpected shape. Distinct from the errors above, which describe *this* app rejecting the
 * request — an `UpstreamError` means the request was valid but the proxied call itself broke. */
export class UpstreamError extends AppError {
  constructor(message = "The backend service is unavailable.") {
    super(502, message, "upstream_error");
  }
}

/** The caller exceeded a usage quota (e.g. the beta per-user daily analysis limit). Maps to
 * HTTP 429 and carries a stable `code` the UI keys off to render a localized, user-friendly
 * message. */
export class RateLimitError extends AppError {
  constructor(message = "Usage limit reached.", code = "rate_limited") {
    super(429, message, code);
  }
}
