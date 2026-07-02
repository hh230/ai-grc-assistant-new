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
