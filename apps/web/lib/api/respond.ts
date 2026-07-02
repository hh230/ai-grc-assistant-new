/**
 * Shared helpers for API route handlers: uniform error mapping and the 401 response.
 */

import { NextResponse } from "next/server";
import { AppError } from "@/lib/errors";
import { logger } from "@/lib/observability/logger";

export function errorResponse(error: unknown): NextResponse {
  if (error instanceof AppError) {
    // Expected, handled errors are logged at info with their code (no stack noise).
    logger.info("api_error", { code: error.code, status: error.status, message: error.message });
    return NextResponse.json({ error: error.message, code: error.code }, { status: error.status });
  }
  logger.error("api_unhandled_error", error);
  return NextResponse.json(
    { error: "Internal server error.", code: "internal_error" },
    { status: 500 },
  );
}

export function unauthorized(): NextResponse {
  return NextResponse.json(
    { error: "Authentication required.", code: "unauthorized" },
    { status: 401 },
  );
}
