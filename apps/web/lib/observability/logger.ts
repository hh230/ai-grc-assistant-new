/**
 * Minimal structured logger. Emits one JSON object per line (ingestible by any log
 * aggregator / monitoring pipeline) with a level, message, timestamp, and arbitrary
 * context fields. Edge-safe (console + Date only), so it works in middleware too.
 *
 * This is the seam for a full observability stack — every `logger.error` call (API errors via
 * `lib/api/respond.ts`, AI pipeline/chat failures, database pool errors) also reports to
 * Sentry via this one choke point, without touching any call site. `Sentry.captureException`
 * is a safe no-op if `Sentry.init` was never called (see `sentry.server.config.ts` — only
 * initialized in production with a DSN set), so this has no effect in dev/test.
 */

import * as Sentry from "@sentry/nextjs";

type Level = "debug" | "info" | "warn" | "error";

export interface LogFields {
  [key: string]: unknown;
}

function serializeError(error: unknown): LogFields {
  if (error instanceof Error) {
    return { errorName: error.name, errorMessage: error.message, stack: error.stack };
  }
  return { error: String(error) };
}

function emit(level: Level, message: string, fields: LogFields = {}): void {
  const entry = JSON.stringify({ level, msg: message, time: new Date().toISOString(), ...fields });
  if (level === "error") console.error(entry);
  else if (level === "warn") console.warn(entry);
  else if (level === "debug") console.debug(entry);
  else console.info(entry);
}

function report(message: string, error: unknown, fields?: LogFields): void {
  Sentry.captureException(error instanceof Error ? error : new Error(message), {
    extra: { message, ...fields },
  });
}

export const logger = {
  debug: (message: string, fields?: LogFields) => emit("debug", message, fields),
  info: (message: string, fields?: LogFields) => emit("info", message, fields),
  warn: (message: string, fields?: LogFields) => emit("warn", message, fields),
  error: (message: string, error?: unknown, fields?: LogFields) => {
    emit("error", message, { ...fields, ...(error ? serializeError(error) : {}) });
    report(message, error, fields);
  },
};
