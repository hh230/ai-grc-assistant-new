/**
 * Sentry initialization for the Node.js server runtime (API routes, server components,
 * the background analysis pipeline). Loaded once via `instrumentation.ts`. Production-only:
 * without `SENTRY_DSN` set, `Sentry.init` is skipped entirely and every SDK call elsewhere
 * (`Sentry.captureException`, etc.) becomes a safe no-op, so this never affects local/dev/test.
 */

import * as Sentry from "@sentry/nextjs";

const dsn = process.env.SENTRY_DSN;

if (dsn && process.env.NODE_ENV === "production") {
  Sentry.init({
    dsn,
    environment: process.env.VERCEL_ENV ?? process.env.NODE_ENV,
    // Compliance data flows through this app — keep trace payloads lean and never attach
    // request bodies/PII by default (CLAUDE.md §19: audit records must not leak sensitive
    // customer content into a third-party tool).
    tracesSampleRate: 0.1,
    sendDefaultPii: false,
  });
}
