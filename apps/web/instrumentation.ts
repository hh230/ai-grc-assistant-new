/** Next.js instrumentation hook — runs once per runtime at server startup. Loads the matching
 * Sentry config so both the Node.js server and the Edge (middleware) runtime report errors. */

import * as Sentry from "@sentry/nextjs";

export async function register(): Promise<void> {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("./sentry.server.config");
  }
  if (process.env.NEXT_RUNTIME === "edge") {
    await import("./sentry.edge.config");
  }
}

// Safe without a DSN: `Sentry.init` is only called (in the configs above) when `SENTRY_DSN`
// is set in production, and `captureRequestError` is a no-op if no client was ever initialized.
export const onRequestError = Sentry.captureRequestError;
