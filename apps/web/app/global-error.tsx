"use client";

import * as Sentry from "@sentry/nextjs";
import NextError from "next/error";
import { useEffect } from "react";

/**
 * Last-resort error boundary for the whole app — triggers if the root layout itself throws,
 * so it defines its own `<html>/<body>` and cannot depend on next-intl, Tailwind, or any other
 * app context that might be what crashed. Reports to Sentry (safe no-op today: only the
 * server/edge runtimes have a DSN configured — see sentry.server.config.ts — so no client-side
 * telemetry leaves the browser until that's a deliberate decision on its own).
 */
export default function GlobalError({ error }: { error: Error & { digest?: string } }) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html>
      <body>
        <NextError statusCode={0} />
      </body>
    </html>
  );
}
